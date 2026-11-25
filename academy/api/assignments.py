"""Assignment and learner API — ``docs/api.md`` §3 and §5.

The class-level capability only proves ``academy.assign`` exists somewhere in the caller's
grants; the service decides whether the *target* is inside the caller's scope, and an
out-of-scope object still answers 404 so the API never hints that it exists.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from academy.api.pagination import AcademyPagination
from academy.assignments import selectors, service
from academy.assignments.expansion import expand_target
from academy.authorization.core import Access, Capability
from academy.authorization.django import AcademyPermission
from academy.exceptions import DomainValidationError
from academy.models import Assignment, Enrollment

IDEMPOTENCY_TTL = 24 * 60 * 60
TARGET_TYPES = [item.value for item in Assignment.TargetType]


def _access(request: Request) -> Access:
    return request.auth


def _org(request: Request) -> Any:
    return _access(request).principal.organization_id


# --- serializers ------------------------------------------------------------


class AssignmentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    course_id = serializers.UUIDField()
    target_type = serializers.CharField()
    target_ref = serializers.CharField(allow_null=True)
    due_at = serializers.DateTimeField(allow_null=True)
    mandatory = serializers.BooleanField()
    note = serializers.CharField(allow_null=True)
    assigned_by_ref = serializers.CharField()
    cancelled_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    enrollment_count = serializers.SerializerMethodField()

    def get_enrollment_count(self, obj: Assignment) -> int:
        counts = self.context.get("counts")
        if isinstance(counts, dict):
            return int(counts.get(obj.pk, 0))
        return (
            Enrollment.objects.for_org(obj.organization_id)
            .filter(assignment=obj, status=Enrollment.Status.ACTIVE)
            .count()
        )


class AssignmentCreateSerializer(serializers.Serializer):
    course_id = serializers.UUIDField()
    target_type = serializers.ChoiceField(choices=TARGET_TYPES)
    target_ref = serializers.CharField(
        max_length=64, required=False, allow_blank=True, allow_null=True
    )
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    mandatory = serializers.BooleanField(required=False, default=True)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)


class PreviewSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=TARGET_TYPES)
    target_ref = serializers.CharField(
        max_length=64, required=False, allow_blank=True, allow_null=True
    )


class PreviewResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    capped = serializers.BooleanField()


class EnrollmentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    assignment_id = serializers.UUIDField(allow_null=True)
    course_id = serializers.UUIDField()
    course_version_id = serializers.UUIDField()
    user_ref = serializers.CharField()
    status = serializers.CharField()
    due_at = serializers.DateTimeField(allow_null=True)
    mandatory = serializers.BooleanField()
    acknowledged_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    cancelled_at = serializers.DateTimeField(allow_null=True)
    cancel_reason = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()


class OutlineLessonSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    summary = serializers.CharField(allow_null=True)
    position = serializers.IntegerField()
    content_type = serializers.CharField()
    required = serializers.BooleanField()
    required_watch_percent = serializers.IntegerField()
    media_asset_id = serializers.UUIDField(allow_null=True)
    locked = serializers.BooleanField()
    completed = serializers.BooleanField()


class OutlineSectionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    position = serializers.IntegerField()
    lessons = OutlineLessonSerializer(many=True)


class MyEnrollmentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    course_id = serializers.UUIDField()
    course_title = serializers.CharField()
    course_version_id = serializers.UUIDField()
    version_number = serializers.IntegerField()
    status = serializers.CharField()
    user_ref = serializers.CharField()
    due_at = serializers.DateTimeField(allow_null=True)
    mandatory = serializers.BooleanField()
    acknowledgment_required = serializers.BooleanField()
    acknowledged = serializers.BooleanField()
    completed_at = serializers.DateTimeField(allow_null=True)
    cancelled_at = serializers.DateTimeField(allow_null=True)
    cancel_reason = serializers.CharField(allow_null=True)
    progress_percent = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class MyEnrollmentDetailSerializer(MyEnrollmentSerializer):
    sections = OutlineSectionSerializer(many=True)


# --- helpers ----------------------------------------------------------------


def _counts(organization_id: Any, assignments: list[Assignment]) -> dict[Any, int]:
    if not assignments:
        return {}
    rows = (
        Enrollment.objects.for_org(organization_id)
        .filter(
            assignment_id__in=[row.pk for row in assignments],
            status=Enrollment.Status.ACTIVE,
        )
        .values("assignment_id")
    )
    counts: dict[Any, int] = {}
    for row in rows:
        counts[row["assignment_id"]] = counts.get(row["assignment_id"], 0) + 1
    return counts


def _replay_key(request: Request, organization_id: Any) -> str | None:
    key = request.headers.get("Idempotency-Key", "").strip()
    if not key:
        return None
    return f"macademy:idempotency:assignment:{organization_id}:{key}"


# --- management: assignments ------------------------------------------------


class AssignmentListCreateView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.ASSIGN
    throttle_scope = "write"

    @extend_schema(responses=AssignmentSerializer(many=True))
    def get(self, request: Request) -> Response:
        access = _access(request)
        course_id = request.query_params.get("course")
        target_type = request.query_params.get("target_type")
        active_raw = request.query_params.get("active")
        rows = selectors.list_assignments(
            access,
            course_id=UUID(str(course_id)) if course_id else None,
            target_type=target_type or None,
            active=None if active_raw is None else active_raw.lower() == "true",
        )
        paginator = AcademyPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        counts = _counts(_org(request), list(page))
        data = AssignmentSerializer(page, many=True, context={"counts": counts}).data
        return paginator.get_paginated_response(data)

    @extend_schema(request=AssignmentCreateSerializer, responses=AssignmentSerializer)
    def post(self, request: Request) -> Response:
        serializer = AssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        organization_id = _org(request)
        cache_key = _replay_key(request, organization_id)
        if cache_key is None:
            raise DomainValidationError(
                "an Idempotency-Key header is required",
                fields={"Idempotency-Key": "required for assignment creation"},
            )
        digest = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
        stored = cache.get(cache_key)
        if isinstance(stored, dict):
            if stored.get("digest") != digest:
                raise DomainValidationError(
                    "this Idempotency-Key was used for a different request",
                    fields={"Idempotency-Key": "reused with a different body"},
                )
            existing = (
                Assignment.objects.for_org(organization_id)
                .filter(pk=stored["assignment_id"])
                .first()
            )
            if existing is not None:
                return Response(AssignmentSerializer(existing).data, status=status.HTTP_200_OK)
        course = selectors.require_course(organization_id, data["course_id"])
        assignment = service.create_assignment(
            _access(request),
            course=course,
            target_type=str(data["target_type"]),
            target_ref=data.get("target_ref") or None,
            due_at=data.get("due_at"),
            mandatory=bool(data.get("mandatory", True)),
            note=data.get("note") or None,
        )
        cache.set(
            cache_key, {"digest": digest, "assignment_id": str(assignment.pk)}, IDEMPOTENCY_TTL
        )
        return Response(AssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)


class AssignmentPreviewView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.ASSIGN
    throttle_scope = "read"

    @extend_schema(request=PreviewSerializer, responses=PreviewResponseSerializer)
    def post(self, request: Request) -> Response:
        serializer = PreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        access = _access(request)
        kind, ref = service.validate_target(str(data["target_type"]), data.get("target_ref"))
        service.require_target_scope(access, kind, ref)
        expansion = expand_target(access.principal.organization_id, kind, ref)
        return Response({"count": expansion.count, "capped": expansion.capped})


class AssignmentDetailView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.ASSIGN
    throttle_scope = "write"

    @extend_schema(request=None, responses=None)
    def delete(self, request: Request, assignment_id: Any) -> Response:
        assignment = selectors.require_assignment(_access(request), _org(request), assignment_id)
        service.cancel_assignment(_access(request), assignment)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CourseRosterView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.ASSIGN
    throttle_scope = "read"

    @extend_schema(responses=EnrollmentSerializer(many=True))
    def get(self, request: Request, course_id: Any) -> Response:
        access = _access(request)
        course = selectors.require_course(_org(request), course_id)
        overdue_raw = request.query_params.get("overdue")
        rows = selectors.roster(
            access,
            course,
            status=request.query_params.get("status") or None,
            overdue=None if overdue_raw is None else overdue_raw.lower() == "true",
            department_ref=request.query_params.get("department_ref") or None,
        )
        paginator = AcademyPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(EnrollmentSerializer(page, many=True).data)


class EnrollmentCancelView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.ASSIGN
    throttle_scope = "write"

    @extend_schema(request=None, responses=None)
    def post(self, request: Request, enrollment_id: Any) -> Response:
        enrollment = selectors.require_managed_enrollment(
            _access(request), _org(request), enrollment_id
        )
        service.cancel_enrollment(_access(request), enrollment)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- learner ----------------------------------------------------------------


def _paged(request: Request, rows: list[Any], serializer: Any, view: APIView) -> Response:
    paginator = AcademyPagination()
    page = paginator.paginate_queryset(rows, request, view=view)
    response = paginator.get_paginated_response(serializer(page, many=True).data)
    response["Cache-Control"] = "private, no-store"
    return response


class MyCoursesView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.LEARN
    throttle_scope = "read"

    @extend_schema(responses=MyEnrollmentSerializer(many=True))
    def get(self, request: Request) -> Response:
        access = _access(request)
        rows = selectors.my_enrollments(access, status=Enrollment.Status.ACTIVE)
        return _paged(
            request,
            [selectors.enrollment_payload(row) for row in rows],
            MyEnrollmentSerializer,
            self,
        )


class MyEnrollmentsView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.LEARN
    throttle_scope = "read"

    @extend_schema(responses=MyEnrollmentSerializer(many=True))
    def get(self, request: Request) -> Response:
        access = _access(request)
        rows = selectors.my_enrollments(access, status=request.query_params.get("status") or None)
        return _paged(
            request,
            [selectors.enrollment_payload(row) for row in rows],
            MyEnrollmentSerializer,
            self,
        )


class EnrollmentDetailView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.LEARN
    throttle_scope = "read"

    @extend_schema(responses=MyEnrollmentDetailSerializer)
    def get(self, request: Request, enrollment_id: Any) -> Response:
        enrollment = selectors.require_own_enrollment(_access(request), enrollment_id)
        payload = selectors.enrollment_payload(enrollment, with_outline=True)
        return Response(payload, headers={"Cache-Control": "private, no-store"})
