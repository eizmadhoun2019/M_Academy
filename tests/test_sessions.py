"""T-014 acceptance: sessions, the access middleware, throttles and the suspension record.

The API never learns who the caller is from the session: the middleware resolves a
:class:`Principal` and the authorization layer decides. These tests cover both documented modes
(``hub`` claims and the standalone local sign-in) and the local suspension table (D-028).
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

import pytest
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory, override_settings
from django.utils import timezone

from academy.access import cache as access_cache
from academy.access.principals import (
    SESSION_KEY,
    current_principal,
    principal_from_claims,
    principal_from_session,
)
from academy.authorization.core import Access, Principal, resolve_access
from academy.models import AccessSuspension

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")

PREVIEW = "/academy/preview/ar/"
CAPABILITIES = "/api/v1/academy/me/capabilities/"


def capabilities(response: Any) -> dict[str, dict[str, Any]]:
    """The payload's list, keyed by capability name for readable assertions."""
    return {item["capability"]: item for item in response.json()["capabilities"]}


def error_code(response: Any) -> str:
    return str(response.json()["code"])


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    cache.clear()


def sign_in(
    client: Client,
    user_ref: str = "u-42",
    *,
    roles: tuple[str, ...] = ("employee",),
    departments: tuple[str, ...] = (),
    active: bool = True,
) -> None:
    session = client.session
    session[SESSION_KEY] = {
        "user_ref": user_ref,
        "roles": list(roles),
        "department_refs": list(departments),
        "is_active": active,
    }
    session.save()


def suspend(user_ref: str = "u-42", reason: str = "Policy review") -> AccessSuspension:
    return AccessSuspension.objects.create(
        organization_id=ORG,
        user_ref=user_ref,
        reason=reason,
        suspended_by_ref="u-admin",
    )


def test_the_session_names_the_user_and_never_the_capabilities() -> None:
    request = RequestFactory().get(PREVIEW)
    cast(Any, request).session = {"academy_identity": {"user_ref": "u-42", "roles": ["employee"]}}
    principal = principal_from_session(request)
    assert principal is not None
    assert principal.user_ref == "u-42"
    assert principal.organization_id == ORG
    assert principal.is_active is True


def test_a_session_without_identity_is_anonymous() -> None:
    request = RequestFactory().get(PREVIEW)
    cast(Any, request).session = {}
    assert principal_from_session(request) is None


def test_hub_claims_from_another_organization_are_rejected() -> None:
    claims = {
        "user_ref": "u-42",
        "organization_id": "00000000-0000-0000-0000-000000000001",
        "role": "employee",
        "is_active": True,
    }
    assert principal_from_claims(claims) is None


def test_hub_claims_map_role_and_departments() -> None:
    claims = {
        "user_ref": "u-42",
        "organization_id": str(ORG),
        "role": "department_manager",
        "department_refs": ["dep-1", ""],
        "is_active": True,
    }
    principal = principal_from_claims(claims)
    assert principal is not None
    assert principal.roles == frozenset({"department_manager"})
    assert principal.department_refs == frozenset({"dep-1"})


def test_the_middleware_publishes_one_access_object(db: Any) -> None:
    request = RequestFactory().get(PREVIEW)
    cast(Any, request).session = {"academy_identity": {"user_ref": "u-42", "roles": ["employee"]}}
    seen: dict[str, Any] = {}

    def view(inner: HttpRequest) -> HttpResponse:
        seen["access"] = inner.academy_access  # type: ignore[attr-defined]
        return HttpResponse("ok")

    from academy.access.middleware import AcademyAccessMiddleware

    response = AcademyAccessMiddleware(view)(request)
    assert response.status_code == 200
    assert isinstance(seen["access"], Access)
    assert seen["access"].principal.user_ref == "u-42"


def test_an_authenticated_request_reaches_the_api_with_capabilities(
    db: Any, client: Client
) -> None:
    sign_in(client)
    response = client.get(CAPABILITIES)
    assert response.status_code == 200
    assert "academy.learn" in capabilities(response)


def test_anonymous_api_requests_are_refused(client: Client) -> None:
    assert client.get(CAPABILITIES).status_code == 401


def test_a_suspended_user_is_denied_with_the_documented_code(db: Any, client: Client) -> None:
    sign_in(client)
    suspend()
    response = client.get(CAPABILITIES)
    assert response.status_code == 403
    assert error_code(response) == "access_suspended"
    page = client.get("/academy/library/")
    assert page.status_code == 403
    assert "تم إيقاف وصولك" in page.content.decode()


def test_a_suspension_after_a_cached_request_is_seen_on_the_next_one(
    db: Any, client: Client
) -> None:
    sign_in(client)
    assert client.get(CAPABILITIES).status_code == 200
    suspend()
    assert error_code(client.get(CAPABILITIES)) == "access_suspended"


def test_a_lifted_suspension_stops_blocking(db: Any, client: Client) -> None:
    sign_in(client)
    suspension = suspend()
    assert client.get(CAPABILITIES).status_code == 403
    suspension.lifted_at = timezone.now()
    suspension.lifted_by_ref = "u-admin"
    suspension.save()
    assert client.get(CAPABILITIES).status_code == 200


def test_an_inactive_member_gets_account_inactive(db: Any, client: Client) -> None:
    sign_in(client, active=False)
    response = client.get(CAPABILITIES)
    assert response.status_code == 403
    assert error_code(response) == "account_inactive"
    page = client.get("/academy/library/")
    assert page.status_code == 403
    assert "عضويتك غير نشطة" in page.content.decode()


