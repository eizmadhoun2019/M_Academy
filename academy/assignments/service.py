"""Assignment and enrolment writes — ``docs/api.md`` §5, ``docs/domain-model.md`` §2.6–§2.7.

One target, one course, one transaction: the assignment row, the enrollments it expands to,
the audit row and the committed event all land together or not at all. The expansion always
goes through :func:`academy.assignments.expansion.expand_target`, so the preview a manager
sees is the write that follows (D-017).

Auto-enrolment is the same primitive driven by a Hub webhook (``docs/hub-contract.md`` §4):
``member_changed`` enrols the member into every live assignment that now reaches them and
cancels enrollments whose assignment no longer does; ``member_deactivated`` cancels every
unfinished enrollment (D-028 — a later reactivation never revives a cancelled row).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from academy.assignments import expansion
from academy.assignments.expansion import expand_target
from academy.audit import record
from academy.authorization.core import Access, Capability
from academy.events.signals import emit_on_commit
from academy.exceptions import (
    DomainValidationError,
    Forbidden,
    NotFound,
    StateConflict,
    TargetEmpty,
)
from academy.models import Assignment, Course, CourseVersion, Enrollment

MAX_NOTE = 500


def published_version(organization_id: UUID, course: Course) -> CourseVersion | None:
    """The version an enrollment pins to; a course without one cannot be assigned."""
    return (
        CourseVersion.objects.for_org(organization_id)
        .filter(course=course, status=CourseVersion.Status.PUBLISHED)
        .first()
    )


def _audit(
    organization_id: UUID,
    actor_ref: str,
    action: str,
    object_type: str,
    object_id: Any,
    metadata: dict[str, Any] | None = None,
) -> None:
    record(
        organization_id=organization_id,
        actor_ref=actor_ref,
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        metadata=metadata,
    )


def require_target_scope(access: Access, target_type: str, target_ref: str | None) -> None:
    """Role and organization targets span the tenant; the rest must sit in the caller's scope."""
    if not access.granted(Capability.ASSIGN):
        raise Forbidden("missing capability academy.assign")
    if target_type in (Assignment.TargetType.ROLE, Assignment.TargetType.ORGANIZATION):
        access.require_organization_wide(Capability.ASSIGN)
        return
    if access.covers_all_departments(Capability.ASSIGN):
        return
    if target_type == Assignment.TargetType.DEPARTMENT:
        if not access.allows(Capability.ASSIGN, department_ref=target_ref):
            raise NotFound("target not found")
        return
    users = {
        user.user_ref: user
        for user in expansion.directory().users(access.principal.organization_id, [str(target_ref)])
    }
    member = users.get(str(target_ref))
    if member is None or not any(
        access.allows(Capability.ASSIGN, department_ref=ref) for ref in member.department_refs
    ):
        raise NotFound("target not found")


def validate_target(target_type: str, target_ref: str | None) -> tuple[str, str | None]:
    kind = str(target_type)
    if kind not in {item.value for item in Assignment.TargetType}:
        raise DomainValidationError(
            "unknown target_type",
            fields={"target_type": "must be user, department, role or organization"},
        )
    ref = (target_ref or "").strip() or None
    if kind == Assignment.TargetType.ORGANIZATION:
        if ref is not None:
            raise DomainValidationError(
                "an organization target carries no reference",
                fields={"target_ref": "must be empty for target_type=organization"},
            )
        return kind, None
    if ref is None:
        raise DomainValidationError(
            "target_ref is required",
            fields={"target_ref": f"required for target_type={kind}"},
        )
    return kind, ref


def _create_enrollment(
    assignment: Assignment,
    version: CourseVersion,
    user_ref: str,
    *,
    actor_ref: str,
) -> Enrollment | None:
    """Insert one active enrollment, or ``None`` when the learner already has one."""
    try:
        with transaction.atomic():
            return Enrollment.objects.create(
                organization_id=assignment.organization_id,
                assignment=assignment,
                course=assignment.course,
                course_version=version,
                user_ref=user_ref,
                due_at=assignment.due_at,
                mandatory=assignment.mandatory,
            )
    except IntegrityError:
        # The partial unique index already pins one active enrollment per learner and course.
        return None


