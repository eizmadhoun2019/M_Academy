"""T-011 acceptance: the API conventions and the schema of the skeleton.

The envelope, the 401 without identity, the pagination defaults and the capability payload are
part of the contract in ``docs/api.md`` §1 and §3; the schema test keeps the documented route in
the generated OpenAPI document.
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from django.http import Http404
from django.test import Client
from drf_spectacular.generators import SchemaGenerator
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from academy.api.errors import academy_exception_handler
from academy.api.pagination import AcademyPagination
from academy.api.views import MeCapabilitiesView
from academy.authorization import Grant, Principal, resolve_access
from academy.exceptions import AccessSuspended, Forbidden, NotFound

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")


def principal(**overrides: Any) -> Principal:
    values: dict[str, Any] = {
        "user_ref": "u-20",
        "organization_id": ORG,
        "roles": frozenset({"employee"}),
        "department_refs": frozenset({"dep-1"}),
    }
    values.update(overrides)
    return Principal(**values)


def test_the_api_root_requires_an_identity() -> None:
    response = Client().get("/api/v1/academy/me/capabilities/")

    assert response.status_code == 401
    assert response.json() == {
        "code": "unauthorized",
        "detail": "no verified Academy identity",
        "fields": {},
    }


def test_the_capabilities_route_answers_from_the_resolved_access() -> None:
    grant = Grant(capability="academy.view_reports", scope_type="department", scope_ref="dep-1")
    access = resolve_access(principal(), [grant], mode="grants_only")
    request = APIRequestFactory().get("/api/v1/academy/me/capabilities/")
    request.academy_access = access

    response = MeCapabilitiesView.as_view()(request)

    assert response.status_code == 200
    assert response["Cache-Control"] == "private, no-store"
    body = response.data
    assert body["user_ref"] == "u-20"
    assert body["organization_id"] == ORG
    assert {"capability": "academy.learn", "scope_type": "organization"} in body["capabilities"]
    assert {
        "capability": "academy.view_reports",
        "scope_type": "department",
        "departments": ["dep-1"],
    } in body["capabilities"]


def test_the_schema_documents_the_versioned_route() -> None:
    schema = SchemaGenerator().get_schema(request=None, public=True)

    assert "/api/v1/academy/me/capabilities/" in schema["paths"]
    assert "Capabilities" in schema["components"]["schemas"]


def test_the_error_envelope_carries_code_detail_and_fields() -> None:
    forbidden = academy_exception_handler(Forbidden("nope"), {})
    not_found = academy_exception_handler(NotFound("gone"), {})
    suspended = academy_exception_handler(AccessSuspended("stopped"), {})
    missing = academy_exception_handler(Http404("gone"), {})

    assert forbidden is not None and forbidden.status_code == 403
    assert forbidden.data == {"code": "forbidden", "detail": "nope", "fields": {}}
    assert not_found is not None and not_found.status_code == 404
    assert suspended is not None and suspended.status_code == 403
    assert suspended.data["code"] == "access_suspended"
    assert missing is not None and missing.status_code == 404
    assert missing.data["code"] == "not_found"


def test_drf_failures_use_the_same_envelope() -> None:
    unauthenticated = academy_exception_handler(exceptions.NotAuthenticated("who"), {})
    denied = academy_exception_handler(exceptions.PermissionDenied("no"), {})
    invalid = academy_exception_handler(exceptions.ValidationError({"title": ["required"]}), {})

    assert unauthenticated is not None and unauthenticated.status_code == 401
    assert unauthenticated.data["code"] == "unauthorized"
    assert denied is not None and denied.data["code"] == "forbidden"
    assert invalid is not None and invalid.status_code == 400
    assert invalid.data["code"] == "validation_error"
    assert invalid.data["fields"] == {"title": ["required"]}


def test_an_unknown_failure_is_left_to_django() -> None:
    assert academy_exception_handler(RuntimeError("boom"), {}) is None


def test_pagination_matches_the_documented_limits() -> None:
    paginator = AcademyPagination()

    assert paginator.page_size == 25
    assert paginator.page_size_query_param == "page_size"
    assert paginator.max_page_size == 100


def test_the_view_serializes_an_organization_scope() -> None:
    access = resolve_access(principal(roles=frozenset({"platform_admin"})), mode="grants_only")
    request = APIRequestFactory().get("/api/v1/academy/me/capabilities/")
    request.academy_access = access

    response = cast(Response, MeCapabilitiesView.as_view()(request))
    capabilities = response.data["capabilities"]

    assert {"capability": "academy.learn", "scope_type": "organization"} in capabilities
