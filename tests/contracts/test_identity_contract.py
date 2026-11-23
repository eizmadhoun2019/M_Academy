"""Identity seam contract (REQ-02) — every implementation must pass this suite.

Adding a class to ``IMPLEMENTATIONS`` runs the same assertions against it; T-015 adds the Hub
fake behind this seam. The suite fixes only what the seam promises: valid tokens verify to
their claims, everything else raises ``ValueError``, and expiry/audience are the caller's
business (``docs/hub-contract.md`` §2, §5).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Callable
from typing import Any

import pytest

from academy.adapters.identity import IdentityAdapter
from host_stub.identity import DevelopmentIdentity, sign_claims

SECRET = "identity-secret-0123456789abcdef"
OTHER_SECRET = "identity-secret-fedcba9876543210"
KID = "dev-1"

CLAIMS: dict[str, Any] = {
    "iss": "masheed-hub",
    "aud": "masheed-academy",
    "iat": 1795132800,
    "exp": 1795132860,
    "nonce": "N1928Egz4jYnK-w22BR8XP3mYXMh9mVB",
    "organization_id": "25498ed9-13b1-4f10-8294-859ff80a41b7",
    "user_ref": "u-42",
    "display_name": "Example Employee",
    "language": "ar",
    "role": "employee",
    "department_refs": ["training"],
    "is_active": True,
    "method": "GET",
    "target": "/api/v1/academy/?view=compact",
}

IMPLEMENTATIONS: dict[str, Callable[[], IdentityAdapter]] = {
    "host_stub.DevelopmentIdentity": DevelopmentIdentity,
}


@pytest.fixture(params=list(IMPLEMENTATIONS.values()), ids=list(IMPLEMENTATIONS))
def adapter(request: pytest.FixtureRequest) -> IdentityAdapter:
    return request.param()


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def token_for(kid: str, payload: bytes, secret: str) -> str:
    """A token over arbitrary payload bytes, for the malformed cases."""
    encoded = _encode(payload)
    message = f"{kid}.{encoded}".encode("ascii")
    signature = _encode(hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest())
    return f"{kid}.{encoded}.{signature}"


def test_returns_the_signed_claims(adapter: IdentityAdapter) -> None:
    token = sign_claims(CLAIMS, kid=KID, secret=SECRET)

    assert adapter.verify(token, {KID: SECRET}) == CLAIMS


def test_accepts_a_rotated_key_ring(adapter: IdentityAdapter) -> None:
    token = sign_claims(CLAIMS, kid=KID, secret=SECRET)

    assert adapter.verify(token, {KID: SECRET, "next-1": OTHER_SECRET}) == CLAIMS


def test_rejects_an_unknown_key_id(adapter: IdentityAdapter) -> None:
    token = sign_claims(CLAIMS, kid=KID, secret=SECRET)

    with pytest.raises(ValueError):
        adapter.verify(token, {"other-1": SECRET})


def test_rejects_a_signature_from_another_secret(adapter: IdentityAdapter) -> None:
    token = sign_claims(CLAIMS, kid=KID, secret=OTHER_SECRET)

    with pytest.raises(ValueError):
        adapter.verify(token, {KID: SECRET})


def test_rejects_a_tampered_payload(adapter: IdentityAdapter) -> None:
    token = sign_claims(CLAIMS, kid=KID, secret=SECRET)
    kid, payload, signature = token.split(".")
    forged = _encode(b'{"user_ref":"someone-else"}')

    with pytest.raises(ValueError):
        adapter.verify(f"{kid}.{forged}.{signature}", {KID: SECRET})


@pytest.mark.parametrize(
    "token",
    [
        "",
        "no-dots-at-all",
        "only.two",
        "kid.payload.signature.extra",
        ".payload.signature",
        "kid..signature",
    ],
)
def test_rejects_a_token_that_is_not_three_fields(adapter: IdentityAdapter, token: str) -> None:
    with pytest.raises(ValueError):
        adapter.verify(token, {KID: SECRET})


@pytest.mark.parametrize("kid", ["has space", "has/slash", "", "x" * 65])
def test_rejects_an_invalid_key_id(adapter: IdentityAdapter, kid: str) -> None:
    if not kid:
        token = f".{_encode(b'{}')}.{_encode(b'sig')}"
    else:
        token = sign_claims(CLAIMS, kid=kid, secret=SECRET)

    with pytest.raises(ValueError):
        adapter.verify(token, {kid: SECRET})


def test_rejects_a_payload_that_is_not_json(adapter: IdentityAdapter) -> None:
    token = token_for(KID, b"not-json", SECRET)

    with pytest.raises(ValueError):
        adapter.verify(token, {KID: SECRET})


def test_rejects_claims_that_are_not_an_object(adapter: IdentityAdapter) -> None:
    token = token_for(KID, b'["u-42"]', SECRET)

    with pytest.raises(ValueError):
        adapter.verify(token, {KID: SECRET})


def test_rejects_an_empty_key_ring(adapter: IdentityAdapter) -> None:
    token = sign_claims(CLAIMS, kid=KID, secret=SECRET)

    with pytest.raises(ValueError):
        adapter.verify(token, {})


def test_leaves_expiry_to_the_caller(adapter: IdentityAdapter) -> None:
    stale = {**CLAIMS, "iat": 1, "exp": 2}

    assert adapter.verify(sign_claims(stale, kid=KID, secret=SECRET), {KID: SECRET}) == stale
