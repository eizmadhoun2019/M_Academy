"""T-015 acceptance: signed Hub identity on the browser path (``docs/hub-contract.md`` §2).

Nothing in these tests trusts a claim the signature does not cover: expired, tampered,
misrouted, replayed and wrong-tenant assertions are all indistinguishable from no identity.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

import pytest
from django.core.cache import cache
from django.test import override_settings

from academy.access.principals import SESSION_KEY
from host_hub.fake import DEFAULT_KID, DEFAULT_SECRET, sign_identity

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
OTHER_ORG = UUID("2f5e3d1a-0c4b-4a8e-9f2d-6b7c8d9e0f11")
SECRET = "test-identity-secret-that-is-at-least-32-bytes"
CAPABILITIES = "/api/v1/academy/me/capabilities/"
HUB = dict(
    ACADEMY_ACCESS_MODE="hub",
    ACADEMY_HUB_IDENTITY_KEYS={DEFAULT_KID: SECRET},
    ACADEMY_HUB_WEBHOOK_KEYS={DEFAULT_KID: SECRET},
)


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    cache.clear()


def token(**overrides: Any) -> str:
    values: dict[str, Any] = {
        "method": "GET",
        "target": CAPABILITIES,
        "organization_id": ORG,
        "kid": DEFAULT_KID,
        "secret": SECRET,
    }
    values.update(overrides)
    return sign_identity(**values)


def get(client: Any, value: str | None, path: str = CAPABILITIES) -> Any:
    """Django's typed client cannot take a dynamic ``HTTP_*`` keyword; this wrapper can."""
    with override_settings(**HUB):
        return client.get(path, **{"HTTP_X_MASHEED_IDENTITY": value})


def status(client: Any, value: str | None, path: str = CAPABILITIES) -> int:
    return int(get(client, value, path).status_code)


def test_a_valid_assertion_authenticates_and_names_the_user(db: Any, client: Any) -> None:
    response = get(client, token())
    assert response.status_code == 200
    assert response.json()["user_ref"] == "u-42"


def test_missing_identity_is_401(db: Any, client: Any) -> None:
    assert status(client, None) == 401


def test_a_tampered_signature_is_401(db: Any, client: Any) -> None:
    value = token()
    tampered = value[:-2] + ("AA" if not value.endswith("AA") else "BB")
    assert status(client, tampered) == 401


def test_an_expired_assertion_is_401(db: Any, client: Any) -> None:
    assert status(client, token(now=int(time.time()) - 3600)) == 401


def test_a_wrong_secret_is_401(db: Any, client: Any) -> None:
    assert status(client, token(secret=DEFAULT_SECRET)) == 401


def test_another_tenant_is_401(db: Any, client: Any) -> None:
    assert status(client, token(organization_id=OTHER_ORG)) == 401


def test_an_assertion_signed_for_another_path_is_401(db: Any, client: Any) -> None:
    assert status(client, token(target="/api/v1/academy/other")) == 401


def test_an_assertion_signed_for_another_method_is_401(db: Any, client: Any) -> None:
    assert status(client, token(method="POST")) == 401


def test_a_replayed_nonce_is_401(db: Any, client: Any) -> None:
    nonce = "N1928Egz4jYnK-w22BR8XP3mYXMh9mVB"
    first = get(client, token(nonce=nonce))
    second = get(client, token(nonce=nonce))
    assert first.status_code == 200
    assert second.status_code == 401


def test_an_inactive_member_is_403_account_inactive(db: Any, client: Any) -> None:
    response = get(client, token(is_active=False))
    assert response.status_code == 403
    assert response.json()["code"] == "account_inactive"


def test_a_hub_identity_is_ignored_in_standalone_mode(db: Any, client: Any) -> None:
    with override_settings(**{**HUB, "ACADEMY_ACCESS_MODE": "standalone"}):
        assert client.get(CAPABILITIES, **{"HTTP_X_MASHEED_IDENTITY": token()}).status_code == 401
        session = client.session
        session[SESSION_KEY] = {"user_ref": "u-local", "roles": ["employee"], "is_active": True}
        session.save()
        response = client.get(CAPABILITIES, **{"HTTP_X_MASHEED_IDENTITY": token()})
        assert response.json()["user_ref"] == "u-local"


def test_the_roles_of_the_assertion_reach_the_authorization_layer(db: Any, client: Any) -> None:
    with override_settings(**{**HUB, "ACADEMY_AUTHORIZATION_MODE": "role_plus_grants"}):
        response = client.get(
            CAPABILITIES,
            **{
                "HTTP_X_MASHEED_IDENTITY": token(
                    role="department_manager", department_refs=["dep-1"]
                )
            },
        )
    capabilities = {item["capability"]: item for item in response.json()["capabilities"]}
    assert capabilities["academy.manage_content"]["departments"] == ["dep-1"]
