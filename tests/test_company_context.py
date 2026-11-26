"""T-026 CP3 acceptance: the company comes from the membership, never from the caller.

The tests build two companies with identical shapes, give each account exactly one membership,
and prove that (a) the session cannot name or switch a company, (b) ``/me/organization`` answers
from the membership and ignores a company in the query or a header, and (c) an identifier from
the other company is a plain 404.
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from conftest import ORG_ID, OTHER_ORG_ID
from django.test import Client, RequestFactory
from django.utils import timezone
from factories import make_course

from academy.access.principals import SESSION_KEY, principal_from_session
from academy.access.tenancy import context_for_ref, context_for_session
from academy.models import Department, Membership, PermissionGrant, User

CAPABILITIES = "/api/v1/academy/me/capabilities/"
ORGANIZATION = "/api/v1/academy/me/organization/"


def _account(
    user_ref: str,
    *,
    organization_id: UUID = ORG_ID,
    status: str = Membership.Status.ACTIVE,
    department: Department | None = None,
) -> tuple[User, Membership]:
    user = User.objects.create(
        email=f"{user_ref}@example.com",
        display_name=user_ref,
        legacy_ref=user_ref,
        status=User.Status.ACTIVE,
    )
    membership = Membership.objects.create(
        organization_id=organization_id,
        user=user,
        status=status,
        joined_at=timezone.now() if status == Membership.Status.ACTIVE else None,
        removed_at=timezone.now() if status == Membership.Status.REMOVED else None,
        department=department,
    )
    return user, membership


def _sign_in(client: Client, user_ref: str, membership_id: UUID, **extra: Any) -> None:
    session = client.session
    session[SESSION_KEY] = {
        "user_ref": user_ref,
        "membership_id": str(membership_id),
        "roles": ["employee"],
        "is_active": True,
        **extra,
    }
    session.save()


def test_the_company_is_derived_from_the_single_membership(db: Any) -> None:
    _account("u-a", organization_id=ORG_ID)
    _account("u-b", organization_id=OTHER_ORG_ID)

    first = context_for_ref("u-a")
    second = context_for_ref("u-b")

    assert first is not None and first.organization_id == ORG_ID
    assert second is not None and second.organization_id == OTHER_ORG_ID


def test_an_account_without_a_membership_has_no_company(db: Any) -> None:
    User.objects.create(
        email="platform@example.com",
        display_name="Platform",
        legacy_ref="u-platform",
        status=User.Status.ACTIVE,
    )

    assert context_for_ref("u-platform") is None


def test_a_removed_membership_grants_no_company(db: Any) -> None:
    _account("u-removed", status=Membership.Status.REMOVED)

    assert context_for_ref("u-removed") is None


def test_a_tampered_membership_id_switches_nothing(db: Any) -> None:
    _, mine = _account("u-mine", organization_id=ORG_ID)
    _, theirs = _account("u-theirs", organization_id=OTHER_ORG_ID)

    assert context_for_session("u-mine", theirs.pk) is None
    assert context_for_session("u-mine", mine.pk) is not None


def test_an_unknown_account_resolves_no_company(db: Any) -> None:
    assert context_for_ref("u-never-imported") is None


def test_a_company_in_the_session_is_ignored(db: Any) -> None:
    _, membership = _account("u-a", organization_id=ORG_ID)
    request = RequestFactory().get("/api/v1/academy/me/capabilities/")
    cast(Any, request).session = {
        SESSION_KEY: {
            "user_ref": "u-a",
            "membership_id": str(membership.pk),
            "organization_id": str(OTHER_ORG_ID),
            "roles": ["employee"],
            "is_active": True,
        }
    }

    principal = principal_from_session(request)

    assert principal is not None
    assert principal.organization_id == ORG_ID
    assert principal.membership_id == membership.pk


def test_a_tampered_membership_id_is_refused(db: Any, client: Client) -> None:
    _account("u-mine", organization_id=ORG_ID)
    _, theirs = _account("u-theirs", organization_id=OTHER_ORG_ID)
    _sign_in(client, "u-mine", theirs.pk)

    assert client.get(CAPABILITIES).status_code == 401
    assert client.get(ORGANIZATION).status_code == 401


def test_me_organization_answers_from_the_membership(db: Any, client: Client) -> None:
    department = Department.objects.create(
        organization_id=ORG_ID, name_ar="التدريب", legacy_ref="dep-1"
    )
    _, membership = _account("u-a", organization_id=ORG_ID, department=department)
    _sign_in(client, "u-a", membership.pk)

    response = client.get(ORGANIZATION)

    assert response.status_code == 200
    assert response["Cache-Control"] == "private, no-store"
    body = response.json()
    assert body["organization"]["id"] == str(ORG_ID)
    assert body["organization"]["slug"] == "masheed"
    assert body["membership"]["id"] == str(membership.pk)
    assert body["membership"]["department"] == {
        "id": str(department.pk),
        "name_ar": "التدريب",
    }


def test_me_organization_ignores_a_company_in_the_query_or_header(db: Any, client: Client) -> None:
    _, membership = _account("u-a", organization_id=ORG_ID)
    _sign_in(client, "u-a", membership.pk)

    response = client.get(
        ORGANIZATION,
        {"organization_id": str(OTHER_ORG_ID)},
        HTTP_X_ORGANIZATION_ID=str(OTHER_ORG_ID),
    )

    assert response.status_code == 200
    assert response.json()["organization"]["id"] == str(ORG_ID)


def test_two_members_read_only_their_own_company(db: Any, client: Client) -> None:
    _, mine = _account("u-a", organization_id=ORG_ID)
    _sign_in(client, "u-a", mine.pk)
    assert client.get(ORGANIZATION).json()["organization"]["id"] == str(ORG_ID)

    _, theirs = _account("u-b", organization_id=OTHER_ORG_ID)
    _sign_in(client, "u-b", theirs.pk)
    assert client.get(ORGANIZATION).json()["organization"]["id"] == str(OTHER_ORG_ID)


def test_a_platform_only_account_is_membership_inactive(db: Any, client: Client) -> None:
    user = User.objects.create(
        email="platform@example.com",
        display_name="Platform",
        legacy_ref="u-platform",
        status=User.Status.ACTIVE,
    )
    session = client.session
    session[SESSION_KEY] = {"user_ref": user.legacy_ref, "roles": ["employee"], "is_active": True}
    session.save()

    response = client.get(ORGANIZATION)

    assert response.status_code == 403
    assert response.json()["code"] == "membership_inactive"


def test_another_companys_course_is_not_found(db: Any, client: Client) -> None:
    mine = make_course(ORG_ID, title="Mine", owner_department_ref="dep-1")
    theirs = make_course(OTHER_ORG_ID, title="Theirs", owner_department_ref="dep-1")
    _, membership = _account("u-b", organization_id=OTHER_ORG_ID)
    PermissionGrant.objects.create(
        organization_id=OTHER_ORG_ID,
        user_ref="u-b",
        capability=PermissionGrant.Capability.MANAGE_CONTENT,
        scope_type=PermissionGrant.Scope.DEPARTMENT,
        scope_ref="dep-1",
        granted_by_ref="u-admin",
    )
    _sign_in(client, "u-b", membership.pk)

    own = client.get(f"/api/v1/academy/manage/courses/{theirs.pk}/")
    foreign = client.get(f"/api/v1/academy/manage/courses/{mine.pk}/")

    assert own.status_code == 200
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "not_found"


def test_an_unauthenticated_request_has_no_company(client: Client) -> None:
    assert client.get(ORGANIZATION).status_code == 401
