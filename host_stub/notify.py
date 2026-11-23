"""Development and test notification transport: records instead of sending.

It keeps the two properties the seam promises — one delivery per idempotency key and per event
id, and a conflict when a key is reused for different content — without touching a mail server
or the Hub. T-015 replaces it in production with the Hub HTTP transport, which the same
contract suite checks.
"""

from __future__ import annotations

from uuid import UUID

from academy.adapters.notify import ActivityEvent, MailMessage, MailReceipt
from academy.exceptions import Conflict


class RecordingNotifier:
    """Collects messages and activity events in memory."""

    def __init__(self) -> None:
        self._mail: list[tuple[UUID, MailMessage]] = []
        self._activity: list[tuple[UUID, ActivityEvent]] = []
        self._mail_keys: dict[tuple[UUID, str], MailMessage] = {}
        self._event_keys: dict[tuple[UUID, str], ActivityEvent] = {}

    @property
    def sent_mail(self) -> tuple[tuple[UUID, MailMessage], ...]:
        """Every delivered message, oldest first, as (organization, message) pairs."""
        return tuple(self._mail)

    @property
    def recorded_activity(self) -> tuple[tuple[UUID, ActivityEvent], ...]:
        """Every recorded activity event, oldest first."""
        return tuple(self._activity)

    def send_mail(self, organization_id: UUID, message: MailMessage) -> MailReceipt:
        key = (organization_id, message.idempotency_key)
        seen = self._mail_keys.get(key)
        if seen is not None:
            if seen != message:
                raise Conflict(
                    f"idempotency key {message.idempotency_key!r} was used for different content"
                )
            return MailReceipt(accepted=True, duplicate=True)
        self._mail_keys[key] = message
        self._mail.append((organization_id, message))
        return MailReceipt(accepted=True, duplicate=False)

    def record_activity(self, organization_id: UUID, event: ActivityEvent) -> bool:
        key = (organization_id, str(event.event_id))
        seen = self._event_keys.get(key)
        if seen is not None:
            if seen != event:
                raise Conflict(f"event id {event.event_id} was used for different content")
            return False
        self._event_keys[key] = event
        self._activity.append((organization_id, event))
        return True
