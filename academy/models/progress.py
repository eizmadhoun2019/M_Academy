"""Assignment, enrollment and progress — ``docs/domain-model.md`` §2.6–§2.9.

The database carries every invariant this file can express: one active enrollment per learner
per course, one active assignment per target, one progress row per lesson, and non-negative
watched numbers. ``CompletionRecord`` is immutable through a trigger created in the migration,
not through a service promise.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import F, Q, Value
from django.db.models.functions import Coalesce

from academy.models.base import TenantManager, TenantModel
from academy.models.catalog import Course, CourseVersion, Lesson


class Assignment(TenantModel):
    """One target, one course (§2.6)."""

    class TargetType(models.TextChoices):
        USER = "user", "User"
        DEPARTMENT = "department", "Department"
        ROLE = "role", "Role"
        ORGANIZATION = "organization", "Organization"

    course = models.ForeignKey(Course, on_delete=models.RESTRICT, related_name="assignments")
    target_type = models.CharField(max_length=16, choices=TargetType.choices)
    # D-015: NULL is meaningful only for the organization target.
    target_ref = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001 - NULL is semantic here: the checks tell NULL from ''
    due_at = models.DateTimeField(null=True, blank=True)
    mandatory = models.BooleanField(default=True)
    assigned_by_ref = models.CharField(max_length=64)
    note = models.CharField(max_length=500, null=True, blank=True)  # noqa: DJ001 - NULL is semantic here: the checks tell NULL from ''
    cancelled_at = models.DateTimeField(null=True, blank=True)
    objects: TenantManager[Assignment] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(target_type__in=["user", "department", "role", "organization"]),
                name="assignment_target_type_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(target_type="organization", target_ref__isnull=True)
                    | (~Q(target_type="organization") & Q(target_ref__isnull=False))
                ),
                name="assignment_target_ref_matches_type",
            ),
            models.UniqueConstraint(
                "organization_id",
                "course",
                "target_type",
                Coalesce("target_ref", Value("")),
                condition=Q(cancelled_at__isnull=True),
                name="assignment_active_target_unique",
            ),
            models.CheckConstraint(
                condition=Q(cancelled_at__isnull=True) | Q(cancelled_at__gte=F("created_at")),
                name="assignment_cancelled_after_creation",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.course} → {self.target_type}:{self.target_ref or '*'}"


class Enrollment(TenantModel):
    """A learner pinned to one published version (§2.7)."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class CancelReason(models.TextChoices):
        UNASSIGNED = "unassigned", "Unassigned"
        DEACTIVATED = "deactivated", "Deactivated"
        REMOVED_FROM_TARGET = "removed_from_target", "Removed from target"

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.RESTRICT,
        related_name="enrollments",
        null=True,
        blank=True,
    )
    course = models.ForeignKey(Course, on_delete=models.RESTRICT, related_name="enrollments")
    course_version = models.ForeignKey(
        CourseVersion, on_delete=models.RESTRICT, related_name="enrollments"
    )
    user_ref = models.CharField(max_length=64)
    due_at = models.DateTimeField(null=True, blank=True)
    mandatory = models.BooleanField(default=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(  # noqa: DJ001 - NULL is semantic: only a cancelled row has one
        max_length=40, choices=CancelReason.choices, null=True, blank=True
    )
    objects: TenantManager[Enrollment] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization_id", "user_ref", "course"],
                condition=Q(status="active"),
                name="enrollment_one_active_per_course",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["active", "completed", "cancelled"]),
                name="enrollment_status_valid",
            ),
            models.CheckConstraint(
                condition=~Q(status="completed") | Q(completed_at__isnull=False),
                name="enrollment_completed_is_stamped",
            ),
            models.CheckConstraint(
                condition=~Q(status="cancelled") | Q(cancelled_at__isnull=False),
                name="enrollment_cancelled_is_stamped",
            ),
            models.CheckConstraint(
                condition=Q(cancel_reason__isnull=True)
                | Q(cancel_reason__in=["unassigned", "deactivated", "removed_from_target"]),
                name="enrollment_cancel_reason_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization_id", "user_ref", "status"], name="enrollment_org_user"
            ),
            models.Index(
                fields=["organization_id", "course", "status"], name="enrollment_org_course"
            ),
            models.Index(
                fields=["organization_id", "due_at"],
                name="enrollment_org_due",
                condition=Q(status="active", due_at__isnull=False),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_ref} · {self.course}"


class LessonProgress(TenantModel):
    """Watched coverage for one lesson of one enrollment (§2.8, ADR-013)."""

    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, related_name="lesson_progress"
    )
    lesson = models.ForeignKey(Lesson, on_delete=models.RESTRICT, related_name="progress")
    watched_ranges = models.JSONField(default=list)
    watched_seconds = models.DecimalField(max_digits=10, decimal_places=1, default=Decimal("0"))
    position_seconds = models.DecimalField(max_digits=10, decimal_places=1, default=Decimal("0"))
    frontier_seconds = models.DecimalField(max_digits=10, decimal_places=1, default=Decimal("0"))
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    skip_attempts = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    objects: TenantManager[LessonProgress] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "lesson"], name="progress_one_row_per_lesson"
            ),
            models.CheckConstraint(
                condition=Q(watched_seconds__gte=0), name="progress_watched_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(position_seconds__gte=0), name="progress_position_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(frontier_seconds__gte=0), name="progress_frontier_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(frontier_seconds__lte=F("position_seconds")),
                name="progress_frontier_within_position",
            ),
        ]
        indexes = [
            models.Index(fields=["organization_id", "enrollment"], name="progress_org_enrollment"),
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.lesson}"


class CompletionRecord(TenantModel):
    """Immutable proof of completion (§2.9)."""

    class Method(models.TextChoices):
        LESSONS = "lessons", "Lessons"
        ADMIN_OVERRIDE = "admin_override", "Admin override"

    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.RESTRICT, related_name="completion_records"
    )
    # Snapshot columns: reporting must not depend on a later version or course edit.
    course_id = models.UUIDField()
    course_version_id = models.UUIDField()
    user_ref = models.CharField(max_length=64)
    completed_at = models.DateTimeField()
    method = models.CharField(max_length=16, choices=Method.choices, default=Method.LESSONS)
    actor_ref = models.CharField(max_length=64)
    objects: TenantManager[CompletionRecord] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["enrollment"], name="completion_one_per_enrollment"),
            models.CheckConstraint(
                condition=Q(method__in=["lessons", "admin_override"]),
                name="completion_method_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"completion {self.enrollment}"
