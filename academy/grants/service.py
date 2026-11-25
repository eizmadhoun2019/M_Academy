"""Grant and revoke services — ``docs/api.md`` §7 and ``docs/domain-model.md`` §2.14.

Every write here runs the last-admin guard and appends its audit row inside the caller's
transaction, so an authority change and its evidence commit together or not at all.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from django.utils import timezone

from academy.audit import record
from academy.authorization.core import Capability, Grant
from academy.exceptions import Conflict, LastAdmin, NotFound
from academy.models import PermissionGrant


def _capability(value: str) -> Capability:
    """Accept ``academy.admin`` or the stored short ``admin``."""
    return Capability(value if value.startswith("academy.") else f"academy.{value}")


def grants_for(organization_id: UUID, user_ref: str, *, now: datetime | None = None) -> list[Grant]:
    """Every live grant of one user, mapped to the authorization layer's ``Grant``."""
    moment = now or timezone.now()
    rows = PermissionGrant.objects.for_org(organization_id).filter(
        user_ref=user_ref, revoked_at__isnull=True
    )
    grants: list[Grant] = []
    for row in rows:
        if row.expires_at is not None and row.expires_at <= moment:
            continue
        grants.append(
            Grant(
                capability=_capability(row.capability),
                scope_type=row.scope_type,
                scope_ref=row.scope_ref or None,
                expires_at=row.expires_at,
                revoked_at=row.revoked_at,
            )
        )
    return grants


def _active_admin_rows(
    organization_id: UUID, *, exclude: UUID | None = None
) -> Sequence[PermissionGrant]:
    moment = timezone.now()
    rows = PermissionGrant.objects.for_org(organization_id).filter(
        capability=PermissionGrant.Capability.ADMIN,
        revoked_at__isnull=True,
    )
    live = [row for row in rows if row.expires_at is None or row.expires_at > moment]
    return [row for row in live if exclude is None or row.pk != exclude]


def grant(
    *,
    organization_id: UUID,
    actor_ref: str,
    user_ref: str,
    capability: str,
    scope_type: str,
    scope_ref: str | None = None,
    expires_at: datetime | None = None,
) -> PermissionGrant:
    """Create one live grant; a duplicate live grant is a conflict (409)."""
    capability_value = _capability(capability).value.split(".")[-1]
    scope_value = (scope_ref or "").strip()
    if scope_type == PermissionGrant.Scope.DEPARTMENT and not scope_value:
        raise Conflict("a department grant needs a department reference")
    if scope_type == PermissionGrant.Scope.ORGANIZATION and scope_value:
        raise Conflict("an organization grant cannot carry a department reference")
    duplicate = PermissionGrant.objects.for_org(organization_id).filter(
        user_ref=user_ref,
        capability=capability_value,
        scope_type=scope_type,
        scope_ref=scope_value,
        revoked_at__isnull=True,
    )
    if duplicate.exists():
        raise Conflict("this user already holds that capability in that scope")

    row = PermissionGrant.objects.create(
        organization_id=organization_id,
        user_ref=user_ref,
        capability=capability_value,
        scope_type=scope_type,
        scope_ref=scope_value,
        granted_by_ref=actor_ref,
        expires_at=expires_at,
    )
    record(
        organization_id=organization_id,
        actor_ref=actor_ref,
        action="grant.created",
        object_type="PermissionGrant",
        object_id=str(row.pk),
        metadata={
            "user_ref": user_ref,
            "capability": capability_value,
            "scope_type": scope_type,
            "scope_ref": scope_value or None,
        },
    )
    return row


def revoke(
    *, organization_id: UUID, actor_ref: str, grant_id: UUID, now: datetime | None = None
) -> PermissionGrant:
    """Revoke one grant, refusing to remove the organization's last active admin (409)."""
    row = PermissionGrant.objects.for_org(organization_id).filter(pk=grant_id).first()
    if row is None:
        raise NotFound("grant not found")
    if row.revoked_at is not None:
        return row
    if row.capability == PermissionGrant.Capability.ADMIN and not _active_admin_rows(
        organization_id, exclude=row.pk
    ):
        raise LastAdmin("the last active academy.admin grant cannot be revoked")
    row.revoked_at = now or timezone.now()
    row.revoked_by_ref = actor_ref
    row.save(update_fields=["revoked_at", "revoked_by_ref", "updated_at"])
    record(
        organization_id=organization_id,
        actor_ref=actor_ref,
        action="grant.revoked",
        object_type="PermissionGrant",
        object_id=str(row.pk),
        metadata={
            "user_ref": row.user_ref,
            "capability": row.capability,
            "scope_type": row.scope_type,
            "scope_ref": row.scope_ref,
        },
    )
    return row
