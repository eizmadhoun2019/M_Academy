"""Browser identity from the Hub proxy — ``docs/hub-contract.md`` §1 and §2."""

from __future__ import annotations

from typing import Any, cast

from django.conf import settings
from django.http import HttpRequest

from academy.access.principals import ROLES, access_mode
from academy.hub.assertions import InvalidAssertion, verify

MAX_DEPARTMENT_REFS = 50
MAX_REF_LENGTH = 64
MAX_DISPLAY_NAME = 200
LANGUAGES = ("ar", "en")


def _identity_header(request: HttpRequest) -> str:
    name = str(settings.ACADEMY_HUB_IDENTITY_HEADER)
    return str(request.META.get("HTTP_" + name.upper().replace("-", "_"), ""))


def request_target(request: HttpRequest) -> str:
    """The signed target: decoded path plus the original query string, unchanged."""
    query = request.META.get("QUERY_STRING", "")
    return f"{request.path_info}?{query}" if query else request.path_info


def validate_claims(claims: dict[str, Any]) -> dict[str, Any]:
    """Reject a verified token whose claim *shapes* the contract does not allow."""
    user_ref = claims.get("user_ref")
    if not isinstance(user_ref, str) or not user_ref or len(user_ref) > MAX_REF_LENGTH:
        raise InvalidAssertion("user_ref must be a non-empty reference of at most 64 characters")
    display_name = claims.get("display_name")
    if (
        not isinstance(display_name, str)
        or not display_name
        or len(display_name) > MAX_DISPLAY_NAME
    ):
        raise InvalidAssertion("display_name must be 1-200 characters")
    if claims.get("language") not in LANGUAGES:
        raise InvalidAssertion("language must be ar or en")
    if claims.get("role") not in ROLES:
        raise InvalidAssertion("role must be platform_admin, department_manager or employee")
    refs = claims.get("department_refs")
    if not isinstance(refs, list) or len(refs) > MAX_DEPARTMENT_REFS:
        raise InvalidAssertion("department_refs must be a list of at most 50 references")
    for ref in refs:
        if not isinstance(ref, str) or not ref or len(ref) > MAX_REF_LENGTH:
            raise InvalidAssertion("department references must be 1-64 characters")
    if not isinstance(claims.get("is_active"), bool):
        raise InvalidAssertion("is_active must be a boolean")
    return claims


def claims_from_request(request: HttpRequest) -> dict[str, Any] | None:
    """Verified claims for this request, or ``None`` when the identity is absent or invalid."""
    token = _identity_header(request)
    if not token:
        return None
    try:
        claims = verify(
            token,
            keys=settings.ACADEMY_HUB_IDENTITY_KEYS,
            issuer=settings.ACADEMY_HUB_ISSUER,
            audience=settings.ACADEMY_HUB_AUDIENCE,
            lifetime=settings.ACADEMY_HUB_ASSERTION_TTL,
            skew=settings.ACADEMY_HUB_CLOCK_SKEW,
            method=request.method,
            target=request_target(request),
        )
        return validate_claims(claims)
    except InvalidAssertion:
        return None


class HubIdentityMiddleware:
    """In ``hub`` mode the proxy's assertion *is* the identity; nothing else is trusted."""

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> Any:
        if access_mode() == "hub":
            claims = claims_from_request(request)
            if claims is not None:
                cast(Any, request).academy_identity = claims
        return self.get_response(request)
