"""Celery entry points — the names, queues and limits of ``docs/background-jobs.md`` §1.

Every task is a thin wrapper: the work lives in :mod:`academy.notifications.service` and
:mod:`academy.notifications.reminders`, where the idempotency keys sit next to the inserts.
Retries are bounded — three attempts, five then fifteen minutes apart — because a message that
still cannot leave is better reported by the sweeper than retried forever.

``academy.escalations.digest`` takes either one batch (organisation, manager, due date) or, with
no arguments, every batch the table says is missing its digest. The beat entry uses the second
form, so a reminder run that crashed between recording an escalation and queueing its digest is
repaired by the same morning's second task.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any
from uuid import UUID

from celery import shared_task

from academy.notifications import reminders, service

logger = logging.getLogger("academy.notifications")

#: Seconds before the second and third attempt (§1: 3 attempts in total).
RETRY_DELAYS = (300, 900)


@shared_task(
    bind=True,
    name="academy.notifications.send",
    soft_time_limit=60,
    time_limit=90,
    max_retries=len(RETRY_DELAYS),
)
def send_notification(self: Any, log_id: str, organization_id: str) -> str:
    """Render and deliver one queued row; returns the resulting status."""
    try:
        return service.deliver_by_id(UUID(log_id), UUID(organization_id))
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            logger.warning(
                "notification send exhausted its attempts",
                extra={"log_id": log_id, "organization_id": organization_id},
            )
            raise
        countdown = RETRY_DELAYS[min(self.request.retries, len(RETRY_DELAYS) - 1)]
        raise self.retry(exc=exc, countdown=countdown) from exc


@shared_task(
    name="academy.notifications.sweep",
    soft_time_limit=300,
    time_limit=330,
)
def sweep() -> int:
    """Re-enqueue pending or failed rows under the attempt cap; returns how many."""
    rows = service.pending()
    for row in rows:
        send_notification.delay(str(row.pk), str(row.organization_id))
    return len(rows)


@shared_task(
    name="academy.reminders.evaluate",
    soft_time_limit=1800,
    time_limit=1860,
)
def evaluate_reminders() -> dict[str, int]:
    """The daily sweep: the three learner anchors plus the escalation set."""
    return reminders.evaluate()


@shared_task(
    bind=True,
    name="academy.escalations.digest",
    soft_time_limit=1800,
    time_limit=1860,
    max_retries=1,
)
def send_escalation_digest(
    self: Any,
    organization_id: str | None = None,
    manager_ref: str | None = None,
    due_date: str | None = None,
) -> int:
    """Send one batch, or every batch still owed a digest; returns how many were sent."""
    try:
        if organization_id and manager_ref and due_date:
            reminders.send_digest(UUID(organization_id), manager_ref, date.fromisoformat(due_date))
            return 1
        sent = 0
        for organization, manager, due in reminders.pending_digests():
            reminders.send_digest(organization, manager, due)
            sent += 1
        return sent
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            raise
        raise self.retry(exc=exc, countdown=300) from exc


__all__ = [
    "RETRY_DELAYS",
    "evaluate_reminders",
    "send_escalation_digest",
    "send_notification",
    "sweep",
]