def _enrolled_event(enrollment: Enrollment, *, actor_ref: str) -> None:
    emit_on_commit(
        "enrollment.created",
        organization_id=enrollment.organization_id,
        actor_ref=actor_ref,
        payload={
            "enrollment_id": str(enrollment.pk),
            "assignment_id": str(enrollment.assignment_id),
            "course_id": str(enrollment.course_id),
            "course_version_id": str(enrollment.course_version_id),
            "user_ref": enrollment.user_ref,
            "due_at": enrollment.due_at.isoformat() if enrollment.due_at else None,
        },
    )


def create_assignment(
    access: Access,
    *,
    course: Course,
    target_type: str,
    target_ref: str | None = None,
    due_at: datetime | None = None,
    mandatory: bool = True,
    note: str | None = None,
) -> Assignment:
    """Create the assignment and expand it to enrollments inside one transaction."""
    organization_id = access.principal.organization_id
    kind, ref = validate_target(target_type, target_ref)
    require_target_scope(access, kind, ref)
    if course.organization_id != organization_id:
        raise NotFound("course not found")
    if course.status == Course.Status.ARCHIVED:
        raise StateConflict("course_not_published", "an archived course cannot be assigned")
    version = published_version(organization_id, course)
    if version is None:
        raise StateConflict(
            "course_not_published", "a course needs a published version before it can be assigned"
        )
    if note is not None and len(note) > MAX_NOTE:
        raise DomainValidationError(
            "note is too long", fields={"note": f"at most {MAX_NOTE} characters"}
        )

    expansion = expand_target(organization_id, kind, ref)
    if not expansion.user_refs:
        raise TargetEmpty("the target reaches no active member")

    actor_ref = access.principal.user_ref
    with transaction.atomic():
        try:
            with transaction.atomic():
                assignment = Assignment.objects.create(
                    organization_id=organization_id,
                    course=course,
                    target_type=kind,
                    target_ref=ref,
                    due_at=due_at,
                    mandatory=mandatory,
                    assigned_by_ref=actor_ref,
                    note=note or None,
                )
        except IntegrityError:
            raise StateConflict(
                "conflict", "an active assignment already targets this course and group"
            ) from None
        existing = set(
            Enrollment.objects.for_org(organization_id)
            .filter(
                course=course,
                status=Enrollment.Status.ACTIVE,
                user_ref__in=list(expansion.user_refs),
            )
            .values_list("user_ref", flat=True)
        )
        Enrollment.objects.bulk_create(
            [
                Enrollment(
                    organization_id=organization_id,
                    assignment=assignment,
                    course=course,
                    course_version=version,
                    user_ref=user_ref,
                    due_at=due_at,
                    mandatory=mandatory,
                )
                for user_ref in expansion.user_refs
                if user_ref not in existing
            ]
        )
        _audit(
            organization_id,
            actor_ref,
            "assignment.created",
            "Assignment",
            assignment.pk,
            {
                "course_id": str(course.pk),
                "target_type": kind,
                "recipients": expansion.count,
                "capped": expansion.capped,
            },
        )
        # One event for the batch: a delivery of 5,000 enrollments must not mean 5,000 events.
        # The consumers read the durable rows of this assignment when they run.
        emit_on_commit(
            "assignment.created",
            organization_id=organization_id,
            actor_ref=actor_ref,
            payload={
                "assignment_id": str(assignment.pk),
                "course_id": str(course.pk),
                "target_type": kind,
                "recipients": expansion.count,
                "capped": expansion.capped,
            },
        )
    return assignment


def _cancel_rows(
    organization_id: UUID,
    rows: Iterable[Enrollment],
    *,
    reason: str,
    actor_ref: str,
) -> int:
    """Soft-cancel active enrollments; returns how many rows changed."""
    cancelled = 0
    now = timezone.now()
    for row in rows:
        row.status = Enrollment.Status.CANCELLED
        row.cancelled_at = now
        row.cancel_reason = reason
        row.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])
        cancelled += 1
    if cancelled:
        emit_on_commit(
            "enrollment.cancelled",
            organization_id=organization_id,
            actor_ref=actor_ref,
            payload={"reason": reason, "cancelled": cancelled},
        )
    return cancelled


