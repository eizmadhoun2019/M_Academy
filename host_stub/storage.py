"""Development and test object storage, held in memory.

Presigned URLs point at a ``memory://`` endpoint rather than the bucket; the media pipeline
(T-018) only hands them to the browser, and tests read objects through :meth:`InMemoryStorage.get`
instead of following them. Keys are validated here exactly as the seam requires, so a wrong key
fails in development rather than in production.
"""

from __future__ import annotations

from urllib.parse import quote, urlencode

from academy.adapters.storage import ObjectStat, validate_key, validate_prefix


class InMemoryStorage:
    """Dict-backed bucket with presigned-URL shapes and metadata."""

    def __init__(self, *, endpoint: str = "memory://academy") -> None:
        self._endpoint = endpoint.rstrip("/")
        self._objects: dict[str, tuple[bytes, str]] = {}

    # --- test and development helpers ---------------------------------------

    def put(self, key: str, data: bytes, *, content_type: str) -> None:
        """Store an object directly, as the browser's ``PUT`` would have."""
        validate_key(key)
        if not content_type:
            raise ValueError("content_type must be a non-empty string")
        if not isinstance(data, bytes):
            raise ValueError("data must be bytes")
        self._objects[key] = (data, content_type)

    def get(self, key: str) -> bytes | None:
        """Read an object's bytes, or ``None`` when nothing is stored under ``key``."""
        validate_key(key)
        stored = self._objects.get(key)
        return None if stored is None else stored[0]

    def keys(self) -> tuple[str, ...]:
        """Every stored key, sorted."""
        return tuple(sorted(self._objects))

    # --- the seam -----------------------------------------------------------

    def presign_put(self, key: str, *, content_type: str, max_bytes: int, ttl_seconds: int) -> str:
        validate_key(key)
        if not content_type:
            raise ValueError("content_type must be a non-empty string")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        query = urlencode(
            {
                "method": "PUT",
                "expires": ttl_seconds,
                "max-bytes": max_bytes,
                "content-type": content_type,
            },
            quote_via=quote,
        )
        return f"{self._endpoint}/{key}?{query}"

    def presign_get(self, key: str, *, ttl_seconds: int) -> str:
        validate_key(key)
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        return f"{self._endpoint}/{key}?{urlencode({'method': 'GET', 'expires': ttl_seconds})}"

    def stat(self, key: str) -> ObjectStat | None:
        validate_key(key)
        stored = self._objects.get(key)
        if stored is None:
            return None
        data, content_type = stored
        return ObjectStat(key=key, size_bytes=len(data), content_type=content_type)

    def delete_prefix(self, prefix: str) -> int:
        validate_prefix(prefix)
        doomed = [key for key in self._objects if key.startswith(prefix)]
        for key in doomed:
            del self._objects[key]
        return len(doomed)
