"""Celery tasks for media processing — ``docs/background-jobs.md`` §1."""

from __future__ import annotations

import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from academy.media import service

logger = logging.getLogger(__name__)


@shared_task(
    name="academy.media.process",
    bind=True,
    max_retries=2,
    soft_time_limit=3300,
    time_limit=3600,
    autoretry_for=(),
)
def process_media(self, asset_id: str, organization_id: str) -> str:  # type: ignore[no-untyped-def]
    from django.conf import settings

    attempts = int(getattr(settings, "ACADEMY_TRANSCODE_ATTEMPTS", 2))
    countdowns = [60, 300]
    try:
        service.process_asset(asset_id, organization_id)
        return "ready"
    except SoftTimeLimitExceeded as exc:
        service._fail_by_id(asset_id, organization_id, "transcode_failed")
        countdown = countdowns[min(self.request.retries, len(countdowns) - 1)]
        raise self.retry(exc=exc, countdown=countdown) from exc
    except Exception as exc:  # noqa: BLE001
        try:
            service._fail_by_id(asset_id, organization_id, _error_code(exc))
        except Exception:  # noqa: BLE001
            logger.exception("could not mark media asset failed")
        if self.request.retries < attempts:
            countdown = countdowns[min(self.request.retries, len(countdowns) - 1)]
            raise self.retry(exc=exc, countdown=countdown) from exc
        return "failed"


def _error_code(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    if "probe" in name or "ffprobe" in str(exc).lower():
        return "probe_failed"
    if "storage" in str(exc).lower() or "url" in str(exc).lower():
        return "storage_unavailable"
    return "transcode_failed"