def cancel_assignment(access: Access, assignment: Assignment) -> Assignment:
    """Soft-cancel an assignment and every active enrollment it created."""
    if assignment.cancelled_at is not None:
        return assignment
    organization_id = assignment.organization_id
    actor_ref = access.principal.user_ref
    with transaction.atomic():
        assignment.cancelled_at = timezone.now()
        assignment.save(update_fields=["cancelled_at", "updated_at"])
        rows = list(
            Enrollment.objects.for_org(organization_id).filter(
                assignment=assignment, status=Enrollment.Status.ACTIVE
            )
        )
        cancelled = _cancel_rows(
            organization_id,
            rows,
            reason=Enrollment.CancelReason.UNASSIGNED,
            actor_ref=actor_ref,
        )
        _audit(
            organization_id,
            actor_ref,
            "assignment.cancelled",
            "Assignment",
            assignment.pk,
            {"course_id": str(assignment.course_id), "cancelled_enrollments": cancelled},
        )
    return assignment


def cancel_enrollment(access: Access, enrollment: Enrollment) -> Enrollment:
    """Cancel one enrollment by hand (``removed_from_target``), audited in the transaction."""
    if enrollment.status == Enrollment.Status.CANCELLED:
        return enrollment
    if enrollment.status != Enrollment.Status.ACTIVE:
        raise StateConflict("conflict", "only an active enrollment can be cancelled")
    actor_ref = access.principal.user_ref
    with transaction.atomic():
        _cancel_rows(
            enrollment.organization_id,
            [enrollment],
            reason=Enrollment.CancelReason.REMOVED_FROM_TARGET,
            actor_ref=actor_ref,
        )
        _audit(
            enrollment.organization_id,
            actor_ref,
            "enrollment.cancelled",
            "Enrollment",
            enrollment.pk,
            {
                "course_id": str(enrollment.course_id),
                "cancel_reason": Enrollment.CancelReason.REMOVED_FROM_TARGET,
            },
        )
    return enrollment


# --- Hub membership hooks ---------------------------------------------------


def _matching_assignments(
    organization_id: UUID, user_ref: str, department_refs: Sequence[str], role: str | None
) -> list[Assignment]:
    scope = Q(target_type=Assignment.TargetType.ORGANIZATION)
    scope |= Q(target_type=Assignment.TargetType.USER, target_ref=user_ref)
    if department_refs:
        scope |= Q(target_type=Assignment.TargetType.DEPARTMENT, target_ref__in=department_refs)
    if role:
        scope |= Q(target_type=Assignment.TargetType.ROLE, target_ref=role)
    return list(
        Assignment.objects.for_org(organization_id)
        .filter(cancelled_at__isnull=True)
        .filter(scope)
        .select_related("course")
    )


def sync_member(
    organization_id: UUID,
    user_ref: str,
    *,
    department_refs: Sequence[str] = (),
    role: str | None = None,
    is_active: bool = True,
) -> dict[str, int]:
    """Apply one ``member_changed`` fact: enrol where the member is now reached, drop the rest."""
    if not is_active:
        return {"enrolled": 0, "cancelled": cancel_for_deactivation(organization_id, user_ref)}
    enrolled = 0
    cancelled = 0
    with transaction.atomic():
        assignments = _matching_assignments(organization_id, user_ref, department_refs, role)
        for assignment in assignments:
            version = published_version(organization_id, assignment.course)
            if version is None:
                continue
            row = _create_enrollment(assignment, version, user_ref, actor_ref="system")
            if row is not None:
                _enrolled_event(row, actor_ref="system")
                enrolled += 1

        stale = list(
            Enrollment.objects.for_org(organization_id)
            .filter(
                user_ref=user_ref,
                status=Enrollment.Status.ACTIVE,
                assignment__isnull=False,
            )
            .exclude(assignment_id__in=[assignment.pk for assignment in assignments])
        )
        if stale:
            cancelled = _cancel_rows(
                organization_id,
                stale,
                reason=Enrollment.CancelReason.REMOVED_FROM_TARGET,
                actor_ref="system",
            )
    return {"enrolled": enrolled, "cancelled": cancelled}


def cancel_for_deactivation(organization_id: UUID, user_ref: str) -> int:
    """Cancel every unfinished enrollment of a deactivated member (D-028)."""
    with transaction.atomic():
        rows = list(
            Enrollment.objects.for_org(organization_id).filter(
                user_ref=user_ref, status=Enrollment.Status.ACTIVE
            )
        )
        if not rows:
            return 0
        return _cancel_rows(
            organization_id, rows, reason=Enrollment.CancelReason.DEACTIVATED, actor_ref="system"
        )


__all__ = [
    "cancel_assignment",
    "cancel_enrollment",
    "cancel_for_deactivation",
    "create_assignment",
    "published_version",
    "require_target_scope",
    "sync_member",
    "validate_target",
]
