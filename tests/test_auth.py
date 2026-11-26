"""T-027 CP1 acceptance: email + password sign-in, verification and password reset.

The matrix follows ``docs/security.md`` §2 and ``docs/api.md`` §3/§15: only the credential
creates a session, failures never reveal whether an email exists, tokens are hashed and
single-use, a reset or change invalidates other sessions, and no secret reaches a log, the
session or a response.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

import pytest
from django.core import mail
from django.core.cache import cache
from django.test import Client, override_settings

from academy.access import accounts
from academy.models import AccountToken, Membership, User
from academy.models.tenancy import Organization

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
LOGIN = "/api/v1/academy/auth/login/"
LOGOUT = "/api/v1/academy/auth/logout/"
RESET_REQUEST = "/api/v1/academy/auth/password/reset/request/"
RESET_CONFIRM = "/api/v1/academy/auth/password/reset/confirm/"
CHANGE = "/api/v1/academy/auth/password/change/"
VERIFY_REQUEST = "/api/v1/academy/auth/email/verify/request/"
VERIFY_CONFIRM = "/api/v1/academy/auth/email/verify/confirm/"
CAPABILITIES = "/api/v1/academy/me/capabilities/"

PASSWORD = "Correct-Horse-Battery-7"
NEW_PASSWORD = "Another-Stable-Passphrase-9"
TOKEN_IN_MAIL = re.compile(r"token=([A-Za-z0-9_\-]+)")


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    cache.clear()


def make_user(
    email: str = "learner@example.com",
    *,
    password: str = PASSWORD,
    verified: bool = True,
    status: str = User.Status.ACTIVE,
    with_membership: bool = True,
) -> User:
    user = User.objects.create(
        email=email,
        display_name="Learner",
        status=status,
        is_email_verified=verified,
    )
    user.set_password(password)
    user.save()
    if with_membership:
        Organization.objects.get_or_create(
            id=ORG, defaults={"name_ar": "Masheed Academy", "slug": "masheed"}
        )
        Membership.objects.create(
            organization_id=ORG,
            user=user,
            status=Membership.Status.ACTIVE,
            joined_at="2026-01-01T00:00:00Z",
        )
    return user


def post(client: Client, path: str, payload: dict[str, Any]) -> Any:
    return client.post(path, payload, content_type="application/json")


def login(client: Client, email: str = "learner@example.com", password: str = PASSWORD) -> Any:
    return post(client, LOGIN, {"email": email, "password": password})


def mailed_token() -> str:
    body = str(mail.outbox[-1].body)
    match = TOKEN_IN_MAIL.search(body)
    assert match is not None
    return match.group(1)


def test_only_the_credential_creates_a_session(db: Any, client: Client) -> None:
    make_user()
    wrong = login(client, password="not-the-password")
    assert wrong.status_code == 401
    assert wrong.json()["code"] == "invalid_credentials"
    assert client.session.get("academy_identity") is None

    ok = login(client)
    assert ok.status_code == 200
    assert ok.json()["email_verified"] is True
    identity = client.session["academy_identity"]
    assert identity["user_id"]
    assert "password" not in identity
    assert client.get(CAPABILITIES).status_code == 200


def test_an_unknown_email_is_indistinguishable_from_a_wrong_password(
    db: Any, client: Client
) -> None:
    make_user()
    unknown = login(client, email="nobody@example.com")
    wrong = login(client, email="learner@example.com", password="wrong-password")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()
    assert unknown.json()["detail"] == "invalid email or password"


def test_email_matching_ignores_case_and_surrounding_space(db: Any, client: Client) -> None:
    make_user(email="Learner@Example.com")
    assert login(client, email="  learner@example.COM ").status_code == 200


@pytest.mark.parametrize("status", [User.Status.SUSPENDED, User.Status.DEACTIVATED])
def test_a_disabled_account_cannot_sign_in(db: Any, client: Client, status: str) -> None:
    make_user(status=status)
    response = login(client)
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


@override_settings(THROTTLES_ENABLED=True)
def test_five_failures_lock_the_pair_for_the_window(db: Any, client: Client) -> None:
    make_user()
    for _ in range(5):
        assert login(client, password="wrong-password").status_code == 401
    locked = login(client)
    assert locked.status_code == 429
    assert locked.json()["code"] == "throttled"
    # The correct password does not bypass the lock.
    assert login(client).status_code == 429


def test_verification_mail_is_sent_and_the_token_is_hashed(db: Any, client: Client) -> None:
    make_user(verified=False, status=User.Status.UNVERIFIED)
    response = post(client, VERIFY_REQUEST, {"email": "learner@example.com"})
    assert response.status_code == 202
    assert len(mail.outbox) == 1
    raw = mailed_token()
    row = AccountToken.objects.get()
    assert row.token_hash != raw
    assert len(row.token_hash) == 64
    assert raw not in row.token_hash


def test_verification_activates_the_account_once(db: Any, client: Client) -> None:
    user = make_user(verified=False, status=User.Status.UNVERIFIED)
    post(client, VERIFY_REQUEST, {"email": "learner@example.com"})
    raw = mailed_token()

    confirmed = post(client, VERIFY_CONFIRM, {"token": raw})
    assert confirmed.status_code == 200
    user.refresh_from_db()
    assert user.is_email_verified is True
    assert user.status == User.Status.ACTIVE

    replay = post(client, VERIFY_CONFIRM, {"token": raw})
    assert replay.status_code == 400
    assert replay.json()["code"] == "token_invalid"


def test_an_expired_verification_token_is_refused(db: Any, client: Client) -> None:
    make_user(verified=False, status=User.Status.UNVERIFIED)
    with override_settings(ACADEMY_EMAIL_VERIFICATION_TTL_SECONDS=0):
        post(client, VERIFY_REQUEST, {"email": "learner@example.com"})
        raw = mailed_token()
    response = post(client, VERIFY_CONFIRM, {"token": raw})
    assert response.status_code == 400
    assert response.json()["code"] == "token_invalid"


def test_resending_verification_retires_the_previous_token(db: Any, client: Client) -> None:
    make_user(verified=False, status=User.Status.UNVERIFIED)
    post(client, VERIFY_REQUEST, {"email": "learner@example.com"})
    first = mailed_token()
    post(client, VERIFY_REQUEST, {"email": "learner@example.com"})
    second = mailed_token()
    assert first != second
    assert post(client, VERIFY_CONFIRM, {"token": first}).status_code == 400
    assert post(client, VERIFY_CONFIRM, {"token": second}).status_code == 200


def test_reset_request_is_identical_for_known_and_unknown_addresses(
    db: Any, client: Client
) -> None:
    make_user()
    known = post(client, RESET_REQUEST, {"email": "learner@example.com"})
    unknown = post(client, RESET_REQUEST, {"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json() == {"status": "accepted"}
    assert len(mail.outbox) == 1


def test_reset_consumes_the_token_and_revokes_other_sessions(db: Any, client: Client) -> None:
    user = make_user()
    other = Client()
    assert login(client).status_code == 200
    assert login(other).status_code == 200

    post(client, RESET_REQUEST, {"email": "learner@example.com"})
    raw = mailed_token()
    confirmed = post(client, RESET_CONFIRM, {"token": raw, "password": NEW_PASSWORD})
    assert confirmed.status_code == 200

    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    assert user.password_changed_at is not None
    # Both existing sessions carry the old password fingerprint.
    assert client.get(CAPABILITIES).status_code == 401
    assert other.get(CAPABILITIES).status_code == 401
    assert post(client, RESET_CONFIRM, {"token": raw, "password": NEW_PASSWORD}).status_code == 400
    assert login(client, password=NEW_PASSWORD).status_code == 200


def test_reset_rejects_a_weak_password(db: Any, client: Client) -> None:
    make_user()
    post(client, RESET_REQUEST, {"email": "learner@example.com"})
    raw = mailed_token()
    response = post(client, RESET_CONFIRM, {"token": raw, "password": "short"})
    assert response.status_code == 400
    assert response.json()["code"] == "validation_error"
    assert "password" in response.json()["fields"]


def test_change_password_keeps_the_current_session_and_ends_the_others(
    db: Any, client: Client
) -> None:
    make_user()
    other = Client()
    assert login(client).status_code == 200
    assert login(other).status_code == 200

    rejected = post(client, CHANGE, {"current_password": "wrong", "password": NEW_PASSWORD})
    assert rejected.status_code == 400
    changed = post(client, CHANGE, {"current_password": PASSWORD, "password": NEW_PASSWORD})
    assert changed.status_code == 200
    assert client.get(CAPABILITIES).status_code == 200
    assert other.get(CAPABILITIES).status_code == 401
    assert login(other, password=PASSWORD).status_code == 401
    assert login(other, password=NEW_PASSWORD).status_code == 200


def test_an_unverified_account_signs_in_but_reaches_no_tenant_data(db: Any, client: Client) -> None:
    make_user(verified=False, status=User.Status.UNVERIFIED)
    response = login(client)
    assert response.status_code == 200
    assert response.json()["email_verified"] is False
    refused = client.get(CAPABILITIES)
    assert refused.status_code == 403
    assert refused.json()["code"] == "email_unverified"


def test_logout_ends_the_session(db: Any, client: Client) -> None:
    make_user()
    assert login(client).status_code == 200
    assert post(client, LOGOUT, {}).status_code == 204
    assert client.get(CAPABILITIES).status_code == 401


def test_no_password_or_token_reaches_the_logs(
    db: Any, client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    make_user()
    post(client, RESET_REQUEST, {"email": "learner@example.com"})
    raw = mailed_token()
    post(client, RESET_CONFIRM, {"token": raw, "password": NEW_PASSWORD})
    login(client, password=PASSWORD)
    with caplog.at_level(logging.INFO):
        login(client, password=PASSWORD)
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert PASSWORD not in text
    assert NEW_PASSWORD not in text
    assert raw not in text
    assert "learner@example.com" not in text


def test_a_successful_login_clears_the_failure_counter(db: Any, client: Client) -> None:
    make_user()
    with override_settings(THROTTLES_ENABLED=True):
        for _ in range(4):
            login(client, password="wrong-password")
        assert login(client).status_code == 200
        assert accounts.login_locked(client.request, "learner@example.com") is False


SESSIONS = "/api/v1/academy/auth/sessions/"


def test_sessions_list_shows_only_live_sessions_of_the_caller(db: Any, client: Client) -> None:
    make_user()
    login(client)
    rows = client.get(SESSIONS).json()
    assert len(rows) == 1
    assert rows[0]["current"] is True
    assert rows[0]["user_agent_family"]


def test_revoking_another_device_ends_only_that_session(db: Any, client: Client) -> None:
    make_user()
    other = Client()
    assert login(client).status_code == 200
    assert login(other).status_code == 200
    rows = client.get(SESSIONS).json()
    assert len(rows) == 2
    target = next(row for row in rows if not row["current"])

    assert client.delete(f"{SESSIONS}{target['id']}/").status_code == 204
    assert other.get(CAPABILITIES).status_code == 401
    assert client.get(CAPABILITIES).status_code == 200


def test_another_accounts_session_is_a_plain_404(db: Any, client: Client) -> None:
    make_user()
    make_user("second@example.com")
    other = Client()
    login(client)
    login(other, "second@example.com")
    foreign = other.get(SESSIONS).json()[0]["id"]
    assert client.delete(f"{SESSIONS}{foreign}/").status_code == 404


@override_settings(ACADEMY_SESSION_IDLE_SECONDS=0)
def test_the_idle_window_ends_the_session(db: Any, client: Client) -> None:
    make_user()
    login(client)
    assert client.get(CAPABILITIES).status_code == 401
