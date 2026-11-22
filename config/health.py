"""Liveness/readiness endpoint.

Reports the two dependencies a request needs: the database and the cache. Both checks are
time-bounded so a hung dependency answers 503 instead of blocking the probe.
"""

from __future__ import annotations

import logging

from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, JsonResponse
from drf_spectacular.utils import extend_schema

logger = logging.getLogger(__name__)


def _check_database() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # noqa: BLE001 - any failure means "not ready"
        logger.exception("health: database check failed")
        return False
    return True


def _check_cache() -> bool:
    try:
        cache.set("health:probe", "1", timeout=5)
        return cache.get("health:probe") == "1"
    except Exception:  # noqa: BLE001 - any failure means "not ready"
        logger.exception("health: cache check failed")
        return False


@extend_schema(exclude=True)
def healthz(request: HttpRequest) -> JsonResponse:
    checks = {"database": _check_database(), "cache": _check_cache()}
    ready = all(checks.values())
    response = JsonResponse(
        {"status": "ok" if ready else "unavailable", "checks": checks}, status=200 if ready else 503
    )
    response["Cache-Control"] = "no-store"
    return response
