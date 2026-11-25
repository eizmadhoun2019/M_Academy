"""Content management API — ``docs/api.md`` §4.

Authorisation is capability + department scope, decided by the service layer: the class-level
permission only proves ``manage_content`` exists somewhere in the caller's grants, so an
out-of-scope course still answers 404 rather than hinting that it exists.
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from academy.api.pagination import AcademyPagination
from academy.authorization.core import Access, Capability
from academy.authorization.django import AcademyPermission
from academy.content import service
from academy.models import Course, CourseVersion, Lesson, Section


def _access(request: Request) -> Access:
    return request.auth


def _org(request: Request) -> Any:
    return _access(request).principal.organization_id


# --- serializers ------------------------------------------------------------


class CourseSerializer(serializers.ModelSerializer):
    published_version_id = serializers.SerializerMethodField()
    draft_version_id = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "description",
            "owner_department_ref",
            "status",
            "created_by_ref",
            "created_at",
            "updated_at",
            "published_version_id",
            "draft_version_id",
        ]
        read_only_fields = fields

    def _version(self, course: Course, wanted: str) -> str | None:
        versions = getattr(course, "_versions_cache", None)
        if versions is None:
            versions = list(
                CourseVersion.objects.for_org(course.organization_id).filter(course=course)
            )
            course._versions_cache = versions  # type: ignore[attr-defined]
        for version in versions:
            if version.status == wanted:
                return str(version.pk)
        return None

    def get_published_version_id(self, course: Course) -> str | None:
        return self._version(course, CourseVersion.Status.PUBLISHED)

    def get_draft_version_id(self, course: Course) -> str | None:
        return self._version(course, CourseVersion.Status.DRAFT)


class CourseWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    owner_department_ref = serializers.CharField(
        max_length=64, required=False, allow_blank=True, allow_null=True
    )


class VersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseVersion
        fields = [
            "id",
            "course_id",
            "version_number",
            "status",
            "acknowledgment_required",
            "cover_media_id",
            "published_at",
            "published_by_ref",
            "created_by_ref",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ["id", "version_id", "title", "position"]
        read_only_fields = fields


class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = [
            "id",
            "section_id",
            "title",
            "summary",
            "body",
            "position",
            "content_type",
            "media_asset_id",
            "required",
            "required_watch_percent",
        ]
        read_only_fields = fields


class SectionWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    position = serializers.IntegerField(min_value=1, required=False)


class SectionPatchSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)


class LessonWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    position = serializers.IntegerField(min_value=1, required=False)
    summary = serializers.CharField(max_length=300, required=False, allow_null=True)
    body = serializers.CharField(required=False, allow_blank=True)
    content_type = serializers.ChoiceField(
        choices=[item.value for item in Lesson.ContentType], required=False
    )
    media_asset_id = serializers.UUIDField(required=False, allow_null=True)
    required = serializers.BooleanField(required=False)
    required_watch_percent = serializers.IntegerField(min_value=50, max_value=100, required=False)


class LessonPatchSerializer(LessonWriteSerializer):
    title = serializers.CharField(max_length=200, required=False)


class ReorderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)


def _ordered_ids(serializer: ReorderSerializer) -> list[Any]:
    return list(serializer.validated_data["ids"])


def _version_payload(version: CourseVersion) -> dict[str, Any]:
    sections = list(Section.objects.for_org(version.organization_id).filter(version=version))
    sections.sort(key=lambda row: row.position)
    lessons = list(Lesson.objects.for_org(version.organization_id).filter(section__version=version))
    by_section: dict[Any, list[Lesson]] = {}
    for lesson in lessons:
        by_section.setdefault(lesson.section_id, []).append(lesson)
    payload = dict(VersionSerializer(version).data)
    payload["sections"] = []
    for section in sections:
        row = dict(SectionSerializer(section).data)
        row["lessons"] = [
            dict(LessonSerializer(lesson).data)
            for lesson in sorted(by_section.get(section.pk, []), key=lambda item: item.position)
        ]
        payload["sections"].append(row)
    return payload


# --- courses ----------------------------------------------------------------


class CourseListCreateView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(responses=CourseSerializer(many=True))
    def get(self, request: Request) -> Response:
        rows = list(service.list_courses(_access(request)))
        status_filter = request.query_params.get("status")
        department = request.query_params.get("owner_department_ref")
        query = (request.query_params.get("q") or "").strip()
        if status_filter:
            rows = [row for row in rows if row.status == status_filter]
        if department:
            rows = [row for row in rows if row.owner_department_ref == department]
        if query:
            rows = [row for row in rows if query.casefold() in row.title.casefold()]
        paginator = AcademyPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(CourseSerializer(page, many=True).data)

    @extend_schema(request=CourseWriteSerializer, responses=CourseSerializer)
    def post(self, request: Request) -> Response:
        serializer = CourseWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        course = service.create_course(
            _access(request),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            owner_department_ref=data.get("owner_department_ref") or None,
        )
        return Response(CourseSerializer(course).data, status=status.HTTP_201_CREATED)


class CourseDetailView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(responses=CourseSerializer)
    def get(self, request: Request, course_id: Any) -> Response:
        course = service.require_course(_access(request), _org(request), course_id)
        payload = dict(CourseSerializer(course).data)
        versions = CourseVersion.objects.for_org(_org(request)).filter(course=course)
        payload["versions"] = VersionSerializer(versions.order_by("version_number"), many=True).data
        return Response(payload)

    @extend_schema(request=CourseWriteSerializer, responses=CourseSerializer)
    def patch(self, request: Request, course_id: Any) -> Response:
        course = service.require_course(_access(request), _org(request), course_id)
        serializer = CourseWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        course = service.update_course(
            _access(request),
            course,
            title=data.get("title"),
            description=data.get("description"),
            owner_department_ref=data.get("owner_department_ref", Ellipsis),
        )
        return Response(CourseSerializer(course).data)


class CourseArchiveView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(request=None, responses=CourseSerializer)
    def post(self, request: Request, course_id: Any) -> Response:
        course = service.require_course(_access(request), _org(request), course_id)
        return Response(CourseSerializer(service.archive_course(_access(request), course)).data)


class CourseCloneView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(request=None, responses=VersionSerializer)
    def post(self, request: Request, course_id: Any) -> Response:
        course = service.require_course(_access(request), _org(request), course_id)
        version = service.clone_version(_access(request), course)
        return Response(VersionSerializer(version).data, status=status.HTTP_201_CREATED)


# --- versions ---------------------------------------------------------------


class VersionDetailView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(responses=VersionSerializer)
    def get(self, request: Request, version_id: Any) -> Response:
        version = service.require_version(_access(request), _org(request), version_id)
        return Response(_version_payload(version))


class VersionPublishView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(request=None, responses=VersionSerializer)
    def post(self, request: Request, version_id: Any) -> Response:
        version = service.require_version(_access(request), _org(request), version_id)
        version = service.publish_version(_access(request), version)
        return Response(_version_payload(version))


class VersionDiscardView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(request=None, responses=None)
    def post(self, request: Request, version_id: Any) -> Response:
        version = service.require_version(_access(request), _org(request), version_id)
        service.discard_version(_access(request), version)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- sections ---------------------------------------------------------------


class VersionSectionsView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(responses=SectionSerializer(many=True))
    def get(self, request: Request, version_id: Any) -> Response:
        version = service.require_version(_access(request), _org(request), version_id)
        rows = Section.objects.for_org(_org(request)).filter(version=version).order_by("position")
        return Response(SectionSerializer(rows, many=True).data)

    @extend_schema(request=SectionWriteSerializer, responses=SectionSerializer)
    def post(self, request: Request, version_id: Any) -> Response:
        version = service.require_version(_access(request), _org(request), version_id)
        serializer = SectionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        section = service.create_section(
            _access(request),
            version,
            title=str(serializer.validated_data["title"]),
            position=serializer.validated_data.get("position"),
        )
        return Response(SectionSerializer(section).data, status=status.HTTP_201_CREATED)


class SectionDetailView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(request=SectionPatchSerializer, responses=SectionSerializer)
    def patch(self, request: Request, section_id: Any) -> Response:
        section = service.require_section(_access(request), _org(request), section_id)
        serializer = SectionPatchSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if "title" in serializer.validated_data:
            section = service.update_section(
                _access(request), section, title=str(serializer.validated_data["title"])
            )
        return Response(SectionSerializer(section).data)

    @extend_schema(request=None, responses=None)
    def delete(self, request: Request, section_id: Any) -> Response:
        section = service.require_section(_access(request), _org(request), section_id)
        service.delete_section(_access(request), section)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SectionReorderView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(request=ReorderSerializer, responses=SectionSerializer(many=True))
    def post(self, request: Request, version_id: Any) -> Response:
        version = service.require_version(_access(request), _org(request), version_id)
        serializer = ReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = service.reorder_sections(_access(request), version, _ordered_ids(serializer))
        return Response(SectionSerializer(rows, many=True).data)


# --- lessons ----------------------------------------------------------------


class SectionLessonsView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(responses=LessonSerializer(many=True))
    def get(self, request: Request, section_id: Any) -> Response:
        section = service.require_section(_access(request), _org(request), section_id)
        rows = Lesson.objects.for_org(_org(request)).filter(section=section).order_by("position")
        return Response(LessonSerializer(rows, many=True).data)

    @extend_schema(request=LessonWriteSerializer, responses=LessonSerializer)
    def post(self, request: Request, section_id: Any) -> Response:
        section = service.require_section(_access(request), _org(request), section_id)
        serializer = LessonWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        title = str(data.pop("title"))
        position = data.pop("position", None)
        lesson = service.create_lesson(
            _access(request), section, title=title, position=position, **data
        )
        return Response(LessonSerializer(lesson).data, status=status.HTTP_201_CREATED)


class LessonDetailView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(request=LessonPatchSerializer, responses=LessonSerializer)
    def patch(self, request: Request, lesson_id: Any) -> Response:
        lesson = service.require_lesson(_access(request), _org(request), lesson_id)
        serializer = LessonPatchSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        if "media_asset_id" in data:
            data["media_asset"] = data.pop("media_asset_id")
        lesson = service.update_lesson(_access(request), lesson, data)
        return Response(LessonSerializer(lesson).data)

    @extend_schema(request=None, responses=None)
    def delete(self, request: Request, lesson_id: Any) -> Response:
        service.delete_lesson(
            _access(request), service.require_lesson(_access(request), _org(request), lesson_id)
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class LessonReorderView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(request=ReorderSerializer, responses=LessonSerializer(many=True))
    def post(self, request: Request, section_id: Any) -> Response:
        section = service.require_section(_access(request), _org(request), section_id)
        serializer = ReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = service.reorder_lessons(_access(request), section, _ordered_ids(serializer))
        return Response(LessonSerializer(rows, many=True).data)
