"""Operational records — ``docs/domain-model.md`` §2.11–§2.13.

These tables are the idempotency and accountability layer: a reminder or notification row is
the proof that one side effect happened, and an audit row is the proof of one consequential
action. ``AuditEvent`` gets its append-only trigger with the audit service in T-012.
"""

from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone

from academy.models.base import TenantManager, TenantModel
from academy.models.progress import Enrollment


class ReminderLog(TenantModel):
    """One reminder actually sent for one enrollment (§2.11)."""

    class Kind(models.TextChoices):
        DUE_MINUS_3 = "due_minus_3", "Three days before due"
        DUE = "due", "Due day"
        DUE_PLUS_1 = "due_plus_1", "One day after due"
        MANAGER_ESCALATION = "manager_escalation", "Manager escalation"

    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, related_name="reminder_logs"
    )
    kind = models.CharField(max_length=24, choices=Kind.choices)
    recipient_ref = models.CharField(max_length=64)
    sent_at = models.DateTimeField(default=timezone.now)
    objects: TenantManager[ReminderLog] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "kind", "recipient_ref"],
                name="reminder_once_per_kind_recipient",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    kind__in=["due_minus_3", "due", "due_plus_1", "manager_escalation"]
                ),
                name="reminder_kind_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind} → {self.recipient_ref}"


class NotificationLog(TenantModel):
    """One outbound message and its delivery state (§2.12)."""

    class Kind(models.TextChoices):
        COURSE_ASSIGNED = "course_assigned", "Course assigned"
        COURSE_COMPLETED = "course_completed", "Course completed"
        LEARNER_COMPLETED = "learner_completed", "Learner completed"
        MANAGER_ESCALATION = "manager_escalation", "Manager escalation"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        IN_APP = "in_app", "In-app"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    kind = models.CharField(max_length=32, choices=Kind.choices)
    dedupe_key = models.CharField(max_length=128)
    recipient_ref = models.CharField(max_length=64)
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.EMAIL)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    error_code = models.CharField(max_length=40, null=True, blank=True)  # noqa: DJ001 - NULL is semantic: only a failed send has a code
    sent_at = models.DateTimeField(null=True, blank=True)
    objects: TenantManager[NotificationLog] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization_id", "dedupe_key", "channel"],
                name="notification_once_per_dedupe_channel",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    kind__in=[
                        "course_assigned",
                        "course_completed",
                        "learner_completed",
                        "manager_escalation",
                    ]
                ),
                name="notification_kind_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(channel__in=["email", "in_app"]),
                name="notification_channel_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["pending", "sent", "failed", "skipped"]),
                name="notification_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(status="sent") | models.Q(sent_at__isnull=False),
                name="notification_sent_is_stamped",
            ),
        ]
        indexes = [
            models.Index(fields=["organization_id", "status"], name="notification_org_status"),
        ]

    def __str__(self) -> str:
        return f"{self.kind} → {self.recipient_ref} ({self.status})"


class AuditEvent(TenantModel):
    """Append-only record of one consequential action (§2.13, ADR-009)."""

    event_id = models.UUIDField(default=uuid.uuid4, editable=False)
    actor_ref = models.CharField(max_length=64)
    action = models.CharField(max_length=64)
    object_type = models.CharField(max_length=32)
    object_id = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(default=timezone.now)
    objects: TenantManager[AuditEvent] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization_id", "event_id"], name="audit_event_unique"
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization_id", "object_type", "object_id"],
                name="audit_org_object",
            ),
            models.Index(fields=["organization_id", "occurred_at"], name="audit_org_occurred"),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.object_type}:{self.object_id}"
