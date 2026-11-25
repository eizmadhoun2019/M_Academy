"""Read side of ``AccessSuspension`` (``docs/domain-model.md`` §2.15)."""

from __future__ import annotations

from uuid import UUID

from academy.models import AccessSuspension


def is_suspended(organization_id: UUID, user_ref: str) -> bool:
    """True while an un-lifted suspension exists for this user."""
    return AccessSuspension.objects.filter(
        organization_id=organization_id,
        user_ref=user_ref,
        lifted_at__isnull=True,
    ).exists()
