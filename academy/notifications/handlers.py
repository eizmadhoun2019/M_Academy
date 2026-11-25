"""Event subscriptions — N-1, N-2 and N-3 of ``docs/notifications.md`` §2.

Handlers only queue rows (ADR-007); the send is a task, so a slow or failing transport never
makes the enrollment that triggered it slow or failing. Each handler is idempotent through the
queue's dedupe key, which is why a replayed event costs one lookup and no second email.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from academy.events.handlers import subscribe, unsubscribe
from academy.events.types import DomainEvent
from academy.models import NotificationLog
from academy.notifications import service

logger = logging.getLogger("academy.notifications")

ENROLLMENT_CREATED = "enrollment.created"
ENROLLMENT_COMPLETED = "enrollment.completed"

_SUBSCRIBED = False


def _uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def on_enrollment_created(event: DomainEvent) -> None:
    """N-1 — an assignment expansion created an active enrollment, so tell the learner."""
    payload = event.payload
    assignment_id = _uuid(payload.get("assignment_id"))
    user_ref = str(payload.get("user_ref") or "")
    if assignment_id is None or not user_ref:
        # A manual enrollment has no assignment and no assignment message; nothing to send.
        return
    service.queue(
        NotificationLog.Kind.COURSE_ASSIGNED,
        organization_id=event.organization_id,
        dedupe_key=f"assigned:{assignment_id}:{user_ref}",
        recipient_ref=user_ref,
    )


def on_enrollment_completed(event: DomainEvent) -> None:
    """N-2 to the learner (email + in-app) and N-3 to their managers (in-app)."""
    payload = event.payload
    enrollment_id = _uuid(payload.get("enrollment_id"))
    if enrollment_id is None:
        return
    row = service.enrollment(event.organization_id, enrollment_id)
    if row is None:
        return
    service.queue(
        NotificationLog.Kind.COURSE_COMPLETED,
        organization_id=event.organization_id,
        dedupe_key=f"completed:{enrollment_id}",
        recipient_ref=row.user_ref,
    )
    for manager_ref in service.managers_for(row):
        service.queue(
            NotificationLog.Kind.LEARNER_COMPLETED,
            organization_id=event.organization_id,
            dedupe_key=f"learner_completed:{enrollment_id}:{manager_ref}",
            recipient_ref=manager_ref,
            channels=(NotificationLog.Channel.IN_APP,),
        )


def subscribe_all() -> None:
    """Connect the handlers once per process; ``AppConfig.ready`` calls this."""
    global _SUBSCRIBED
    if _SUBSCRIBED:
        return
    subscribe(ENROLLMENT_CREATED, on_enrollment_created)
    subscribe(ENROLLMENT_COMPLETED, on_enrollment_completed)
    _SUBSCRIBED = True


def unsubscribe_all() -> None:
    """Disconnect the handlers; tests call this so the package leaves no state behind."""
    global _SUBSCRIBED
    unsubscribe(ENROLLMENT_CREATED, on_enrollment_created)
    unsubscribe(ENROLLMENT_COMPLETED, on_enrollment_completed)
    _SUBSCRIBED = False


__all__ = [
    "ENROLLMENT_COMPLETED",
    "ENROLLMENT_CREATED",
    "on_enrollment_completed",
    "on_enrollment_created",
    "subscribe_all",
    "unsubscribe_all",
]
