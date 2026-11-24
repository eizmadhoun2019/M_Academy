"""``audit.record``: one append-only row inside the caller's transaction.

The service never emits an event of its own and never opens a transaction, so an audit row
exists exactly when the action it describes committed and disappears with it (ADR-009). The
database trigger added in migration ``0004`` is the real guard; the checks here reject a bad
call before it reaches PostgreSQL, where the error would only name the trigger.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from django.utils import timezone

from academy.models import AuditEvent

_ACTION = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
_OBJECT_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_KEY = re.compile(r"^[a-z][a-z0-9_]*$")

#: ``metadata`` carries IDs only (``docs/domain-model.md`` §2.13). These keys name free text or
#: personal data, so a caller that tries to store them is fixed at the call site instead of
#: leaking it into a table with a five-year retention.
_FORBIDDEN_KEYS = frozenset(
    {
        "address",
        "comment",
        "comments",
        "description",
        "display_name",
        "email",
        "first_name",
        "free_text",
        "full_name",
        "ip",
        "ip_address",
        "last_name",
        "mobile",
        "name",
        "note",
        "notes",
        "phone",
        "reason",
        "text",
        "title",
    }
)

_METADATA_TYPES = (str, int, float, bool, type(None))


class AuditError(ValueError):
    """A call that cannot be recorded as written."""


def record(
    *,
    organization_id: UUID,
    actor_ref: str,
    action: str,
    object_type: str,
    object_id: str,
    metadata: Mapping[str, Any] | None = None,
    occurred_at: datetime | None = None,
    event_id: UUID | None = None,
) -> AuditEvent:
    """Append one audit row in the current transaction and return it.

    ``actor_ref`` is the verified ``user_ref`` or ``"system"``; ``action`` is the dotted name
    from ARCHITECTURE §7; ``object_id`` is a UUID or opaque reference. Passing ``event_id``
    makes the call idempotent for one organization, which is what the Hub mirror needs.
    """
    _require_organization(organization_id)
    _require_ref(actor_ref, "actor_ref")
    if not _ACTION.match(action):
        raise AuditError(f"action must be a dotted lowercase name, got {action!r}")
    if not _OBJECT_TYPE.match(object_type):
        raise AuditError(f"object_type must be a simple model name, got {object_type!r}")
    _require_ref(object_id, "object_id")

    cleaned = _clean_metadata(metadata)

    if event_id is not None:
        existing = AuditEvent.objects.for_org(organization_id).filter(event_id=event_id).first()
        if existing is not None:
            if (
                existing.actor_ref,
                existing.action,
                existing.object_type,
                existing.object_id,
            ) != (actor_ref, action, object_type, object_id):
                raise AuditError(f"event_id {event_id} already records a different action")
            return existing

    return AuditEvent.objects.create(
        organization_id=organization_id,
        event_id=event_id or uuid4(),
        actor_ref=actor_ref,
        action=action,
        object_type=object_type,
        object_id=object_id,
        metadata=cleaned,
        occurred_at=occurred_at or timezone.now(),
    )


def _require_organization(organization_id: object) -> None:
    if not isinstance(organization_id, UUID):
        raise AuditError("organization_id must be an organization UUID")


def _require_ref(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise AuditError(f"{field} must be a non-empty string")
    if len(value) > 64:
        raise AuditError(f"{field} is limited to 64 characters")
    if value != value.strip():
        raise AuditError(f"{field} must not carry surrounding whitespace")


def _clean_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        raise AuditError("metadata must be a mapping of ids")
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if not isinstance(key, str) or not _KEY.match(key):
            raise AuditError(f"metadata key must be a lowercase name, got {key!r}")
        if key in _FORBIDDEN_KEYS:
            raise AuditError(f"metadata.{key} names free text or personal data; store its id")
        if isinstance(value, _METADATA_TYPES):
            cleaned[key] = value
            continue
        if isinstance(value, (list, tuple)) and all(
            isinstance(item, _METADATA_TYPES) for item in value
        ):
            cleaned[key] = list(value)
            continue
        raise AuditError(f"metadata.{key} must be an id, scalar or list of ids")
    return cleaned
