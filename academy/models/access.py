"""Academy-local access records — ``docs/domain-model.md`` §2.15 (D-028).

A suspension removes every effective capability without deleting the stored grants and
without touching Hub membership. Reading it is enough for this task; the audited suspend and
lift commands arrive with the permission administration in T-016.
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from academy.models.base import TenantManager, TenantModel


class AccessSuspension(TenantModel):
    """One active suspension per user; lifting keeps the row for the audit trail."""

    user_ref = models.CharField(max_length=64)
    reason = models.CharField(max_length=500)
    suspended_at = models.DateTimeField(default=timezone.now)
    suspended_by_ref = models.CharField(max_length=64)
    lifted_at = models.DateTimeField(null=True, blank=True)
    lifted_by_ref = models.CharField(max_length=64, null=True, blank=True)
    objects: TenantManager[AccessSuspension] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization_id", "user_ref"],
                condition=models.Q(lifted_at__isnull=True),
                name="suspension_one_active_per_user",
            ),
            models.CheckConstraint(
                condition=models.Q(lifted_at__isnull=True) | models.Q(lifted_by_ref__isnull=False),
                name="suspension_lift_names_its_actor",
            ),
            models.CheckConstraint(
                condition=models.Q(reason__regex=r"\S"),
                name="suspension_reason_not_blank",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization_id", "user_ref", "lifted_at"],
                name="suspension_org_user_live",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_ref} ({'lifted' if self.lifted_at else 'suspended'})"
