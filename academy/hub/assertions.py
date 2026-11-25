"""Signed Hub assertions — ``docs/hub-contract.md`` §2 and §4.

The configured verifier proves the signature and returns the decoded claims; everything a
signature cannot prove stays here: issuer, audience, lifetime, clock skew, the method and target
the proxy signed, the single-use nonce and the tenant. Rejecting is always the same outcome — an
invalid assertion is indistinguishable from a missing identity.
"""

from __future__ import annotations

import importlib
import re
import time
from collections.abc import Callable, Mapping
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured

from academy.adapters.loader import load_adapter

#: Base64url of 24 random bytes, unpadded.
_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{32}$")
_KID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

WEBHOOK_CLAIMS = (
    "iss",
    "aud",
    "iat",
    "exp",
    "nonce",
    "target",
    "body_sha256",
)

REQUIRED_CLAIMS = (
    "iss",
    "aud",
    "iat",
    "exp",
    "nonce",
    "organization_id",
    "user_ref",
    "display_name",
    "language",
    "role",
    "department_refs",
    "is_active",
    "method",
    "target",
)


class InvalidAssertion(ValueError):
    """The assertion is malformed, expired, replayed, misrouted or for another tenant."""


def _callable(path: str) -> Callable[[str, Mapping[str, str]], dict[str, Any]]:
    module_path, _, attribute = path.partition(":")
    if not module_path or not attribute:
        raise ImproperlyConfigured(
            f"ACADEMY_HUB_IDENTITY_VERIFIER={path!r} must be 'module.path:callable'"
        )
    try:
        module = importlib.import_module(module_path)
    except ImportError as error:
        raise ImproperlyConfigured(
            f"ACADEMY_HUB_IDENTITY_VERIFIER module {module_path!r} is not importable ({error})"
        ) from error
    target = getattr(module, attribute, None)
    if not callable(target):
        raise ImproperlyConfigured(
            f"ACADEMY_HUB_IDENTITY_VERIFIER={path!r} does not resolve to a callable"
        )
    return target


def _verify_signature(token: str, keys: Mapping[str, str]) -> dict[str, Any]:
    """Run the replacement verifier when configured, otherwise the identity adapter."""
    configured = str(getattr(settings, "ACADEMY_HUB_IDENTITY_VERIFIER", "") or "").strip()
    if configured:
        return _callable(configured)(token, keys)
    verifier = load_adapter("identity")()
    return verifier.verify(token, keys)


def _seconds(claims: Mapping[str, Any], name: str) -> int:
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidAssertion(f"claim {name!r} must be integer Unix seconds")
    return value


def _consume_nonce(audience: str, nonce: str, lifetime: int) -> None:
    """One successful use per nonce; the cache entry outlives the acceptance window."""
    key = f"macademy:nonce:{audience}:{nonce}"
    if not cache.add(key, "1", timeout=lifetime):
        raise InvalidAssertion("assertion nonce was already used")


def verify(
    token: str,
    *,
    keys: Mapping[str, str],
    issuer: str,
    audience: str,
    lifetime: int,
    skew: int,
    method: str | None = None,
    target: str | None = None,
    now: int | None = None,
    required_claims: tuple[str, ...] = REQUIRED_CLAIMS,
) -> dict[str, Any]:
    """Verify one assertion and return its claims, or raise :class:`InvalidAssertion`."""
    if not keys:
        raise InvalidAssertion("no verification keys are configured")
    try:
        claims = _verify_signature(token, keys)
    except ValueError as error:
        raise InvalidAssertion(str(error)) from error
    if not isinstance(claims, Mapping):
        raise InvalidAssertion("verified claims must be an object")

    missing = [name for name in required_claims if name not in claims]
    if missing:
        raise InvalidAssertion(f"missing claims: {', '.join(missing)}")
    if claims["iss"] != issuer:
        raise InvalidAssertion("wrong issuer")
    if claims["aud"] != audience:
        raise InvalidAssertion("wrong audience")

    current = int(now if now is not None else time.time())
    issued = _seconds(claims, "iat")
    expires = _seconds(claims, "exp")
    if expires < current - skew:
        raise InvalidAssertion("assertion expired")
    if issued > current + skew:
        raise InvalidAssertion("assertion issued in the future")
    if expires - issued > lifetime:
        raise InvalidAssertion("assertion lifetime exceeds the configured window")

    nonce = claims["nonce"]
    if not isinstance(nonce, str) or not _NONCE_RE.match(nonce):
        raise InvalidAssertion("nonce must be 24 bytes of unpadded base64url")

    if method is not None and "method" in required_claims:
        signed_method = claims.get("method")
        if not isinstance(signed_method, str) or signed_method.upper() != method.upper():
            raise InvalidAssertion("assertion was signed for another method")
    if target is not None and claims["target"] != target:
        raise InvalidAssertion("assertion was signed for another target")

    _consume_nonce(audience, nonce, lifetime + skew)
    return dict(claims)
