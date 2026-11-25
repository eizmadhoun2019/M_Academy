"""T-016 acceptance: permission grants, enforcement and the last-admin guard.

The service is tested without HTTP (REQ-13's matrix), then the administration API is exercised
in ``grants_only`` — H1's production mode (D-027) — where a Hub role alone grants nothing.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import Client, override_settings
from django.utils import timezone

from academy.api.grants import GrantSerializer
from academy.authorization.core import Access, Capability, Principal, resolve_access
from academy.exceptions import Conflict, LastAdmin
from academy.grants.service import grant, grants_for, revoke
from academy.models import AccessSuspension, AuditEvent, PermissionGrant
from host_hub.fake import DEFAULT_KID, sign_identity

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
OTHER_ORG = UUID("2f5e3d1a-0c4b-4a8e-9f2d-6b7c8d9e0f11")
SECRET = "test-identity-secret-that-is-at-least-32-bytes"
KID = DEFAULT_KID
GRANTS = "/api/v1/academy/manage/grants/"
CAPABILITIES = "/api/v1/academy/me/capabilities/"

HUB = dict(
    ACADEMY_ACCESS_MODE="hub",
    ACADEMY_HUB_IDENTITY_KEYS={KID: SECRET},
    ACADEMY_HUB_WEBHOOK_KEYS={KID: SECRET},
    ACADEMY_AUTHORIZATION_MODE="grants_only",
)


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    cache.clear()


def call(
    client: Client,
    method: str,
    path: str,
    *,
    user_ref: str = "u-admin",
    role: str = "employee",
    body: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    settings: dict[str, Any] | None = None,
) -> Any:
    token = sign_identity(
        method=method,
        target=path,
        organization_id=ORG,
        user_ref=user_ref,
        role=role,
        kid=KID,
        secret=SECRET,
    )
    extra: dict[str, Any] = {"HTTP_X_MASHEED_IDENTITY": token}
    if idempotency_key:
        extra["HTTP_IDEMPOTENCY_KEY"] = idempotency_key
    payload = json.dumps(body) if body is not None else None
    with override_settings(**{**HUB, **(settings or {})}):
        if method == "POST":
            return client.post(path, data=payload, content_type="application/json", **extra)
        if method == "DELETE":
            return client.delete(path, **extra)
        return client.get(path, **extra)


def admin_grant(user_ref: str = "u-admin", **overrides: Any) -> PermissionGrant:
    values: dict[str, Any] = {
        "organization_id": ORG,
        "user_ref": user_ref,
        "capability": "admin",
        "scope_type": "organization",
        "granted_by_ref": "system",
    }
    values.update(overrides)
    return PermissionGrant.objects.create(**values)


def test_grant_records_audit_in_the_same_call(db: Any) -> None:
    row = grant(
        organization_id=ORG,
        actor_ref="u-admin",
        user_ref="u-42",
        capability="academy.manage_content",
        scope_type="department",
        scope_ref="dep-1",
    )
    assert row.capability == "manage_content"
    event = AuditEvent.objects.get(action="grant.created")
    assert event.object_id == str(row.pk)
    assert event.actor_ref == "u-admin"


def test_a_duplicate_live_grant_is_a_conflict(db: Any) -> None:
    grant(
        organization_id=ORG,
        actor_ref="u-admin",
        user_ref="u-42",
        capability="academy.assign",
        scope_type="organization",
    )
    with pytest.raises(Conflict):
        grant(
            organization_id=ORG,
            actor_ref="u-admin",
            user_ref="u-42",
            capability="academy.assign",
            scope_type="organization",
        )


def test_a_scope_shape_is_enforced(db: Any) -> None:
    with pytest.raises(Conflict):
        grant(
            organization_id=ORG,
            actor_ref="u-admin",
            user_ref="u-42",
            capability="academy.assign",
            scope_type="department",
        )
    with pytest.raises(Conflict):
        grant(
            organization_id=ORG,
            actor_ref="u-admin",
            user_ref="u-42",
            capability="academy.assign",
            scope_type="organization",
            scope_ref="dep-1",
        )


def test_revocation_keeps_the_row_and_blocks_a_re_grant_of_the_same_scope(db: Any) -> None:
    row = grant(
        organization_id=ORG,
        actor_ref="u-admin",
        user_ref="u-42",
        capability="academy.view_reports",
        scope_type="organization",
    )
    admin_grant()
    revoked = revoke(organization_id=ORG, actor_ref="u-admin", grant_id=row.pk)
    assert revoked.revoked_at is not None
    assert revoked.revoked_by_ref == "u-admin"
    assert grants_for(ORG, "u-42") == []
    again = grant(
        organization_id=ORG,
        actor_ref="u-admin",
        user_ref="u-42",
        capability="academy.view_reports",
        scope_type="organization",
    )
    assert again.pk != row.pk


def test_an_expired_grant_is_ineffective(db: Any) -> None:
    grant(
        organization_id=ORG,
        actor_ref="u-admin",
        user_ref="u-42",
        capability="academy.manage_content",
        scope_type="organization",
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    assert grants_for(ORG, "u-42") == []


def test_the_last_active_admin_cannot_be_revoked(db: Any) -> None:
    row = admin_grant()
    with pytest.raises(LastAdmin):
        revoke(organization_id=ORG, actor_ref="u-admin", grant_id=row.pk)
    assert PermissionGrant.objects.get(pk=row.pk).revoked_at is None


def test_the_last_admin_guard_counts_only_live_admins(db: Any) -> None:
    first = admin_grant("u-admin")
    admin_grant("u-second")
    revoke(organization_id=ORG, actor_ref="u-admin", grant_id=first.pk)
    second = PermissionGrant.objects.get(user_ref="u-second")
    with pytest.raises(LastAdmin):
        revoke(organization_id=ORG, actor_ref="u-admin", grant_id=second.pk)


def test_a_suspended_user_keeps_the_grants_but_loses_the_capability(db: Any) -> None:
    row = grant(
        organization_id=ORG,
        actor_ref="u-admin",
        user_ref="u-42",
        capability="academy.manage_content",
        scope_type="organization",
    )
    AccessSuspension.objects.create(
        organization_id=ORG,
        user_ref="u-42",
        reason="Policy review",
        suspended_by_ref="u-admin",
    )
    principal = Principal(
        user_ref="u-42", organization_id=ORG, roles=frozenset({"employee"}), suspended=True
    )
    assert resolve_access(principal, grants_for(ORG, "u-42")).capabilities == {}
    assert PermissionGrant.objects.get(pk=row.pk).revoked_at is None


def test_provision_admin_creates_once_and_refuses_a_second_run(db: Any) -> None:
    call_command("provision_admin", "--user-ref", "u-admin", verbosity=0)
    assert PermissionGrant.objects.get(user_ref="u-admin").capability == "admin"
    with pytest.raises(CommandError):
        call_command("provision_admin", "--user-ref", "u-other", verbosity=0)


def test_an_admin_can_grant_and_the_grant_takes_effect(db: Any) -> None:
    admin_grant()
    response = call(
        Client(),
        "POST",
        GRANTS,
        body={
            "user_ref": "u-42",
            "capability": "academy.manage_content",
            "scope_type": "department",
            "scope_ref": "dep-1",
        },
    )
    assert response.status_code == 201
    assert response.json()["state"] == "active"
    with override_settings(ACADEMY_AUTHORIZATION_MODE="grants_only"):
        capabilities = call(Client(), "GET", CAPABILITIES, user_ref="u-42").json()["capabilities"]
    assert {
        "capability": "academy.manage_content",
        "scope_type": "department",
        "departments": ["dep-1"],
    } in capabilities


def test_a_hub_role_alone_grants_nothing_in_grants_only(db: Any) -> None:
    response = call(
        Client(),
        "POST",
        GRANTS,
        role="platform_admin",
        body={
            "user_ref": "u-42",
            "capability": "academy.assign",
            "scope_type": "organization",
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_the_list_filters_and_paginates(db: Any) -> None:
    admin_grant()
    grant(
        organization_id=ORG,
        actor_ref="u-admin",
        user_ref="u-42",
        capability="academy.assign",
        scope_type="organization",
    )
    response = call(Client(), "GET", GRANTS + "?user_ref=u-42&state=active")
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["user_ref"] == "u-42"
    assert body["results"][0]["capability"] == "assign"


def test_the_api_refuses_to_revoke_the_last_admin(db: Any) -> None:
    row = admin_grant()
    response = call(Client(), "DELETE", f"{GRANTS}{row.pk}/")
    assert response.status_code == 409
    assert response.json()["code"] == "last_admin"


def test_revocation_through_the_api_is_audited(db: Any) -> None:
    admin_grant()
    row = PermissionGrant.objects.create(
        organization_id=ORG,
        user_ref="u-42",
        capability="assign",
        scope_type="organization",
        granted_by_ref="u-admin",
    )
    response = call(Client(), "DELETE", f"{GRANTS}{row.pk}/")
    assert response.status_code == 200
    assert response.json()["state"] == "revoked"
    assert AuditEvent.objects.filter(action="grant.revoked", object_id=str(row.pk)).exists()


def test_a_suspended_admin_is_denied_even_with_the_grant(db: Any) -> None:
    admin_grant()
    AccessSuspension.objects.create(
        organization_id=ORG,
        user_ref="u-admin",
        reason="Policy review",
        suspended_by_ref="u-super",
    )
    response = call(Client(), "GET", GRANTS)
    assert response.status_code == 403
    assert response.json()["code"] == "access_suspended"
    assert PermissionGrant.objects.filter(user_ref="u-admin", revoked_at__isnull=True).exists()


def test_a_grant_in_another_tenant_is_not_reachable(db: Any) -> None:
    admin_grant()
    other = PermissionGrant.objects.create(
        organization_id=OTHER_ORG,
        user_ref="u-42",
        capability="assign",
        scope_type="organization",
        granted_by_ref="u-admin",
    )
    assert call(Client(), "DELETE", f"{GRANTS}{other.pk}/").status_code == 404


def test_idempotency_repeats_return_the_same_grant(db: Any) -> None:
    admin_grant()
    body = {
        "user_ref": "u-42",
        "capability": "academy.assign",
        "scope_type": "organization",
    }
    first = call(Client(), "POST", GRANTS, body=body, idempotency_key="grant-1")
    second = call(Client(), "POST", GRANTS, body=body, idempotency_key="grant-1")
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert PermissionGrant.objects.filter(user_ref="u-42").count() == 1


def test_idempotency_conflicts_when_the_body_changes(db: Any) -> None:
    admin_grant()
    body = {
        "user_ref": "u-42",
        "capability": "academy.assign",
        "scope_type": "organization",
    }
    call(Client(), "POST", GRANTS, body=body, idempotency_key="grant-2")
    changed = dict(body, capability="academy.view_reports")
    response = call(Client(), "POST", GRANTS, body=changed, idempotency_key="grant-2")
    assert response.status_code == 409


def test_an_invalid_grant_body_is_400_with_fields(db: Any) -> None:
    admin_grant()
    response = call(
        Client(),
        "POST",
        GRANTS,
        body={"user_ref": "u 42", "capability": "academy.assign", "scope_type": "organization"},
    )
    assert response.status_code == 400
    assert "user_ref" in response.json()["fields"]


def test_the_serializer_reports_expired_and_revoked_states() -> None:
    row = PermissionGrant(
        id=uuid4(),
        organization_id=ORG,
        user_ref="u-42",
        capability="assign",
        scope_type="organization",
        granted_by_ref="u-admin",
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    assert GrantSerializer(row).data["state"] == "expired"
    row.revoked_at = timezone.now()
    row.revoked_by_ref = "u-admin"
    assert GrantSerializer(row).data["state"] == "revoked"


def test_grants_reach_the_access_object_of_the_middleware(db: Any, client: Client) -> None:
    admin_grant("u-42")
    response = call(client, "GET", CAPABILITIES, user_ref="u-42")
    capabilities = {item["capability"] for item in response.json()["capabilities"]}
    assert "academy.admin" in capabilities


def test_the_access_object_has_no_capability_without_a_grant(db: Any) -> None:
    access = resolve_access(
        Principal(user_ref="u-42", organization_id=ORG, roles=frozenset({"employee"})),
        [],
        mode="grants_only",
    )
    assert isinstance(access, Access)
    assert Capability.ADMIN not in access.capabilities
