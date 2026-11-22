"""Health endpoint tests (T-001 acceptance: ``/healthz`` answers 200)."""

from __future__ import annotations

import pytest
from django.test import Client


@pytest.mark.django_db
def test_healthz_reports_ready() -> None:
    response = Client().get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"database": True, "cache": True},
    }
    assert response["Cache-Control"] == "no-store"
    assert response["Content-Type"] == "application/json"


@pytest.mark.django_db
def test_healthz_reports_unavailable_when_cache_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_get(key: str, default: object = None) -> object:
        raise ConnectionError("redis down")

    monkeypatch.setattr("config.health.cache.get", broken_get)

    response = Client().get("/healthz")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert response.json()["checks"] == {"database": True, "cache": False}
