"""The emitter: a Django signal fired through ``transaction.on_commit``.

Nothing here knows what listens. A service calls :func:`emit_on_commit`, the signal fires once
the transaction has committed, and ``academy.events.handlers`` decides who receives it.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from functools import partial
from typing import Any
from uuid import UUID

from django.db import transaction
from django.dispatch import Signal

from academy.events.types import DomainEvent

#: Sent once per committed event with the ``event`` keyword argument.
domain_event: Signal = Signal()


def emit_on_commit(
    name: str,
    *,
    organization_id: UUID,
    actor_ref: str = "system",
    payload: Mapping[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> DomainEvent:
    """Register ``event`` to be dispatched when the current transaction commits.

    Inside an atomic block the event waits for the outermost commit; outside one there is
    nothing to wait for, so Django runs the callback straight away. A rolled-back transaction
    dispatches nothing.
    """
    extra: dict[str, Any] = {}
    if occurred_at is not None:
        extra["occurred_at"] = occurred_at
    event = DomainEvent(
        name=name,
        organization_id=organization_id,
        actor_ref=actor_ref,
        payload=payload or {},
        **extra,
    )
    transaction.on_commit(partial(_publish, event))
    return event


def _publish(event: DomainEvent) -> None:
    domain_event.send(sender=DomainEvent, event=event)


__all__ = ["domain_event", "emit_on_commit"]
