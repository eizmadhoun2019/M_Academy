"""Content services — ``docs/api.md`` §4 and ``docs/domain-model.md`` §2.1–§2.4.

Every write checks the caller's capability *and* the course's department scope, runs inside one
transaction and appends its audit row there. Published versions are frozen by a database
trigger; these services refuse the edit earlier with a readable 409 so the API never surfaces a
trigger error.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from academy.audit import record
from academy.authorization.core import Access, Capability
from academy.content.validation import validate_for_publish
from academy.exceptions import (
    DomainValidationError,
    Forbidden,
    NotFound,
    PublishInvalid,
    StateConflict,
)
from academy.models import Course, CourseVersion, Lesson, Section

MAX_TITLE = 200


def manageable(access: Access, course: Course) -> bool:
    """Department managers own their departments' courses; general courses are admin-only."""
    if not access.granted(Capability.MANAGE_CONTENT):
        return False
    if course.owner_department_ref is None:
        return access.allows(Capability.ADMIN)
    return bool(
        access.allows(Capability.MANAGE_CONTENT, department_ref=course.owner_department_ref)
    )


def require_course(access: Access, organization_id: UUID, course_id: UUID) -> Course:
    course = Course.objects.for_org(organization_id).filter(pk=course_id).first()
    if course is None or not manageable(access, course):
        # Same answer for missing and out of scope: no cross-tenant or cross-department hint.
        raise NotFound("course not found")
    return course


def require_version(access: Access, organization_id: UUID, version_id: UUID) -> CourseVersion:
    version = (
        CourseVersion.objects.for_org(organization_id)
        .select_related("course")
        .filter(pk=version_id)
        .first()
    )
    if version is None or not manageable(access, version.course):
        raise NotFound("version not found")
    return version


def require_section(access: Access, organization_id: UUID, section_id: UUID) -> Section:
    row = (
        Section.objects.for_org(organization_id)
        .select_related("version__course")
        .filter(pk=section_id)
        .first()
    )
    if row is None or not manageable(access, row.version.course):
        raise NotFound("section not found")
    return row


def require_lesson(access: Access, organization_id: UUID, lesson_id: UUID) -> Lesson:
    row = (
        Lesson.objects.for_org(organization_id)
        .select_related("section__version__course")
        .filter(pk=lesson_id)
        .first()
    )
    if row is None or not manageable(access, row.section.version.course):
        raise NotFound("lesson not found")
    return row


def _require_draft(version: CourseVersion) -> None:
    if version.status == CourseVersion.Status.PUBLISHED:
        raise StateConflict("version_published", "a published version is immutable")
    if version.status == CourseVersion.Status.ARCHIVED:
        raise StateConflict("version_published", "an archived version cannot be edited")


