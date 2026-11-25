"""Read paths for assignments and enrollments — ``docs/api.md`` §3 and §5.

Write rules live in :mod:`academy.assignments.service`; these helpers only decide what a
caller may see, always through ``for_org`` and never from a client-supplied organization.

Visibility follows the capability's scope: an all-department ``academy.assign`` holder sees
every assignment, while a department manager sees the assignments whose target is one of their
departments (or, for a single-member target, whose member belongs to one of them). Role and
organization targets span the whole tenant, so they are visible to the org-wide holder only.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from academy.adapters.organization import MAX_USER_REFS
from academy.assignments import expansion, gating
from academy.authorization.core import Access, Capability
from academy.exceptions import NotFound
from academy.models import Assignment, Course, Enrollment

ASSIGNMENT_STATUSES = ("active", "completed", "cancelled")


def _chunks(values: Sequence[str], size: int) -> list[Sequence[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _member_departments(
    organization_id: UUID, user_refs: Sequence[str]
) -> dict[str, frozenset[str]]:
    """Department references of the given members, looked up in batches of 50."""
    found: dict[str, frozenset[str]] = {}
    for chunk in _chunks(list(dict.fromkeys(user_refs)), MAX_USER_REFS):
        for user in expansion.directory().users(organization_id, chunk):
            found[user.user_ref] = frozenset(user.department_refs)
    return found


def visible(access: Access, assignment: Assignment, departments: dict[str, frozenset[str]]) -> bool:
    """Whether the caller may see (and act on) this assignment."""
    if not access.granted(Capability.ASSIGN):
        return False
    if access.covers_all_departments(Capability.ASSIGN):
        return True
    kind = assignment.target_type
    if kind == Assignment.TargetType.DEPARTMENT:
        return access.allows(Capability.ASSIGN, department_ref=assignment.target_ref)
    if kind == Assignment.TargetType.USER:
        refs = departments.get(str(assignment.target_ref), frozenset())
        return any(access.allows(Capability.ASSIGN, department_ref=ref) for ref in refs)
    return False


def _departments_for(
    access: Access, assignments: Sequence[Assignment], organization_id: UUID
) -> dict[str, frozenset[str]]:
    if access.covers_all_departments(Capability.ASSIGN):
        return {}
    refs = [
        str(row.target_ref)
        for row in assignments
        if row.target_type == Assignment.TargetType.USER and row.target_ref
    ]
    return _member_departments(organization_id, refs) if refs else {}


def visible_assignments(
    access: Access, assignments: Sequence[Assignment], organization_id: UUID
) -> list[Assignment]:
    departments = _departments_for(access, assignments, organization_id)
    return [row for row in assignments if visible(access, row, departments)]


def list_assignments(
    access: Access,
    *,
    course_id: UUID | None = None,
    target_type: str | None = None,
    active: bool | None = None,
) -> list[Assignment]:
    organization_id = access.principal.organization_id
    rows = list(
        Assignment.objects.for_org(organization_id).select_related("course").order_by("-created_at")
    )
    if course_id is not None:
        rows = [row for row in rows if row.course_id == course_id]
    if target_type:
        rows = [row for row in rows if row.target_type == target_type]
    if active is not None:
        rows = [row for row in rows if (row.cancelled_at is None) == active]
    return visible_assignments(access, rows, organization_id)


def require_assignment(access: Access, organization_id: UUID, assignment_id: UUID) -> Assignment:
    row = (
        Assignment.objects.for_org(organization_id)
        .select_related("course")
        .filter(pk=assignment_id)
        .first()
    )
    if row is None:
        raise NotFound("assignment not found")
    departments = _departments_for(access, [row], organization_id)
    if not visible(access, row, departments):
        raise NotFound("assignment not found")
    return row


def require_course(organization_id: UUID, course_id: UUID) -> Course:
    course = Course.objects.for_org(organization_id).filter(pk=course_id).first()
    if course is None:
        raise NotFound("course not found")
    return course


def _enrollment_visible(
    access: Access, enrollment: Enrollment, departments: dict[str, frozenset[str]]
) -> bool:
    if not access.granted(Capability.ASSIGN):
        return False
    if access.covers_all_departments(Capability.ASSIGN):
        return True
    if enrollment.assignment_id is None:
        return False
    assignment = enrollment.assignment
    return assignment is not None and visible(access, assignment, departments)


def roster(
    access: Access,
    course: Course,
    *,
    status: str | None = None,
    overdue: bool | None = None,
    department_ref: str | None = None,
) -> list[Enrollment]:
    """Enrollments of one course the caller may see (``manage/courses/{id}/enrollments/``)."""
    from django.utils import timezone

    organization_id = access.principal.organization_id
    rows = list(
        Enrollment.objects.for_org(organization_id)
        .select_related("assignment")
        .filter(course=course)
        .order_by("user_ref")
    )
    if status:
        rows = [row for row in rows if row.status == status]
    if overdue is not None:
        now = timezone.now()
        rows = [
            row
            for row in rows
            if (
                row.status == Enrollment.Status.ACTIVE
                and row.due_at is not None
                and row.due_at < now
            )
            == overdue
        ]
    member_refs = [str(row.user_ref) for row in rows]
    departments = _member_departments(organization_id, member_refs) if member_refs else {}
    if department_ref:
        rows = [
            row for row in rows if department_ref in departments.get(str(row.user_ref), frozenset())
        ]
    return [row for row in rows if _enrollment_visible(access, row, departments)]


def require_managed_enrollment(
    access: Access, organization_id: UUID, enrollment_id: UUID
) -> Enrollment:
    row = (
        Enrollment.objects.for_org(organization_id)
        .select_related("assignment", "course")
        .filter(pk=enrollment_id)
        .first()
    )
    if row is None:
        raise NotFound("enrollment not found")
    departments = _departments_for(
        access, [row.assignment] if row.assignment else [], organization_id
    )
    if not _enrollment_visible(access, row, departments):
        raise NotFound("enrollment not found")
    return row


# --- learner reads ----------------------------------------------------------


def require_own_enrollment(access: Access, enrollment_id: UUID) -> Enrollment:
    row = (
        Enrollment.objects.for_org(access.principal.organization_id)
        .select_related("course", "course_version")
        .filter(pk=enrollment_id, user_ref=access.principal.user_ref)
        .first()
    )
    if row is None:
        raise NotFound("enrollment not found")
    return row


def my_enrollments(access: Access, *, status: str | None = None) -> list[Enrollment]:
    rows = Enrollment.objects.for_org(access.principal.organization_id).filter(
        user_ref=access.principal.user_ref
    )
    if status:
        rows = rows.filter(status=status)
    return list(rows.select_related("course", "course_version").order_by("-created_at"))


def progress_percent(enrollment: Enrollment) -> int:
    ordered = gating.ordered_lessons(enrollment)
    return gating.progress_percent(ordered, gating.completed_lesson_ids(enrollment))


def enrollment_payload(enrollment: Enrollment, *, with_outline: bool = False) -> dict[str, Any]:
    """The learner-facing shape of one enrollment (``docs/api.md`` §3)."""
    version = enrollment.course_version
    payload: dict[str, Any] = {
        "id": str(enrollment.pk),
        "course_id": str(enrollment.course_id),
        "course_title": enrollment.course.title,
        "course_version_id": str(enrollment.course_version_id),
        "version_number": version.version_number,
        "status": enrollment.status,
        "user_ref": enrollment.user_ref,
        "due_at": enrollment.due_at.isoformat() if enrollment.due_at else None,
        "mandatory": enrollment.mandatory,
        "acknowledgment_required": version.acknowledgment_required,
        "acknowledged": enrollment.acknowledged_at is not None,
        "completed_at": (enrollment.completed_at.isoformat() if enrollment.completed_at else None),
        "cancelled_at": enrollment.cancelled_at.isoformat() if enrollment.cancelled_at else None,
        "cancel_reason": enrollment.cancel_reason,
        "progress_percent": progress_percent(enrollment),
        "created_at": enrollment.created_at.isoformat(),
    }
    if with_outline:
        payload["sections"] = gating.outline(enrollment)
    return payload


__all__ = [
    "ASSIGNMENT_STATUSES",
    "enrollment_payload",
    "list_assignments",
    "my_enrollments",
    "progress_percent",
    "require_assignment",
    "require_course",
    "require_managed_enrollment",
    "require_own_enrollment",
    "roster",
    "visible",
    "visible_assignments",
]
