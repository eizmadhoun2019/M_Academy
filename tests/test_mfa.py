"""T-027 CP2 acceptance: TOTP MFA, recovery codes and role-enforced enrolment.

``docs/security.md`` §2 fixes the behaviour under test: enrolment needs the password, the secret
is stored encrypted and returned once, confirmation issues ten hashed single-use recovery codes,
a correct password on an enrolled account creates no session until a five-minute challenge is
answered, disabling needs the password *and* a current code, and an account whose role mandates
MFA reaches no tenant data before it enrols.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pyotp
import pytest
from django.core.cache import cache
from django.test import Client, override_settings
from django.utils import timezone

from academy.access import mfa
from academy.models import Membership, MFADevice, Organization, RecoveryCode, User

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
LOGIN = "/api/v1/academy/auth/login/"
VERIFY = "/api/v1/academy/auth/mfa/verify/"
ENROLL = "/api/v1/academy/auth/mfa/enroll/"
CONFIRM = "/api/v1/academy/auth/mfa/confirm/"
DISABLE = "/api/v1/academy/auth/mfa/disable/"
CAPABILITIES = "/api/v1/academy/me/capabilities/"
PASSWORD = "Correct-Horse-Battery-7"


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    cache.clear()


def make_user(roles: list[str] | None = None, verified: bool = True) -> User:
    Organization.objects.get_or_create(
        id=ORG, defaults={"name_ar": "Masheed Academy", "slug": "masheed"}
    )
    account = User.objects.create(
        email=f"learner-{uuid4()}@example.com",
        display_name="Learner",
        status=User.Status.ACTIVE,
        is_email_verified=verified,
    )
    account.set_password(PASSWORD)
    account.save()
    Membership.objects.create(
        organization_id=ORG,
        user=account,
        status=Membership.Status.ACTIVE,
        joined_at=timezone.now(),
        roles=roles or ["employee"],
    )
    return account


def post(client: Client, path: str, payload: dict[str, Any]) -> Any:
    return client.post(path, payload, content_type="application/json")


def login(client: Client, account: User, **extra: Any) -> Any:
    payload: dict[str, Any] = {"email": account.email, "password": PASSWORD}
    payload.update(extra)
    return post(client, LOGIN, payload)


def enrol(client: Client) -> tuple[str, list[str]]:
    """Enrol and confirm one device through the API; returns the secret and recovery codes."""
    started = post(client, ENROLL, {"password": PASSWORD})
    assert started.status_code == 200
    secret = started.json()["secret"]
    confirmed = post(client, CONFIRM, {"code": pyotp.TOTP(secret).now()})
    assert confirmed.status_code == 200
    return secret, list(confirmed.json()["recovery_codes"])


def test_enrolment_returns_the_secret_once_and_stores_it_encrypted(db: Any, client: Client) -> None:
    account = make_user()
    login(client, account)
    response = post(client, ENROLL, {"password": PASSWORD})
    assert response.status_code == 200
    secret = response.json()["secret"]
    assert response.json()["otpauth_uri"].startswith("otpauth://totp/")
    device = MFADevice.objects.get(user=account)
    assert device.confirmed_at is None
    assert secret not in device.secret_encrypted
    assert mfa.decrypt_secret(device.secret_encrypted) == secret


def test_enrolment_requires_the_password(db: Any, client: Client) -> None:
    account = make_user()
    login(client, account)
    response = post(client, ENROLL, {"password": "not-the-password"})
    assert response.status_code == 400
    assert response.json()["fields"]["password"] == ["incorrect"]
    assert MFADevice.objects.count() == 0


def test_confirming_issues_ten_hashed_recovery_codes(db: Any, client: Client) -> None:
    account = make_user()
    login(client, account)
    started = post(client, ENROLL, {"password": PASSWORD})
    secret = started.json()["secret"]

    confirmed = post(client, CONFIRM, {"code": pyotp.TOTP(secret).now()})
    assert confirmed.status_code == 200
    codes = list(confirmed.json()["recovery_codes"])
    assert len(codes) == 10
    rows = RecoveryCode.objects.filter(user=account)
    assert rows.count() == 10
    assert all(row.code_hash not in codes for row in rows)
    assert not RecoveryCode.objects.filter(code_hash__in=codes).exists()
    device = MFADevice.objects.get(user=account)
    assert device.confirmed_at is not None

    again = post(client, CONFIRM, {"code": pyotp.TOTP(secret).now()})
    assert again.status_code == 400


def test_a_confirmed_device_forces_a_challenge_before_a_session(db: Any, client: Client) -> None:
    account = make_user()
    login(client, account)
    secret, _ = enrol(client)
    post(client, "/api/v1/academy/auth/logout/", {})
    client.session.flush()

    challenged = login(client, account)
    assert challenged.status_code == 401
    assert challenged.json()["code"] == "mfa_required"
    challenge_id = challenged.json()["fields"]["challenge_id"]
    assert client.session.get("academy_identity") is None

    verified = post(
        client, VERIFY, {"challenge_id": challenge_id, "code": pyotp.TOTP(secret).now()}
    )
    assert verified.status_code == 200
    assert client.get(CAPABILITIES).status_code == 200


def test_the_code_may_be_supplied_with_the_password(db: Any, client: Client) -> None:
    account = make_user()
    login(client, account)
    secret, _ = enrol(client)
    client.session.flush()
    response = login(client, account, mfa_code=pyotp.TOTP(secret).now())
    assert response.status_code == 200


def test_a_challenge_is_single_use(db: Any, client: Client) -> None:
    account = make_user()
    login(client, account)
    secret, _ = enrol(client)
    client.session.flush()

    challenge_id = login(client, account).json()["fields"]["challenge_id"]
    code = pyotp.TOTP(secret).now()
    assert post(client, VERIFY, {"challenge_id": challenge_id, "code": code}).status_code == 200
    client.session.flush()
    replay = post(client, VERIFY, {"challenge_id": challenge_id, "code": code})
    assert replay.status_code == 401
    assert replay.json()["code"] == "mfa_invalid"


def test_a_wrong_code_consumes_the_challenge(db: Any, client: Client) -> None:
    account = make_user()
    login(client, account)
    secret, _ = enrol(client)
    client.session.flush()

    challenge_id = login(client, account).json()["fields"]["challenge_id"]
    wrong = post(client, VERIFY, {"challenge_id": challenge_id, "code": "000000"})
    assert wrong.status_code == 401
    assert wrong.json()["code"] == "mfa_invalid"
    retried = post(client, VERIFY, {"challenge_id": challenge_id, "code": pyotp.TOTP(secret).now()})
    assert retried.status_code == 401


def test_a_recovery_code_works_once(db: Any, client: Client) -> None:
    account = make_user()
    login(client, account)
    _, codes = enrol(client)
    client.session.flush()

    first = login(client, account).json()["fields"]["challenge_id"]
    assert post(client, VERIFY, {"challenge_id": first, "code": codes[0]}).status_code == 200
    client.session.flush()

    second = login(client, account).json()["fields"]["challenge_id"]
    assert post(client, VERIFY, {"challenge_id": second, "code": codes[0]}).status_code == 401
    client.session.flush()

    third = login(client, account).json()["fields"]["challenge_id"]
    assert post(client, VERIFY, {"challenge_id": third, "code": codes[1]}).status_code == 200


def test_disabling_needs_the_password_and_a_current_code(db: Any, client: Client) -> None:
    account = make_user()
    login(client, account)
    secret, _ = enrol(client)

    assert post(client, DISABLE, {"password": "wrong", "code": "000000"}).status_code == 400
    assert post(client, DISABLE, {"password": PASSWORD, "code": "000000"}).status_code == 400
    disabled = post(client, DISABLE, {"password": PASSWORD, "code": pyotp.TOTP(secret).now()})
    assert disabled.status_code == 200
    assert not MFADevice.objects.filter(user=account).exists()
    assert not RecoveryCode.objects.filter(user=account).exists()

    client.session.flush()
    assert login(client, account).status_code == 200


@override_settings(ACADEMY_MFA_REQUIRED_ROLES="department_manager")
def test_a_role_that_mandates_mfa_must_enrol_before_tenant_data(db: Any, client: Client) -> None:
    account = make_user(roles=["department_manager"])
    assert login(client, account).status_code == 200
    refused = client.get(CAPABILITIES)
    assert refused.status_code == 403
    assert refused.json()["code"] == "mfa_enrollment_required"

    # The auth routes stay reachable, so the account can enrol and satisfy the gate.
    enrol(client)
    assert client.get(CAPABILITIES).status_code == 200

    client.session.flush()
    challenged = login(client, account)
    assert challenged.status_code == 401
    assert challenged.json()["code"] == "mfa_required"


def test_the_default_required_roles_do_not_lock_a_learner(db: Any, client: Client) -> None:
    account = make_user()
    assert login(client, account).status_code == 200
    assert client.get(CAPABILITIES).status_code == 200
