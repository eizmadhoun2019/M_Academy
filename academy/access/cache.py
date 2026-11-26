"""Short-lived capability cache (``docs/configuration.md`` §2, ADR-012).

The cache stores the *resolved* answer, never the raw principal, and its key carries every
input that changes the answer: the authorization mode, the principal's role and department
fingerprint, and whether a suspension is active. A suspension therefore produces a new key on
the next request, so D-028's "denied on the next request" holds without an invalidation call.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from types import MappingProxyType
from typing import Any

from django.conf import settings
from django.core.cache import cache

from academy.authorization.core import Access, Capability, Grant, Principal, Scope, resolve_access


def _fingerprint(principal: Principal, grants: Sequence[Grant], mode: str) -> str:
    parts = [
        mode,
        principal.user_ref,
        str(principal.organization_id),
        str(principal.membership_id or ""),
        "1" if principal.is_active else "0",
        "1" if principal.suspended else "0",
        ",".join(sorted(principal.roles)),
        ",".join(sorted(principal.department_refs)),
        ";".join(
            f"{grant.capability}:{grant.scope_type}:{grant.scope_ref or ''}:"
            f"{grant.expires_at.isoformat() if grant.expires_at else ''}:"
            f"{'revoked' if grant.revoked_at else 'live'}"
            for grant in grants
        ),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def cache_key(principal: Principal, grants: Sequence[Grant], mode: str) -> str:
    return f"macademy:access:{_fingerprint(principal, grants, mode)}"


def _encode(access: Access) -> dict[str, Any]:
    return {
        "denied_reason": access.denied_reason,
        "capabilities": {
            str(capability): [scope.all_departments, sorted(scope.departments)]
            for capability, scope in access.capabilities.items()
        },
    }


def _decode(principal: Principal, state: dict[str, Any]) -> Access:
    capabilities = {
        Capability(capability): Scope(
            all_departments=bool(value[0]), departments=frozenset(value[1])
        )
        for capability, value in state["capabilities"].items()
    }
    return Access(
        principal=principal,
        capabilities=MappingProxyType(capabilities),
        denied_reason=state["denied_reason"],
    )


def cached_access(
    principal: Principal, grants: Sequence[Grant] = (), *, mode: str | None = None
) -> Access:
    """Resolve once per fingerprint, or reuse the answer stored within the TTL."""
    resolved_mode = mode or str(getattr(settings, "ACADEMY_AUTHORIZATION_MODE", "role_plus_grants"))
    key = cache_key(principal, grants, resolved_mode)
    state = cache.get(key)
    if isinstance(state, dict):
        return _decode(principal, state)
    access = resolve_access(principal, grants, mode=resolved_mode)
    cache.set(key, _encode(access), timeout=int(getattr(settings, "ACADEMY_CACHE_TTL_SECONDS", 60)))
    return access
