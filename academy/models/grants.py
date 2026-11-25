"""Academy-local permission grants — ``docs/domain-model.md`` §2.14 (D-027).

A grant is the only source of management authority in H1's ``grants_only`` mode, and it adds to
the role defaults in ``role_plus_grants``. Revocation is a state change, never a delete, so the
audit trail and a later suspension (D-028) keep pointing at the same rows.
"""

from __future__ import annotations

from django.db import models

from academy.models.base import TenantManager, TenantModel


class PermissionGrant(TenantModel):
    """One capability for one user, scoped to the organization or a department."""

    class Capability(models.TextChoices):
        LEARN = "learn", "Learn"
        MANAGE_CONTENT = "manage_content", "Manage content"
        ASSIGN = "assign", "Assign"
        VIEW_REPORTS = "view_reports", "View reports"
        ADMIN = "admin", "Admin"

    class Scope(models.TextChoices):
        ORGANIZATION = "organization", "Organization"
        DEPARTMENT = "department", "Department"

    user_ref = models.CharField(max_length=64)
    capability = models.CharField(max_length=24, choices=Capability.choices)
    scope_type = models.CharField(max_length=16, choices=Scope.choices)
    scope_ref = models.CharField(max_length=64, blank=True, default="")
    granted_by_ref = models.CharField(max_length=64)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by_ref = models.CharField(max_length=64, blank=True, default="")
    objects: TenantManager[PermissionGrant] = TenantManager()  # type: ignore[assignment]

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(scope_type="organization", scope_ref="")
                    | models.Q(scope_type="department") & ~models.Q(scope_ref="")
                ),
                name="grant_scope_shape",
            ),
            models.UniqueConstraint(
                fields=["organization_id", "user_ref", "capability", "scope_type", "scope_ref"],
                condition=models.Q(revoked_at__isnull=True),
                name="grant_one_live_per_scope",
            ),
            models.CheckConstraint(
                condition=models.Q(revoked_at__isnull=True) | ~models.Q(revoked_by_ref=""),
                name="grant_revocation_names_its_actor",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization_id", "user_ref", "revoked_at"],
                name="grant_org_user_live",
            ),
            models.Index(
                fields=["organization_id", "capability", "revoked_at"],
                name="grant_org_capability_live",
            ),
        ]

    def __str__(self) -> str:
        scope = self.scope_ref or "organization"
        return f"{self.user_ref}: {self.capability} @ {scope}"
