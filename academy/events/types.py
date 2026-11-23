"""The event envelope.

One frozen value object carries everything a handler may need, so a handler never reads the
model that produced it: the row may be gone, changed or rolled back by the time the event is
delivered. The payload is JSON-serializable because it is also the shape handed to Celery.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

#: ``area.action``: lowercase words joined by one dot, e.g. ``media.ready``.
_EVENT_NAME = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


def _json_safe(payload: dict[str, Any]) -> bool:
    try:
        json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return True


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """A fact that has been committed and can be delivered."""

    name: str
    organization_id: UUID
    actor_ref: str = "system"
    payload: Mapping[str, Any] = field(default_factory=dict)
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not _EVENT_NAME.match(self.name):
            raise ValueError(f"event name {self.name!r} must look like 'area.action'")
        if not isinstance(self.organization_id, UUID):
            raise ValueError("organization_id must be a UUID")
        if not isinstance(self.actor_ref, str) or not self.actor_ref.strip():
            raise ValueError("actor_ref must be a non-empty string")
        if len(self.actor_ref) > 64:
            raise ValueError("actor_ref must be at most 64 characters")
        if not isinstance(self.event_id, UUID):
            raise ValueError("event_id must be a UUID")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware (storage and logs are UTC)")

        payload = dict(self.payload)
        if not _json_safe(payload):
            raise ValueError("payload must be JSON-serializable (it is also a Celery argument)")
        object.__setattr__(self, "payload", MappingProxyType(payload))

    def as_dict(self) -> dict[str, Any]:
        """A plain, JSON-serializable representation (Celery arguments, log lines)."""
        return {
            "event_id": str(self.event_id),
            "name": self.name,
            "organization_id": str(self.organization_id),
            "actor_ref": self.actor_ref,
            "occurred_at": self.occurred_at.isoformat(),
            "payload": dict(self.payload),
        }
