"""Directory cache invalidation shared by the webhook and the Hub directory adapter.

A per-tenant generation counter is part of every directory cache key: a membership webhook
increments it, so all cached lookups for that organization become unreachable at once without
scanning or deleting individual keys (``docs/hub-contract.md`` §3 and §4).
"""

from __future__ import annotations

from uuid import UUID

from django.conf import settings
from django.core.cache import cache


def _key(organization_id: UUID) -> str:
    return f"macademy:hub:directory-generation:{organization_id}"


def directory_generation(organization_id: UUID) -> int:
    value = cache.get(_key(organization_id), 1)
    return int(value) if isinstance(value, int | str) else 1


def invalidate_directory(organization_id: UUID) -> int:
    """Start a new generation and return it."""
    key = _key(organization_id)
    try:
        return int(cache.incr(key))
    except ValueError:
        cache.set(key, 2, timeout=None)
        return 2


def directory_ttl() -> int:
    return int(getattr(settings, "ACADEMY_HUB_DIRECTORY_TTL", 60))
