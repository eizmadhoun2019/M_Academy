"""T-015 acceptance: Hub membership webhooks (``docs/hub-contract.md`` §4).

The endpoint proves the signature, binds the body hash, rejects a replayed nonce, answers a
repeat of the same event with a *fresh* nonce as a duplicate, and treats a reused event id with
different bytes as a conflict.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from django.core.cache import cache
from django.test import Client, override_settings

from academy.hub.cache import directory_generation
from academy.models import HubWebhookEvent
from host_hub.fake import sign_webhook

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
OTHER_ORG = UUID("2f5e3d1a-0c4b-4a8e-9f2d-6b7c8d9e0f11")
WEBHOOK = "/internal/hub/webhooks/"
KID = "w1"
SECRET = "test-webhook-secret-that-is-at-least-32-bytes"
HUB = dict(
    ACADEMY_HUB_IDENTITY_KEYS={KID: SECRET},
    ACADEMY_HUB_WEBHOOK_KEYS={KID: SECRET},
    ACADEMY_ORGANIZATION_ID=ORG,
)


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    cache.clear()


def event(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "event_id": str(uuid4()),
        "type": "member_changed",
        "organization_id": str(ORG),
        "user_ref": "u-42",
        "occurred_at": 1795132800,
        "department_refs": ["training"],
        "role": "employee",
        "is_active": True,
    }
    body.update(overrides)
    return body


def deliver(
    client: Client,
    body: dict[str, Any],
    *,
    signature: str | None = None,
    method: str = "POST",
    **overrides: Any,
) -> Any:
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    token = signature
    if token is None:
        token = sign_webhook(raw, organization_id=ORG, kid=KID, secret=SECRET)
    settings = {**HUB, **overrides}
    with override_settings(**settings):
        return client.generic(
            method,
            WEBHOOK,
            data=raw,
            content_type="application/json",
            HTTP_X_MASHEED_WEBHOOK=token,
        )


def test_a_valid_event_is_accepted_once(db: Any, client: Client) -> None:
    body = event()
    response = deliver(client, body)
    assert response.status_code == 200
    assert response.json() == {"accepted": True, "duplicate": False}
    assert HubWebhookEvent.objects.filter(event_id=body["event_id"]).count() == 1


def test_a_repeat_with_a_fresh_nonce_is_a_duplicate(db: Any, client: Client) -> None:
    body = event()
    assert deliver(client, body).json()["duplicate"] is False
    repeat = deliver(client, body)
    assert repeat.status_code == 200
    assert repeat.json()["duplicate"] is True
    assert HubWebhookEvent.objects.count() == 1


def test_the_same_event_id_with_different_bytes_conflicts(db: Any, client: Client) -> None:
    body = event()
    assert deliver(client, body).status_code == 200
    changed = dict(body, is_active=False)
    response = deliver(client, changed)
    assert response.status_code == 409
    assert response.json()["code"] == "idempotency_conflict"


def test_a_replayed_nonce_is_401(db: Any, client: Client) -> None:
    body = event()
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    nonce = "N1928Egz4jYnK-w22BR8XP3mYXMh9mVB"
    first = sign_webhook(raw, organization_id=ORG, kid=KID, secret=SECRET, nonce=nonce)
    assert deliver(client, body, signature=first).status_code == 200
    second = sign_webhook(raw, organization_id=ORG, kid=KID, secret=SECRET, nonce=nonce)
    assert deliver(client, body, signature=second).status_code == 401


def test_a_bad_signature_is_401(db: Any, client: Client) -> None:
    body = event()
    assert deliver(client, body, signature="w1.abc.def").status_code == 401


def test_a_missing_signature_is_401(db: Any, client: Client) -> None:
    raw = json.dumps(event(), separators=(",", ":")).encode("utf-8")
    with override_settings(**HUB):
        response = client.post(WEBHOOK, data=raw, content_type="application/json")
    assert response.status_code == 401


def test_a_body_hash_mismatch_is_401(db: Any, client: Client) -> None:
    signed_body = event()
    other_body = event()
    raw = json.dumps(other_body, separators=(",", ":")).encode("utf-8")
    token = sign_webhook(
        json.dumps(signed_body, separators=(",", ":")).encode("utf-8"),
        organization_id=ORG,
        kid=KID,
        secret=SECRET,
    )
    with override_settings(**HUB):
        response = client.post(
            WEBHOOK,
            data=raw,
            content_type="application/json",
            HTTP_X_MASHEED_WEBHOOK=token,
        )
    assert response.status_code == 401


def test_another_tenant_is_403(db: Any, client: Client) -> None:
    body = event(organization_id=str(OTHER_ORG))
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    token = sign_webhook(raw, organization_id=OTHER_ORG, kid=KID, secret=SECRET)
    assert deliver(client, body, signature=token).status_code == 403


def test_a_malformed_event_is_400(db: Any, client: Client) -> None:
    body = event()
    del body["type"]
    assert deliver(client, body).status_code == 400


def test_another_method_is_405(db: Any, client: Client) -> None:
    assert deliver(client, event(), method="GET").status_code == 405


def test_an_oversized_body_is_413(db: Any, client: Client) -> None:
    response = deliver(client, event(), ACADEMY_API_BODY_LIMIT_BYTES=8)
    assert response.status_code == 413


def test_an_accepted_event_invalidates_the_directory_cache(db: Any, client: Client) -> None:
    before = directory_generation(ORG)
    assert deliver(client, event()).status_code == 200
    assert directory_generation(ORG) > before


def test_a_deactivation_calls_the_cancellation_hook(
    db: Any, client: Client, monkeypatch: Any
) -> None:
    calls: list[tuple[UUID, str]] = []
    monkeypatch.setattr(
        "academy.hub.webhooks.member_deactivated",
        lambda organization_id, user_ref: calls.append((organization_id, user_ref)),
    )
    response = deliver(client, event(type="member_deactivated"))
    assert response.status_code == 200
    assert calls == [(ORG, "u-42")]
