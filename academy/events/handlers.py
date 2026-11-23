"""Who receives what: subscriptions and the single dispatch receiver.

A handler is a plain callable ``(event) -> None``. Handlers enqueue Celery tasks or touch
related rows; they never do the heavy work themselves (ADR-007). One failing handler is logged
and does not stop the others: the event describes a committed fact, and a broken listener must
not turn a successful write into an error the caller sees.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from academy.events.signals import domain_event
from academy.events.types import DomainEvent

logger = logging.getLogger("academy.events")

Handler = Callable[[DomainEvent], None]

_HANDLERS: dict[str, list[Handler]] = {}


def subscribe(name: str, handler: Handler) -> None:
    """Call ``handler`` for every event named ``name``, in subscription order."""
    if not callable(handler):
        raise TypeError("handler must be callable")
    _HANDLERS.setdefault(name, []).append(handler)


def unsubscribe(name: str, handler: Handler) -> None:
    """Remove one subscription; a name with no handlers left is dropped."""
    handlers = _HANDLERS.get(name)
    if handlers is None:
        return
    if handler in handlers:
        handlers.remove(handler)
    if not handlers:
        _HANDLERS.pop(name, None)


def handlers_for(name: str) -> tuple[Handler, ...]:
    """The handlers currently subscribed to ``name``."""
    return tuple(_HANDLERS.get(name, ()))


def clear_handlers() -> None:
    """Drop every subscription; tests and process-level reconfiguration call this."""
    _HANDLERS.clear()


def dispatch(event: DomainEvent) -> None:
    """Deliver ``event`` to its subscribers, isolating one failure from the rest."""
    for handler in handlers_for(event.name):
        try:
            handler(event)
        except Exception:
            logger.exception(
                "domain event handler failed",
                extra={"event": event.name, "event_id": str(event.event_id)},
            )


def _receive(sender: Any, *, event: DomainEvent, **kwargs: Any) -> None:
    dispatch(event)


# ``weak=False`` keeps this module-level receiver alive for the process lifetime; it is the only
# connection the package makes.
domain_event.connect(_receive, dispatch_uid="academy.events.dispatch", weak=False)


__all__ = ["Handler", "clear_handlers", "dispatch", "handlers_for", "subscribe", "unsubscribe"]