def _audit(
    access: Access,
    action: str,
    object_type: str,
    object_id: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    record(
        organization_id=access.principal.organization_id,
        actor_ref=access.principal.user_ref,
        action=action,
        object_type=object_type,
        object_id=object_id,
        metadata=metadata,
    )


# --- courses ----------------------------------------------------------------


def list_courses(access: Access) -> Sequence[Course]:
    rows = Course.objects.for_org(access.principal.organization_id).order_by("title")
    return [course for course in rows if manageable(access, course)]


def create_course(
    access: Access,
    *,
    title: str,
    description: str = "",
    owner_department_ref: str | None = None,
) -> Course:
    if not title.strip():
        raise DomainValidationError("a course needs a title")
    if owner_department_ref is None:
        if not access.allows(Capability.ADMIN):
            raise Forbidden("a general course can only be created by an administrator")
    elif not access.allows(Capability.MANAGE_CONTENT, department_ref=owner_department_ref):
        raise Forbidden("the department is outside your content scope")
    if not access.granted(Capability.MANAGE_CONTENT):
        raise Forbidden("missing manage_content")

    with transaction.atomic():
        course = Course.objects.create(
            organization_id=access.principal.organization_id,
            title=title.strip(),
            description=description,
            owner_department_ref=owner_department_ref,
            created_by_ref=access.principal.user_ref,
        )
        version = CourseVersion.objects.create(
            organization_id=course.organization_id,
            course=course,
            version_number=1,
            created_by_ref=access.principal.user_ref,
        )
        _audit(access, "course.created", "Course", str(course.pk), {"version_id": str(version.pk)})
    return course


def update_course(
    access: Access,
    course: Course,
    *,
    title: str | None = None,
    description: str | None = None,
    owner_department_ref: Any = Ellipsis,
) -> Course:
    published = CourseVersion.objects.for_org(course.organization_id).filter(
        course=course, status=CourseVersion.Status.PUBLISHED
    )
    if owner_department_ref is not Ellipsis and published.exists():
        raise StateConflict(
            "course_published_locked",
            "the owner department is frozen while a version is published",
        )
    if owner_department_ref is not Ellipsis:
        value = owner_department_ref or None
        if value is None:
            if not access.allows(Capability.ADMIN):
                raise Forbidden("only an administrator can make a course general")
        elif not access.allows(Capability.MANAGE_CONTENT, department_ref=value):
            raise Forbidden("the department is outside your content scope")
        course.owner_department_ref = value
    if title is not None:
        if not title.strip():
            raise DomainValidationError("a course needs a title")
        course.title = title.strip()
    if description is not None:
        course.description = description
    course.save()
    _audit(access, "course.updated", "Course", str(course.pk))
    return course


def archive_course(access: Access, course: Course) -> Course:
    with transaction.atomic():
        published = CourseVersion.objects.for_org(course.organization_id).filter(
            course=course, status=CourseVersion.Status.PUBLISHED
        )
        for version in published:
            version.status = CourseVersion.Status.ARCHIVED
            version.save(update_fields=["status", "updated_at"])
        course.status = Course.Status.ARCHIVED
        course.save(update_fields=["status", "updated_at"])
        _audit(access, "course.archived", "Course", str(course.pk))
    return course


def clone_version(access: Access, course: Course) -> CourseVersion:
    """Clone the published version (or the latest) into a fresh draft; one draft at a time."""
    if (
        CourseVersion.objects.for_org(course.organization_id)
        .filter(course=course, status=CourseVersion.Status.DRAFT)
        .exists()
    ):
        raise StateConflict("draft_exists", "this course already has an open draft")
    source = (
        CourseVersion.objects.for_org(course.organization_id)
        .filter(course=course)
        .order_by("-version_number")
        .first()
    )
    if source is None:
        raise NotFound("the course has no version to clone")
    next_number = (
        CourseVersion.objects.for_org(course.organization_id)
        .filter(course=course)
        .aggregate(Max("version_number"))["version_number__max"]
        or 0
    ) + 1

    with transaction.atomic():
        clone = CourseVersion.objects.create(
            organization_id=course.organization_id,
            course=course,
            version_number=next_number,
            acknowledgment_required=source.acknowledgment_required,
            cover_media=source.cover_media,
            created_by_ref=access.principal.user_ref,
        )
        for section in Section.objects.for_org(course.organization_id).filter(version=source):
            copied = Section.objects.create(
                organization_id=course.organization_id,
                version=clone,
                title=section.title,
                position=section.position,
            )
            for lesson in Lesson.objects.for_org(course.organization_id).filter(section=section):
                Lesson.objects.create(
                    organization_id=course.organization_id,
                    section=copied,
                    title=lesson.title,
                    summary=lesson.summary,
                    body=lesson.body,
                    position=lesson.position,
                    content_type=lesson.content_type,
                    media_asset=lesson.media_asset,
                    required=lesson.required,
                    required_watch_percent=lesson.required_watch_percent,
                )
        _audit(
            access,
            "version.cloned",
            "CourseVersion",
            str(clone.pk),
            {"source_version_id": str(source.pk)},
        )
    return clone


def publish_version(access: Access, version: CourseVersion) -> CourseVersion:
    if version.status != CourseVersion.Status.DRAFT:
        raise StateConflict("version_published", "only a draft can be published")
    reasons = validate_for_publish(version)
    if reasons:
        raise PublishInvalid(
            "the version does not meet the publish rules", fields={"items": reasons}
        )

    with transaction.atomic():
        previous = CourseVersion.objects.for_org(version.organization_id).filter(
            course=version.course, status=CourseVersion.Status.PUBLISHED
        )
        for row in previous:
            row.status = CourseVersion.Status.ARCHIVED
            row.save(update_fields=["status", "updated_at"])
        version.status = CourseVersion.Status.PUBLISHED
        version.published_at = timezone.now()
        version.published_by_ref = access.principal.user_ref
        version.save(update_fields=["status", "published_at", "published_by_ref", "updated_at"])
        course = version.course
        course.status = Course.Status.PUBLISHED
        course.save(update_fields=["status", "updated_at"])
        _audit(
            access,
            "course.published",
            "CourseVersion",
            str(version.pk),
            {"course_id": str(course.pk), "version_number": version.version_number},
        )
    return version


def discard_version(access: Access, version: CourseVersion) -> None:
    if version.status != CourseVersion.Status.DRAFT:
        raise StateConflict("version_published", "only a draft can be discarded")
    with transaction.atomic():
        _audit(
            access,
            "version.discarded",
            "CourseVersion",
            str(version.pk),
            {"course_id": str(version.course_id)},
        )
        version.delete()


# --- sections ---------------------------------------------------------------


def create_section(
    access: Access, version: CourseVersion, *, title: str, position: int | None = None
) -> Section:
    _require_draft(version)
    if not title.strip():
        raise DomainValidationError("a section needs a title")
    with transaction.atomic():
        if position is None:
            last = (
                Section.objects.for_org(version.organization_id)
                .filter(version=version)
                .aggregate(Max("position"))["position__max"]
                or 0
            )
            position = last + 1
        section = Section.objects.create(
            organization_id=version.organization_id,
            version=version,
            title=title.strip(),
            position=position,
        )
        _audit(access, "section.created", "Section", str(section.pk))
    return section


def update_section(access: Access, section: Section, *, title: str) -> Section:
    _require_draft(section.version)
    if not title.strip():
        raise DomainValidationError("a section needs a title")
    section.title = title.strip()
    section.save(update_fields=["title", "updated_at"])
    _audit(access, "section.updated", "Section", str(section.pk))
    return section


def delete_section(access: Access, section: Section) -> None:
    _require_draft(section.version)
    with transaction.atomic():
        _audit(access, "section.deleted", "Section", str(section.pk))
        section.delete()


def reorder_sections(
    access: Access, version: CourseVersion, ordered_ids: Sequence[UUID]
) -> Sequence[Section]:
    _require_draft(version)
    rows = list(Section.objects.for_org(version.organization_id).filter(version=version))
    if sorted(row.pk for row in rows) != sorted(set(ordered_ids)):
        raise StateConflict("position_mismatch", "the list must name every section exactly once")
    by_id = {row.pk: row for row in rows}
    with transaction.atomic():
        for index, section_id in enumerate(ordered_ids, start=1):
            by_id[section_id].position = index
            by_id[section_id].save(update_fields=["position", "updated_at"])
        _audit(access, "section.reordered", "CourseVersion", str(version.pk))
    return [by_id[section_id] for section_id in ordered_ids]


# --- lessons ----------------------------------------------------------------


def _apply_lesson_fields(lesson: Lesson, fields: dict[str, Any]) -> None:
    for name in (
        "title",
        "summary",
        "body",
        "content_type",
        "media_asset",
        "required",
        "required_watch_percent",
    ):
        if name in fields and fields[name] is not None:
            setattr(lesson, name, fields[name])


def create_lesson(
    access: Access,
    section: Section,
    *,
    title: str,
    position: int | None = None,
    **fields: Any,
) -> Lesson:
    _require_draft(section.version)
    with transaction.atomic():
        if position is None:
            last = (
                Lesson.objects.for_org(section.organization_id)
                .filter(section=section)
                .aggregate(Max("position"))["position__max"]
                or 0
            )
            position = last + 1
        lesson = Lesson(
            organization_id=section.organization_id,
            section=section,
            title=title.strip(),
            position=position,
        )
        _apply_lesson_fields(lesson, fields)
        lesson.full_clean(exclude=["body"], validate_unique=False)
        lesson.save()
        _audit(access, "lesson.created", "Lesson", str(lesson.pk))
    return lesson


def update_lesson(access: Access, lesson: Lesson, fields: dict[str, Any]) -> Lesson:
    _require_draft(lesson.section.version)
    if "title" in fields:
        fields["title"] = str(fields["title"]).strip()
    _apply_lesson_fields(lesson, fields)
    lesson.full_clean(exclude=["body"], validate_unique=False)
    lesson.save()
    _audit(access, "lesson.updated", "Lesson", str(lesson.pk))
    return lesson


def delete_lesson(access: Access, lesson: Lesson) -> None:
    _require_draft(lesson.section.version)
    with transaction.atomic():
        _audit(access, "lesson.deleted", "Lesson", str(lesson.pk))
        lesson.delete()


def reorder_lessons(
    access: Access, section: Section, ordered_ids: Sequence[UUID]
) -> Sequence[Lesson]:
    _require_draft(section.version)
    rows = list(Lesson.objects.for_org(section.organization_id).filter(section=section))
    if sorted(row.pk for row in rows) != sorted(set(ordered_ids)):
        raise StateConflict("position_mismatch", "the list must name every lesson exactly once")
    by_id = {row.pk: row for row in rows}
    with transaction.atomic():
        for index, lesson_id in enumerate(ordered_ids, start=1):
            by_id[lesson_id].position = index
            by_id[lesson_id].save(update_fields=["position", "updated_at"])
        _audit(access, "lesson.reordered", "Section", str(section.pk))
    return [by_id[lesson_id] for lesson_id in ordered_ids]


__all__ = [
    "require_course",
    "require_version",
    "_require_draft",
    "manageable",
    "require_course",
    "require_lesson",
    "require_section",
    "require_version",
    "archive_course",
    "clone_version",
    "create_course",
    "create_lesson",
    "create_section",
    "delete_lesson",
    "delete_section",
    "discard_version",
    "list_courses",
    "publish_version",
    "reorder_lessons",
    "reorder_sections",
    "update_course",
    "update_lesson",
    "update_section",
]
