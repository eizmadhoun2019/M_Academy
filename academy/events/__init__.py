"""Domain events — the write path's own vocabulary (ADR-007, REQ-04).

.. code-block:: python

    from academy.events import emit_on_commit

    with transaction.atomic():
        enrollment.save()
        emit_on_commit(
            "enrollment.completed",
            organization_id=organization_id,
            actor_ref=user_ref,
            payload={"enrollment_id": str(enrollment.id)},
        )

The event is dispatched only after the surrounding transaction commits, so a handler can never
observe — or notify anyone about — a write that then rolls back. Handlers ``subscribe`` to a
name and are called with the frozen :class:`DomainEvent`; a handler that fails is logged and the
remaining handlers still run, because the event describes a committed fact that cannot be
undone by a broken listener.

Task-enqueueing handlers land with the tasks they enqueue (T-018 media, T-021 notifications);
this package owns the emitter and the dispatch, not the catalogue of business events.
"""

from __future__ import annotations

from academy.events.handlers import (
    clear_handlers,
    dispatch,
    handlers_for,
    subscribe,
    unsubscribe,
)
from academy.events.signals import domain_event, emit_on_commit
from academy.events.types import DomainEvent

__all__ = [
    "DomainEvent",
    "clear_handlers",
    "dispatch",
    "domain_event",
    "emit_on_commit",
    "handlers_for",
    "subscribe",
    "unsubscribe",
]
