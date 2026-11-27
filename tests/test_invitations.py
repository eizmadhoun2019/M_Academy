"""T-027 CP2 acceptance: company invitations (``docs/security.md`` §2, ``docs/api.md`` §3).

An invitation binds one address to one company, department and role set; the token is hashed,
single-use and seven days long; re-inviting retires the previous token; acceptance creates or
reactivates the account and its single membership, and an address that already belongs to a
company is refused with ``already_member`` instead of gaining a second membership (D-043).
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from django.core import mail
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from academy.access import invitations
from academy.exceptions import (
    AlreadyMember,
    DomainValidationError,
    InvitationInvalid,
    NotFound,
)
from academy.models import Department, Invitation, Membership, Organization, User

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
OTHER_ORG = UUID("2f5e3d1a-0c4b-4a8e-9f2d-6b7c8d9e0f11")
ACCEPT = "/api/v1/academy/auth/invitations/accept/"
LOGIN = "/api/v1/academy/auth/login/"
PASSWORD = "Correct-Horse-Battery-7"
TOKEN_IN_MAIL = re.compile(r"token=([A-Za-z0-9_\-]+)")


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    cache.clear()


@pytest.fixture
def org(db: Any) -> Organization:
    row, _ = Organization.objects.get_or_create(
        id=ORG, defaults={"name_ar": "Masheed Academy", "slug": "masheed"}
    )
    return row


def other_organization() -> Organization:
    row, _ = Organization.objects.get_or_create(
        id=OTHER_ORG, defaults={"name_ar": "Other Company", "slug": "other"}
    )
    return row


def new_account(email: str | None = None, **overrides: Any) -> User:
    account = User.objects.create(
        email=email or f"account-{uuid4()}@example.com",
        display_name="Account",
        status=User.Status.ACTIVE,
        is_email_verified=True,
    )
    for field, value in overrides.items():
        setattr(account, field, value)
    account.save()
    return account


def invite(email: str = "invitee@example.com", roles: tuple[str, ...] = ("employee",)) -> str:
    department = Department.objects.create(
        organization_id=ORG, name_ar=f"التدريب {uuid4().hex[:8]}"
    )
    inviter = Membership.objects.create(
        organization_id=ORG,
        user=new_account(),
        status=Membership.Status.ACTIVE,
        joined_at=timezone.now(),
    )
    _, raw = invitations.invite(
        organization_id=ORG,
        email=email,
        roles=roles,
        department=department,
        invited_by=inviter,
    )
    return raw


def mailed_token() -> str:
    match = TOKEN_IN_MAIL.search(str(mail.outbox[-1].body))
    assert match is not None
    return match.group(1)


def accept(client: Client, token: str, **overrides: Any) -> Any:
    payload: dict[str, Any] = {
        "token": token,
        "password": PASSWORD,
        "display_name": "New Learner",
    }
    payload.update(overrides)
    return client.post(ACCEPT, payload, content_type="application/json")


def test_an_invitation_mails_a_hashed_single_use_token(org: Organization) -> None:
    raw = invite()
    assert len(mail.outbox) == 1
    assert mailed_token() == raw
    row = Invitation.objects.get()
    assert row.token_hash != raw
    assert len(row.token_hash) == 64
    assert row.roles == ["employee"]
    assert row.accepted_at is None
    assert row.expires_at > timezone.now() + timedelta(days=6)


def test_accepting_creates_the_account_and_its_membership(
    org: Organization, client: Client
) -> None:
    department = Department.objects.create(organization_id=ORG, name_ar=f"القسم {uuid4().hex[:8]}")
    inviter = Membership.objects.create(
        organization_id=ORG,
        user=new_account(),
        status=Membership.Status.ACTIVE,
        joined_at=timezone.now(),
    )
    _, raw = invitations.invite(
        organization_id=ORG,
        email="invitee@example.com",
        roles=["department_manager"],
        department=department,
        invited_by=inviter,
    )
    accepted = accept(client, raw)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    # Acceptance is not a credential: no session exists yet.
    assert client.session.get("academy_identity") is None

    account = User.objects.get(email="invitee@example.com")
    assert account.is_email_verified is True
    assert account.status == User.Status.ACTIVE
    assert account.check_password(PASSWORD)
    membership = Membership.objects.get(user=account)
    assert membership.organization_id == ORG
    assert membership.status == Membership.Status.ACTIVE
    assert membership.department_id == department.pk
    assert membership.invited_by_id == inviter.user_id
    assert membership.roles == ["department_manager"]

    signed_in = client.post(
        LOGIN,
        {"email": "invitee@example.com", "password": PASSWORD},
        content_type="application/json",
    )
    assert signed_in.status_code == 200
    assert client.session["academy_identity"]["roles"] == ["department_manager"]


def test_a_replayed_invitation_is_refused(org: Organization, client: Client) -> None:
    raw = invite()
    assert accept(client, raw).status_code == 200
    replay = accept(client, raw, display_name="Someone Else")
    assert replay.status_code == 400
    assert replay.json()["code"] == "invitation_invalid"
    assert User.objects.filter(email="invitee@example.com").count() == 1


def test_an_expired_invitation_is_refused(org: Organization, client: Client) -> None:
    raw = invite()
    Invitation.objects.update(expires_at=timezone.now())
    response = accept(client, raw)
    assert response.status_code == 400
    assert response.json()["code"] == "invitation_invalid"
    assert not User.objects.filter(email="invitee@example.com").exists()


def test_reinviting_retires_the_previous_token(org: Organization, client: Client) -> None:
    first = invite()
    second = invite()
    assert first != second
    assert Invitation.objects.count() == 1
    assert accept(client, first).status_code == 400
    assert accept(client, second).status_code == 200


def test_an_email_with_another_membership_is_refused(org: Organization, client: Client) -> None:
    raw = invite()
    other_organization()
    account = new_account("invitee@example.com")
    Membership.objects.create(
        organization_id=OTHER_ORG,
        user=account,
        status=Membership.Status.ACTIVE,
        joined_at=timezone.now(),
    )
    response = accept(client, raw)
    assert response.status_code == 409
    assert response.json()["code"] == "already_member"
    assert Membership.objects.filter(user=account).count() == 1
    assert Invitation.objects.get().accepted_at is None


def test_an_active_member_of_the_same_company_is_refused(org: Organization, client: Client) -> None:
    raw = invite()
    account = new_account("invitee@example.com")
    Membership.objects.create(
        organization_id=ORG,
        user=account,
        status=Membership.Status.ACTIVE,
        joined_at=timezone.now(),
    )
    response = accept(client, raw)
    assert response.status_code == 409
    assert response.json()["code"] == "already_member"
    assert Membership.objects.filter(user=account).count() == 1


def test_a_removed_membership_is_restored_not_duplicated(org: Organization, client: Client) -> None:
    raw = invite()
    account = new_account("invitee@example.com")
    removed = Membership.objects.create(
        organization_id=ORG,
        user=account,
        status=Membership.Status.REMOVED,
        joined_at=timezone.now(),
        removed_at=timezone.now(),
    )
    response = accept(client, raw)
    assert response.status_code == 200
    removed.refresh_from_db()
    assert removed.status == Membership.Status.ACTIVE
    assert removed.removed_at is None
    assert Membership.objects.filter(user=account).count() == 1


def test_only_company_roles_can_be_invited(org: Organization) -> None:
    with pytest.raises(DomainValidationError):
        invitations.invite(organization_id=ORG, email="x@example.com", roles=["platform_admin"])
    with pytest.raises(DomainValidationError):
        invitations.invite(organization_id=ORG, email="x@example.com", roles=[])
    assert Invitation.objects.count() == 0
    assert mail.outbox == []


def test_a_weak_password_is_refused_without_consuming_the_invitation(
    org: Organization, client: Client
) -> None:
    raw = invite()
    weak = accept(client, raw, password="short")
    assert weak.status_code == 400
    assert weak.json()["code"] == "validation_error"
    assert Invitation.objects.get().accepted_at is None

    retried = accept(client, raw)
    assert retried.status_code == 200


def test_revoking_deletes_the_pending_invitation(org: Organization, client: Client) -> None:
    raw = invite()
    row = Invitation.objects.get()
    invitations.revoke(organization_id=ORG, invitation_id=row.pk)
    assert Invitation.objects.count() == 0
    response = accept(client, raw)
    assert response.status_code == 400
    assert response.json()["code"] == "invitation_invalid"


def test_revoking_an_unknown_invitation_is_a_404(org: Organization) -> None:
    with pytest.raises(NotFound):
        invitations.revoke(organization_id=ORG, invitation_id=uuid4())


def test_an_existing_account_keeps_its_own_password(org: Organization, client: Client) -> None:
    raw = invite()
    account = new_account("invitee@example.com", is_email_verified=False)
    account.set_password("Existing-Password-2026")
    account.save()

    assert accept(client, raw, password="Different-Password-2026").status_code == 200
    account.refresh_from_db()
    assert account.check_password("Existing-Password-2026")
    assert account.is_email_verified is True
    assert Membership.objects.filter(user=account, organization_id=ORG).exists()


def test_an_unknown_token_is_invitation_invalid(org: Organization, client: Client) -> None:
    response = accept(client, "not-a-real-token")
    assert response.status_code == 400
    assert response.json()["code"] == "invitation_invalid"


def test_the_service_rejects_an_already_affiliated_email_at_issue_time(
    org: Organization,
) -> None:
    account = new_account("member@example.com")
    Membership.objects.create(
        organization_id=ORG,
        user=account,
        status=Membership.Status.ACTIVE,
        joined_at=timezone.now(),
    )
    with pytest.raises(AlreadyMember):
        invitations.invite(organization_id=ORG, email="member@example.com", roles=["employee"])


def test_accepting_an_invalidated_row_is_refused(org: Organization) -> None:
    raw = invite()
    Invitation.objects.update(accepted_at=timezone.now())
    with pytest.raises(InvitationInvalid):
        invitations.accept(raw, password=PASSWORD, display_name="Learner")
