"""Notification seam — mail and activity delivery (``docs/hub-contract.md`` §3).

A message names an opaque ``recipient_ref``, never a name or an address: the transport resolves
the reference in the organization and passes the address straight through
(``docs/notifications.md`` §1). Delivery is idempotent per key — resending the same key with the
same content is a duplicate, reusing it for different content is a conflict, exactly as the Hub
contract requires.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

#: Channels ``docs/notifications.md`` §1 defines.
CHANNELS = ("email", "in_app")


def _require(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class MailMessage:
    """One notification to deliver through the organization's transport."""

    kind: str
    recipient_ref: str
    title: str
    body: str
    idempotency_key: str
    url: str | None = None
    channels: tuple[str, ...] = ("email",)
    payload: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        _require("kind", self.kind)
        _require("recipient_ref", self.recipient_ref)
        _require("title", self.title)
        _require("idempotency_key", self.idempotency_key)
        if not self.channels:
            raise ValueError("channels must name at least one channel")
        unknown = [channel for channel in self.channels if channel not in CHANNELS]
        if unknown:
            raise ValueError(f"unknown channels {unknown}; known: {', '.join(CHANNELS)}")
        if self.url is not None:
            _require("url", self.url)
            if not self.url.startswith("/"):
                raise ValueError("url must be an absolute path on the Hub origin")


@dataclass(frozen=True, slots=True)
class MailReceipt:
    """What the transport answers: accepted now, or already delivered for that key."""

    accepted: bool
    duplicate: bool


@dataclass(frozen=True, slots=True)
class ActivityEvent:
    """One entry mirrored to the Hub activity log; ``event_id`` is the delivery key."""

    event_id: UUID
    action: str
    actor_ref: str
    object_type: str
    object_id: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        _require("action", self.action)
        _require("actor_ref", self.actor_ref)
        _require("object_type", self.object_type)
        _require("object_id", self.object_id)
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware (storage and logs are UTC)")


@runtime_checkable
class NotifyAdapter(Protocol):
    """Mail and activity delivery of ``docs/hub-contract.md`` §3."""

    def send_mail(self, organization_id: UUID, message: MailMessage) -> MailReceipt:
        """Deliver once per ``message.idempotency_key`` within the organization.

        Reusing a key with different content raises
        :class:`academy.exceptions.Conflict` instead of silently dropping the message.
        """
        ...

    def record_activity(self, organization_id: UUID, event: ActivityEvent) -> bool:
        """Mirror the event, returning ``True`` for a first delivery and ``False`` for a repeat.

        Reusing an ``event_id`` with different content raises
        :class:`academy.exceptions.Conflict`.
        """
        ...
