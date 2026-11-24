"""T-009 acceptance: the allow/deny/scope matrix of ``CHARTER.md`` §3.1.

The matrix is exercised without a view or a database row: one principal, the grants T-016 will
read, and the two documented modes. ``grants_only`` is the H1 production mode, so it gets the
negative cases that prove Hub roles grant nothing on their own.
"""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse, HttpResponseBase
from django.test import override_settings
from django.utils import timezone

from academy.authorization import (
    Access,
    Capability,
    Grant,
    Principal,
    Scope,
    authorization_mode,
    resolve_access,
    role_capabilities,
)
from academy.authorization.django import AcademyPermission, CapabilityRequiredMixin
from academy.exceptions import AccessSuspended, Forbidden, InactiveAccount

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


def manager() -> Principal:
    return principal(roles=frozenset({"department_manager"}), department_refs=frozenset({"dep-1"}))


def admin() -> Principal:
    return principal(roles=frozenset({"platform_admin"}), department_refs=frozenset({"dep-1"}))


def test_the_default_mode_is_the_compatibility_union() -> None:
    assert authorization_mode() == "role_plus_grants"


def test_an_unknown_mode_is_a_configuration_error() -> None:
    with (
        override_settings(ACADEMY_AUTHORIZATION_MODE="everyone_is_admin"),
        pytest.raises(ImproperlyConfigured),
    ):
        authorization_mode()


def test_an_employee_learns_but_manages_nothing_in_role_mode() -> None:
    access = resolve_access(principal(), mode="role_plus_grants")

    assert access.allows(Capability.LEARN)
    assert not access.allows(Capability.MANAGE_CONTENT)
    with pytest.raises(Forbidden):
        access.require(Capability.ASSIGN)


def test_a_department_manager_is_scoped_to_their_departments() -> None:
    access = resolve_access(manager(), mode="role_plus_grants")

    assert access.allows(Capability.MANAGE_CONTENT, department_ref="dep-1")
    assert not access.allows(Capability.MANAGE_CONTENT, department_ref="dep-2")
    assert not access.allows(Capability.MANAGE_CONTENT, department_ref=None)
    assert access.allows(Capability.VIEW_REPORTS, department_ref="dep-1")
    assert not access.allows(Capability.ADMIN)


def test_a_manager_without_departments_covers_none() -> None:
    access = resolve_access(
        principal(roles=frozenset({"department_manager"}), department_refs=frozenset()),
        mode="role_plus_grants",
    )

    assert access.allows(Capability.LEARN)
    assert not access.allows(Capability.MANAGE_CONTENT, department_ref="dep-1")


def test_a_platform_admin_covers_the_organization() -> None:
    access = resolve_access(admin(), mode="role_plus_grants")

    for capability in Capability:
        assert access.allows(capability, department_ref="dep-9"), capability
    access.require_organization_wide(Capability.ADMIN)


def test_a_department_scope_cannot_write_organization_wide() -> None:
    access = resolve_access(manager(), mode="role_plus_grants")

    with pytest.raises(Forbidden):
        access.require_organization_wide(Capability.ASSIGN)


def test_grants_only_ignores_hub_roles() -> None:
    access = resolve_access(manager(), mode="grants_only")

    assert access.allows(Capability.LEARN)
    assert not access.allows(Capability.MANAGE_CONTENT, department_ref="dep-1")
    assert not access.allows(Capability.ADMIN)
    assert resolve_access(admin(), mode="grants_only").allows(Capability.ADMIN) is False


def test_a_department_grant_adds_its_capability_only_for_that_department() -> None:
    grant = Grant(capability=Capability.MANAGE_CONTENT, scope_type="department", scope_ref="dep-1")

    access = resolve_access(manager(), [grant], mode="grants_only")

    assert access.allows(Capability.MANAGE_CONTENT, department_ref="dep-1")
    assert not access.allows(Capability.MANAGE_CONTENT, department_ref="dep-2")
    assert not access.allows(Capability.ASSIGN, department_ref="dep-1")


def test_an_organization_grant_covers_every_department() -> None:
    grant = Grant(capability=Capability.ADMIN, scope_type="organization")

    access = resolve_access(principal(), [grant], mode="grants_only")

    assert access.allows(Capability.ADMIN, department_ref="dep-9")
    access.require_organization_wide(Capability.ADMIN)


