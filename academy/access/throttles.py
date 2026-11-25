"""Cache-backed rate limits for the server-rendered pages (``docs/configuration.md`` §6)."""

from __future__ import annotations

import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest

_PERIODS = {"sec": 1, "min": 60, "hour": 3600}


def _client_key(request: HttpRequest) -> str:
    return str(request.META.get("REMOTE_ADDR") or "unknown")


def throttle_exceeded(request: HttpRequest, scope: str, rate: str) -> bool:
    """Count one attempt and report whether it went over ``rate`` (for example ``10/min``)."""
    if not bool(getattr(settings, "THROTTLES_ENABLED", True)):
        return False
    limit_text, _, period = rate.partition("/")
    limit = int(limit_text)
    window = _PERIODS.get(period, 60)
    slot = int(time.time() // window)
    key = f"macademy:throttle:{scope}:{_client_key(request)}:{slot}"
    count = cache.get(key, 0)
    if count >= limit:
        return True
    cache.set(key, count + 1, timeout=window + 1)
    return False