def test_access_denied_screen_is_directly_reachable(db: Any, client: Client) -> None:
    assert client.get("/academy/access-denied/").status_code == 403


@override_settings(ACADEMY_AUTHORIZATION_MODE="grants_only")
def test_grants_only_gives_a_manager_no_administration(db: Any, client: Client) -> None:
    sign_in(client, roles=("department_manager",), departments=("dep-1",))
    response = client.get(CAPABILITIES)
    assert "academy.manage_content" not in capabilities(response)
    assert "academy.learn" in capabilities(response)


@override_settings(ACADEMY_AUTHORIZATION_MODE="role_plus_grants")
def test_role_plus_grants_scopes_a_manager_to_the_own_department(db: Any, client: Client) -> None:
    sign_in(client, roles=("department_manager",), departments=("dep-1",))
    scope = capabilities(client.get(CAPABILITIES))["academy.manage_content"]
    assert scope == {
        "capability": "academy.manage_content",
        "scope_type": "department",
        "departments": ["dep-1"],
    }


@override_settings(ACADEMY_AUTHORIZATION_MODE="role_plus_grants")
def test_a_role_change_applies_on_the_next_request(db: Any, client: Client) -> None:
    sign_in(client, roles=("department_manager",), departments=("dep-1",))
    assert "academy.manage_content" in capabilities(client.get(CAPABILITIES))
    sign_in(client, roles=("employee",), departments=("dep-1",))
    assert "academy.manage_content" not in capabilities(client.get(CAPABILITIES))


def test_the_cache_answers_the_same_fingerprint_once(db: Any, monkeypatch: Any) -> None:
    calls: list[str] = []
    real = access_cache.resolve_access

    def counting(principal: Principal, grants: Any = (), *, mode: str) -> Access:
        calls.append(principal.user_ref)
        return real(principal, grants, mode=mode)

    monkeypatch.setattr(access_cache, "resolve_access", counting)
    principal = Principal(user_ref="u-42", organization_id=ORG, roles=frozenset({"employee"}))
    access_cache.cached_access(principal)
    access_cache.cached_access(principal)
    assert calls == ["u-42"]


def test_the_login_form_is_unavailable_in_hub_mode(client: Client) -> None:
    with override_settings(ACADEMY_ACCESS_MODE="hub"):
        assert client.get("/academy/login/").status_code == 404
    with override_settings(DEVELOPMENT_LOGIN=False):
        assert client.get("/academy/login/").status_code == 404


def test_login_stores_identity_only(db: Any, client: Client) -> None:
    response = client.post(
        "/academy/login/",
        {"user_ref": "u-77", "password": "secret", "role": "employee", "department_ref": "dep-1"},
    )
    assert response.status_code == 302
    identity = client.session[SESSION_KEY]
    assert identity["user_ref"] == "u-77"
    assert identity["department_refs"] == ["dep-1"]
    assert "secret" not in str(dict(client.session))


def test_login_can_preview_the_inactive_screen(db: Any, client: Client) -> None:
    response = client.post(
        "/academy/login/",
        {"user_ref": "u-77", "password": "x", "role": "employee", "simulate_inactive": "on"},
    )
    assert response.status_code == 302
    page = client.get("/academy/library/")
    assert page.status_code == 403
    assert "عضويتك غير نشطة" in page.content.decode()


def test_login_rejects_a_malformed_user_reference(db: Any, client: Client) -> None:
    response = client.post("/academy/login/", {"user_ref": "u 77", "password": "x"})
    assert response.status_code == 200
    assert SESSION_KEY not in client.session


def test_login_is_throttled_at_ten_attempts(db: Any, client: Client) -> None:
    with override_settings(THROTTLES_ENABLED=True):
        for _ in range(10):
            assert (
                client.post("/academy/login/", {"user_ref": "u-1", "password": "x"}).status_code
                == 200
            )
        assert (
            client.post("/academy/login/", {"user_ref": "u-1", "password": "x"}).status_code == 429
        )


def test_logout_clears_the_session(db: Any, client: Client) -> None:
    sign_in(client)
    assert client.get(CAPABILITIES).status_code == 200
    assert client.get("/academy/logout/").status_code == 405
    assert client.post("/academy/logout/").status_code == 302
    assert SESSION_KEY not in client.session
    assert client.get(CAPABILITIES).status_code == 401


def test_a_second_active_suspension_is_refused(db: Any) -> None:
    suspend()
    with pytest.raises(IntegrityError), transaction.atomic():
        suspend(reason="Second reason")


def test_a_blank_reason_is_refused(db: Any) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        suspend(reason="   ")


def test_lifting_requires_its_actor(db: Any) -> None:
    suspension = suspend()
    suspension.lifted_at = timezone.now()
    with pytest.raises(IntegrityError), transaction.atomic():
        suspension.save()


def test_hub_mode_reads_claims_from_the_request(db: Any) -> None:
    request = RequestFactory().get(PREVIEW)
    cast(Any, request).session = {}
    request.academy_identity = {  # type: ignore[attr-defined]
        "user_ref": "u-42",
        "organization_id": str(ORG),
        "role": "employee",
        "is_active": True,
    }
    with override_settings(ACADEMY_ACCESS_MODE="hub"):
        principal = current_principal(request)
        assert principal is not None
        assert principal.user_ref == "u-42"
        assert resolve_access(principal).capabilities


def test_hub_mode_offers_no_local_sign_in_page(client: Client) -> None:
    with override_settings(ACADEMY_ACCESS_MODE="hub"):
        assert client.get("/academy/login/").status_code == 404
        assert client.post("/academy/logout/").status_code == 404
