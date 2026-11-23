"""Object-storage seam — presigned URLs, ``stat`` and prefix delete (ARCHITECTURE.md §6).

Keys are tenant-prefixed (``org/<organization_id>/media/<asset_id>/…``,
``docs/configuration.md`` §4) and every implementation refuses a key that leaves that prefix
before it makes a storage request, so a wrong key is an exception at the seam rather than an
object planted in another tenant's part of the bucket.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_KEY_RE = re.compile(rf"^org/(?P<organization>{_UUID})/(?P<rest>[A-Za-z0-9][A-Za-z0-9._/-]*)$")


@dataclass(frozen=True, slots=True)
class ObjectStat:
    """What the bucket reports about one stored object."""

    key: str
    size_bytes: int
    content_type: str
    etag: str | None = None


def organization_prefix(organization_id: UUID) -> str:
    """The media prefix every key of one organization lives under."""
    return f"org/{organization_id}/media/"


def _check_shape(key: str) -> re.Match[str]:
    if not isinstance(key, str) or not key:
        raise ValueError("storage key must be a non-empty string")
    if key.startswith("/") or "\\" in key or ".." in key or "//" in key:
        raise ValueError(f"storage key {key!r} is not a relative path inside the bucket")
    match = _KEY_RE.match(key)
    if match is None:
        raise ValueError(
            f"storage key {key!r} must be 'org/<organization_id>/<path>' with a plain <path>"
        )
    return match


def validate_key(key: str, *, organization_id: UUID | None = None) -> str:
    """Return ``key`` after checking it names an object of the organization's media tree."""
    match = _check_shape(key)
    if key.endswith("/"):
        raise ValueError(f"storage key {key!r} names a prefix, not an object")
    if not match.group("rest").startswith("media/"):
        raise ValueError(f"storage key {key!r} must live under 'media/'")
    if organization_id is not None and UUID(match.group("organization")) != organization_id:
        raise ValueError(f"storage key {key!r} belongs to another organization")
    return key


def validate_prefix(prefix: str, *, organization_id: UUID | None = None) -> str:
    """Return ``prefix`` after checking it is a deletable path below one organization's media."""
    match = _check_shape(prefix)
    if not prefix.endswith("/"):
        raise ValueError(f"storage prefix {prefix!r} must end with '/'")
    rest = match.group("rest")
    if not rest.startswith("media/") or rest == "media/":
        raise ValueError(
            f"storage prefix {prefix!r} must be below the media root, not the media root itself"
        )
    if organization_id is not None and UUID(match.group("organization")) != organization_id:
        raise ValueError(f"storage prefix {prefix!r} belongs to another organization")
    return prefix


@runtime_checkable
class StorageAdapter(Protocol):
    """Object storage as the media pipeline and playback need it."""

    def presign_put(self, key: str, *, content_type: str, max_bytes: int, ttl_seconds: int) -> str:
        """A presigned ``PUT`` URL for one object, bounded in size and lifetime."""
        ...

    def presign_get(self, key: str, *, ttl_seconds: int) -> str:
        """A presigned ``GET`` URL for one object (playlist, segment or poster)."""
        ...

    def stat(self, key: str) -> ObjectStat | None:
        """The stored object's metadata, or ``None`` when the key holds nothing.

        This is how an upload is verified after the browser's direct ``PUT``: a client that
        reports success proves nothing on its own.
        """
        ...

    def delete_prefix(self, prefix: str) -> int:
        """Delete every object below ``prefix`` and return how many were removed."""
        ...
