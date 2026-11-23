"""Development signed-identity verifier (format of ``docs/hub-contract.md`` §2).

It verifies the signature and decodes the claims; issuer, audience, freshness, route binding
and the nonce check stay with the caller, which is exactly the division the Hub contract
specifies for a replacement verifier.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from typing import Any

_KID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _signature(kid: str, payload: str, secret: str) -> str:
    message = f"{kid}.{payload}".encode("ascii")
    return _encode(hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest())


def sign_claims(claims: Mapping[str, Any], *, kid: str, secret: str) -> str:
    """Build the ``kid.payload.signature`` token a development proxy would send.

    Tests and the development login use this instead of a real Hub; it signs exactly what
    :meth:`DevelopmentIdentity.verify` checks.
    """
    payload = _encode(json.dumps(dict(claims), ensure_ascii=False, separators=(",", ":")).encode())
    return f"{kid}.{payload}.{_signature(kid, payload, secret)}"


class DevelopmentIdentity:
    """HMAC-SHA256 verifier for development and tests."""

    def verify(self, token: str, keys: Mapping[str, str]) -> dict[str, Any]:
        if not isinstance(token, str) or not token:
            raise ValueError("identity token is missing")
        if not keys:
            raise ValueError("identity key ring is empty")

        kid, _, rest = token.partition(".")
        payload, _, signature = rest.partition(".")
        if not kid or not payload or not signature or "." in signature:
            raise ValueError("identity token must be 'kid.payload.signature'")
        if not _KID_RE.match(kid):
            raise ValueError(f"identity key id {kid!r} is not 1-64 of [A-Za-z0-9_-]")

        secret = keys.get(kid)
        if not secret:
            raise ValueError(f"identity key id {kid!r} is not in the key ring")

        if not hmac.compare_digest(_signature(kid, payload, secret), signature):
            raise ValueError("identity signature does not match")

        try:
            claims = json.loads(_decode(payload))
        except ValueError as exc:  # binascii.Error and JSONDecodeError are ValueErrors
            raise ValueError(f"identity payload is not base64url JSON ({exc})") from exc
        if not isinstance(claims, dict):
            raise ValueError("identity claims must be a JSON object")
        return claims
