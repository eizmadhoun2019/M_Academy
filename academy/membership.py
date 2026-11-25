"""Membership hooks Academy owes the Hub contract — ``docs/hub-contract.md`` §4.

``member_deactivated`` calls :func:`member_deactivated` inside the webhook transaction so the
cancellation and the receipt commit together. T-019 owns the enrollment expansion and the
cancellation itself; until then the hook records the intent without inventing a side effect.
"""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger("academy.membership")


def member_deactivated(organization_id: UUID, user_ref: str) -> None:
    """The transactional cancellation hook for one deactivated membership."""
    logger.info(
        "membership deactivated; enrollment cancellation is owned by T-019",
        extra={"organization_id": str(organization_id), "user_ref": user_ref},
    )
