"""Turn a request into the :class:`Principal` the authorization layer resolves.

Two documented modes (``docs/configuration.md`` §1, D-026):

``hub``
    The request carries claims that a verified Hub assertion produced. Signature, issuer,
    audience, freshness, route binding and the nonce check belong to T-015; this module only
    maps validated claims and rejects another organization.
``standalone``
    A Django database session holds the signed-in local identity. Nothing about capabilities
    is stored in it: the session names the user, and every request resolves access again.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest

from academy.authorization.core import Principal

ACCESS_MODES = ("hub", "standalone")
ROLES = ("employee", "department_manager", "platform_admin")

#: Where the standalone sign-in keeps the identity. A capability never lives here.
SESSION_KEY = "academy_identity"


def access_mode() -> str:
    """The configured mode, validated where it is used."""
    mode = str(getattr(settings, "ACADEMY_ACCESS_MODE", "hub"))
    if mode not in ACCESS_MODES:
        raise ImproperlyConfigured(
            f"ACADEMY_ACCESS_MODE must be one of {ACCESS_MODES}, got {mode!r}"
        )
    return mode


def organization_id() -> UUID:
    """The one organization this deployment serves (D-026)."""
    value = getattr(settings, "ACADEMY_ORGANIZATION_ID", "")
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as error:
        raise ImproperlyConfigured(
            "ACADEMY_ORGANIZATION_ID must be the agreed organization UUID"
        ) from error


def principal_from_session(request: HttpRequest) -> Principal | None:
    data = request.session.get(SESSION_KEY)
    if not isinstance(data, dict) or not data.get("user_ref"):
        return None
    roles = frozenset(role for role in data.get("roles", ()) if role in ROLES)
    return Principal(
        user_ref=str(data["user_ref"]),
        organization_id=organization_id(),
        roles=roles,
        department_refs=frozenset(str(ref) for ref in data.get("department_refs", ()) if ref),
        is_active=bool(data.get("is_active", True)),
    )


def principal_from_claims(claims: Mapping[str, Any] | None) -> Principal | None:
    """Map already-verified claims, or ``None`` when they are absent or another tenant."""
    if not isinstance(claims, Mapping):
        return None
    user_ref = claims.get("user_ref")
    if not isinstance(user_ref, str) or not user_ref:
        return None
    try:
        claim_org = UUID(str(claims.get("organization_id")))
    except (TypeError, ValueError):
        return None
    if claim_org != organization_id():
        return None
    role = claims.get("role")
    roles = frozenset([role]) if role in ROLES else frozenset()
    refs = claims.get("department_refs")
    departments = (
        frozenset(str(ref) for ref in refs if ref) if isinstance(refs, list) else frozenset()
    )
    return Principal(
        user_ref=user_ref,
        organization_id=claim_org,
        roles=roles,
        department_refs=departments,
        is_active=bool(claims.get("is_active", False)),
    )


def current_principal(request: HttpRequest) -> Principal | None:
    """Resolve the caller according to the configured access mode."""
    if access_mode() == "standalone":
        return principal_from_session(request)
    return principal_from_claims(getattr(request, "academy_identity", None))
