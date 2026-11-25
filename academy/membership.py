"""Membership hooks Academy owes the Hub contract — ``docs/hub-contract.md`` §4.

``member_deactivated`` and the expansion half of ``member_changed`` are T-019. Both run inside
the webhook transaction, next to the receipt: a rolled-back delivery leaves no enrollment
change behind, and a redelivery is deduplicated by the receipt before it reaches here.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from uuid import UUID

from academy.assignments import service

logger = logging.getLogger("academy.membership")


def member_changed(
    organization_id: UUID,
    user_ref: str,
    *,
    department_refs: Sequence[str] = (),
    role: str | None = None,
    is_active: bool = True,
) -> dict[str, int]:
    """Auto-enrol a changed member and drop the enrollments they left (REQ-08, D-015)."""
    result = service.sync_member(
        organization_id,
        user_ref,
        department_refs=department_refs,
        role=role,
        is_active=is_active,
    )
    logger.info(
        "membership changed",
        extra={
            "organization_id": str(organization_id),
            "user_ref": user_ref,
            "enrolled": result.get("enrolled", 0),
            "cancelled": result.get("cancelled", 0),
        },
    )
    return result


def member_deactivated(organization_id: UUID, user_ref: str) -> int:
    """The transactional cancellation hook for one deactivated membership."""
    cancelled = service.cancel_for_deactivation(organization_id, user_ref)
    logger.info(
        "membership deactivated",
        extra={
            "organization_id": str(organization_id),
            "user_ref": user_ref,
            "cancelled": cancelled,
        },
    )
    return cancelled


__all__ = ["member_changed", "member_deactivated"]
