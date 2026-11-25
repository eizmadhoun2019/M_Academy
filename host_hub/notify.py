"""Mail and activity delivery over HTTP — ``docs/hub-contract.md`` §3.

Every write carries its idempotency key, so a retried delivery is answered as a duplicate
instead of sending twice; a key reused for different content surfaces as
:class:`academy.exceptions.Conflict`.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from academy.adapters.notify import ActivityEvent, MailMessage, MailReceipt
from host_hub.http import HubHttpClient


class HubNotifier:
    """Deliver notifications through the Hub service API."""

    def __init__(self, client: HubHttpClient | None = None) -> None:
        self.client = client or HubHttpClient()

    def send_mail(self, organization_id: UUID, message: MailMessage) -> MailReceipt:
        payload: dict[str, Any] = {
            "kind": message.kind,
            "recipient_ref": message.recipient_ref,
            "title": message.title,
            "body": message.body,
            "url": message.url,
            "idempotency_key": message.idempotency_key,
            "channels": list(message.channels),
            "payload": dict(message.payload) if message.payload is not None else None,
        }
        data = self.client.post(
            "mail",
            payload,
            idempotency_key=message.idempotency_key,
            organization_id=str(organization_id),
        )
        return MailReceipt(
            accepted=bool(data.get("accepted", True)), duplicate=bool(data.get("duplicate", False))
        )

    def record_activity(self, organization_id: UUID, event: ActivityEvent) -> bool:
        payload = {
            "event_id": str(event.event_id),
            "action": event.action,
            "actor_ref": event.actor_ref,
            "object_type": event.object_type,
            "object_id": event.object_id,
            "occurred_at": event.occurred_at.isoformat(),
        }
        data = self.client.post(
            "activity",
            payload,
            idempotency_key=str(event.event_id),
            organization_id=str(organization_id),
        )
        return not bool(data.get("duplicate", False))