def test_two_grants_union_their_scope() -> None:
    grants = [
        Grant(capability=Capability.VIEW_REPORTS, scope_type="department", scope_ref="dep-1"),
        Grant(capability=Capability.VIEW_REPORTS, scope_type="department", scope_ref="dep-2"),
    ]

    access = resolve_access(principal(), grants, mode="grants_only")

    assert access.allows(Capability.VIEW_REPORTS, department_ref="dep-1")
    assert access.allows(Capability.VIEW_REPORTS, department_ref="dep-2")
    assert not access.allows(Capability.VIEW_REPORTS, department_ref="dep-3")


def test_an_expired_grant_grants_nothing() -> None:
    grant = Grant(
        capability=Capability.ASSIGN,
        scope_type="organization",
        expires_at=timezone.now() - timedelta(minutes=1),
    )

    access = resolve_access(principal(), [grant], mode="grants_only")

    assert not access.allows(Capability.ASSIGN)


def test_a_grant_expires_exactly_at_its_instant() -> None:
    now = timezone.now()
    grant = Grant(capability=Capability.ASSIGN, scope_type="organization", expires_at=now)

    assert not resolve_access(principal(), [grant], mode="grants_only", now=now).allows(
        Capability.ASSIGN
    )
    assert resolve_access(
        principal(), [grant], mode="grants_only", now=now - timedelta(seconds=1)
    ).allows(Capability.ASSIGN)


def test_a_revoked_grant_grants_nothing() -> None:
    grant = Grant(
        capability=Capability.ADMIN,
        scope_type="organization",
        revoked_at=timezone.now(),
    )

    assert not resolve_access(principal(), [grant], mode="grants_only").allows(Capability.ADMIN)


def test_an_unknown_granted_capability_is_a_bug_not_a_silent_allow() -> None:
    grant = Grant(capability="academy.superuser", scope_type="organization")

    with pytest.raises(ValueError, match="academy.superuser"):
        resolve_access(principal(), [grant], mode="grants_only")


def test_a_suspension_blocks_every_capability() -> None:
    access = resolve_access(principal(suspended=True), mode="grants_only")

    assert not access.allows(Capability.LEARN)
    with pytest.raises(AccessSuspended):
        access.require(Capability.LEARN)


def test_an_inactive_member_is_denied_before_any_grant() -> None:
    access = resolve_access(principal(is_active=False), mode="grants_only")

    assert not access.allows(Capability.LEARN)
    with pytest.raises(InactiveAccount):
        access.require(Capability.LEARN)


def test_scope_covers_only_its_members() -> None:
    scope = Scope.for_departments(["dep-1", ""])

    assert scope.covers("dep-1")
    assert not scope.covers("dep-2")
    assert not scope.covers(None)
    assert Scope.everything().covers(None)
    assert (scope | Scope.for_departments(["dep-2"])).covers("dep-2")
    assert (scope | Scope.everything()).all_departments


def test_role_capabilities_exposes_the_documented_defaults() -> None:
    employee = role_capabilities(principal())

    assert set(employee) == {Capability.LEARN}
    assert Capability.ADMIN in role_capabilities(admin())


def test_the_drf_permission_reads_the_resolved_access() -> None:
    permission = AcademyPermission()
    view = SimpleNamespace(academy_capability=Capability.ADMIN)
    allowed = cast(
        Any, SimpleNamespace(academy_access=resolve_access(admin(), mode="role_plus_grants"))
    )
    denied = cast(
        Any, SimpleNamespace(academy_access=resolve_access(principal(), mode="grants_only"))
    )

    assert permission.has_permission(allowed, view) is True
    assert permission.has_permission(denied, view) is False
    # No resolved access on the request is a denial, never an implicit allow.
    assert permission.has_permission(cast(Any, SimpleNamespace()), view) is False
    # A view that declares no capability is denied.
    assert permission.has_permission(allowed, SimpleNamespace()) is False


class _BaseView:
    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        return HttpResponse("ok")


class _AdminView(CapabilityRequiredMixin, _BaseView):
    academy_capability = Capability.ADMIN


def test_the_web_mixin_denies_before_the_view_body() -> None:
    request: Any = SimpleNamespace(academy_access=resolve_access(principal(), mode="grants_only"))

    with pytest.raises(Forbidden):
        _AdminView().dispatch(request)


def test_the_web_mixin_allows_a_granted_capability() -> None:
    grant = Grant(capability=Capability.ADMIN, scope_type="organization")
    access: Access = resolve_access(principal(), [grant], mode="grants_only")
    request = cast(HttpRequest, SimpleNamespace(academy_access=access))

    assert _AdminView().dispatch(request).status_code == 200


def test_the_web_mixin_reports_a_missing_access_context() -> None:
    with pytest.raises(Forbidden, match="no resolved Academy access"):
        _AdminView().dispatch(cast(HttpRequest, SimpleNamespace()))
