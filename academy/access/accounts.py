"""Account lifecycle: sign-in, email verification and password reset — T-027 CP1.

Everything the auth endpoints do lives here, so the rules are testable without HTTP: the
email+IP failure window, the enumeration-safe responses, hashed single-use tokens, password
validation and the security log line. No secret, token or email address is written to a log or
to the session; a log line carries the account UUID and a truncated client address.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from academy.access import mfa, sessions
from academy.access.net import client_ip, truncated_ip
from academy.access.principals import SESSION_KEY, session_auth_hash
from academy.access.tenancy import roles_for_user
from academy.access.tokens import consume, issue
from academy.exceptions import (
    DomainValidationError,
    InvalidCredentials,
    MFAInvalid,
    MFARequired,
    TokenInvalid,
    TooManyAttempts,
)
from academy.models import AccountToken, User

logger = logging.getLogger("academy.security")

_PAIR_KEY = "academy:loginfail:pair:{email}:{ip}"
_IP_KEY = "academy:loginfail:ip:{ip}"

#: Longest message a mail template receives; the account's language is CP3's delivery work.
_MAIL_SUBJECTS = {
    "verification": "Activate your Masheed Academy account",
    "password_reset": "Reset your Masheed Academy password",
}


def _guard_enabled() -> bool:
    return bool(getattr(settings, "THROTTLES_ENABLED", True))


def _increment(key: str, window: int) -> int:
    cache.add(key, 0, timeout=window)
    try:
        return int(cast(int, cache.incr(key)))
    except ValueError:  # the key expired between ``add`` and ``incr``
        cache.set(key, 1, timeout=window)
        return 1


def login_locked(request: Any, email: str) -> bool:
    """Five failures for one email+IP, or the per-IP ceiling, lock the window."""
    if not _guard_enabled():
        return False
    address = client_ip(request)
    pair = int(cache.get(_PAIR_KEY.format(email=email.strip().lower(), ip=address)) or 0)
    per_ip = int(cache.get(_IP_KEY.format(ip=address)) or 0)
    return pair >= int(getattr(settings, "ACADEMY_LOGIN_MAX_FAILURES", 5)) or per_ip >= int(
        getattr(settings, "ACADEMY_LOGIN_IP_MAX_FAILURES", 20)
    )


def record_login_failure(request: Any, email: str) -> None:
    if not _guard_enabled():
        return
    window = int(getattr(settings, "ACADEMY_LOGIN_WINDOW_SECONDS", 900))
    address = client_ip(request)
    _increment(_PAIR_KEY.format(email=email.strip().lower(), ip=address), window)
    _increment(_IP_KEY.format(ip=address), window)


def clear_login_failures(request: Any, email: str) -> None:
    cache.delete(_PAIR_KEY.format(email=email.strip().lower(), ip=client_ip(request)))


def session_payload(user: User) -> dict[str, Any]:
    """The identity a session stores: the account, a password fingerprint and its roles.

    Roles come from the account's membership, so a session never carries a role the database
    does not grant. No capability, token or secret is stored.
    """
    return {
        "user_id": str(user.pk),
        "auth_hash": session_auth_hash(user),
        "roles": roles_for_user(user),
    }


def sign_in(request: Any, user: User) -> None:
    """Rotate the session key and store the account, never a capability or a secret."""
    request.session.cycle_key()
    request.session[SESSION_KEY] = session_payload(user)
    sessions.start(user, request.session.session_key, request=request)
    user.last_login_at = timezone.now()
    user.save(update_fields=["last_login_at", "updated_at"])


def authenticate_credentials(
    request: Any, email: str, password: str, mfa_code: str | None = None
) -> User:
    """Authenticate or fail with one generic error; each failure feeds the lock window.

    A correct password on an account with a confirmed device creates no session: without a code
    the answer is ``mfa_required`` with a single-use challenge, and a wrong code is
    ``mfa_invalid`` and counts as a failure so the lock window covers guessing.
    """
    address = email.strip().lower()
    if login_locked(request, address):
        logger.warning(
            "auth.login_locked",
            extra={"event": "auth.login_locked", "ip": truncated_ip(client_ip(request))},
        )
        raise TooManyAttempts("too many failed sign-in attempts; try again later")

    # ``authenticate`` dispatches to the configured backend, whose return type the stubs cannot
    # infer from settings; the backend above is the only one configured and returns ``User``.
    user = cast(User | None, authenticate(request, username=address, password=password))
    if user is None:
        record_login_failure(request, address)
        logger.warning(
            "auth.login_failed",
            extra={"event": "auth.login_failed", "ip": truncated_ip(client_ip(request))},
        )
        raise InvalidCredentials("invalid email or password")

    if mfa.enabled(user):
        if not mfa.normalize_code(mfa_code):
            logger.info(
                "auth.mfa_challenge",
                extra={"event": "auth.mfa_challenge", "user_id": str(user.pk)},
            )
            raise MFARequired(mfa.open_challenge(user))
        if not mfa.verify_second_factor(user, mfa_code):
            record_login_failure(request, address)
            logger.warning(
                "auth.mfa_failed",
                extra={"event": "auth.mfa_failed", "ip": truncated_ip(client_ip(request))},
            )
            raise MFAInvalid("the second factor is not valid")

    clear_login_failures(request, address)
    sign_in(request, user)
    logger.info(
        "auth.login_succeeded",
        extra={"event": "auth.login_succeeded", "user_id": str(user.pk)},
    )
    return user


def complete_mfa(request: Any, challenge_id: str, code: str) -> User:
    """Finish a challenged sign-in; the challenge is consumed before the code is checked."""
    user = mfa.consume_challenge(challenge_id)
    if user is None or not user.is_active:
        raise MFAInvalid("the challenge has expired; sign in again")
    if not mfa.verify_second_factor(user, code):
        logger.warning(
            "auth.mfa_failed",
            extra={"event": "auth.mfa_failed", "ip": truncated_ip(client_ip(request))},
        )
        raise MFAInvalid("the second factor is not valid")
    sign_in(request, user)
    logger.info(
        "auth.login_succeeded",
        extra={"event": "auth.login_succeeded", "user_id": str(user.pk)},
    )
    return user


def verification_token(user: User) -> str:
    """A fresh verification token; issuing one retires the account's previous token."""
    return issue(
        user,
        AccountToken.Purpose.VERIFY_EMAIL,
        ttl_seconds=int(getattr(settings, "ACADEMY_EMAIL_VERIFICATION_TTL_SECONDS", 86400)),
    )


def confirm_email(raw: str) -> User:
    """Consume a verification token once and activate the account."""
    row = consume(raw, AccountToken.Purpose.VERIFY_EMAIL)
    if row is None:
        raise TokenInvalid("the verification link is invalid or has expired")
    user = row.user
    fields: list[str] = []
    if not user.is_email_verified:
        user.is_email_verified = True
        fields.append("is_email_verified")
    if user.status == User.Status.UNVERIFIED:
        user.status = User.Status.ACTIVE
        fields.append("status")
    if fields:
        user.save(update_fields=[*fields, "updated_at"])
    logger.info(
        "auth.email_verified",
        extra={"event": "auth.email_verified", "user_id": str(user.pk)},
    )
    return user


def password_reset_token(email: str) -> tuple[User, str] | None:
    """A reset token for an eligible account; ``None`` answers exactly like an unknown email."""
    user = User.objects.filter(email__iexact=email.strip()).first()
    if user is None or not user.is_active or not user.has_usable_password():
        return None
    raw = issue(
        user,
        AccountToken.Purpose.RESET_PASSWORD,
        ttl_seconds=int(getattr(settings, "ACADEMY_PASSWORD_RESET_TTL_SECONDS", 3600)),
    )
    return user, raw


def reset_password(raw: str, new_password: str) -> User:
    """Set a new password from a single-use token; every other session stops resolving."""
    row = consume(raw, AccountToken.Purpose.RESET_PASSWORD)
    if row is None:
        raise TokenInvalid("the reset link is invalid or has expired")
    user = row.user
    validate_password_policy(user, new_password)
    user.set_password(new_password)
    user.password_changed_at = timezone.now()
    user.save(update_fields=["password", "password_changed_at", "updated_at"])
    sessions.revoke_all(user)
    logger.info(
        "auth.password_reset", extra={"event": "auth.password_reset", "user_id": str(user.pk)}
    )
    return user


def change_password(user: User, current_password: str, new_password: str) -> None:
    """Change a known password; the current one is required and re-verified."""
    if not user.check_password(current_password):
        raise DomainValidationError(
            "the current password is not correct", fields={"current_password": ["incorrect"]}
        )
    validate_password_policy(user, new_password)
    user.set_password(new_password)
    user.password_changed_at = timezone.now()
    user.save(update_fields=["password", "password_changed_at", "updated_at"])
    logger.info(
        "auth.password_changed",
        extra={"event": "auth.password_changed", "user_id": str(user.pk)},
    )


def send_account_mail(user: User, template: str, link: str, ttl_seconds: int) -> None:
    """Render and send one account mail; a transport failure is logged, never raised."""
    body = render_to_string(
        f"academy/mail/{template}.txt",
        {
            "display_name": user.display_name,
            "link": link,
            "hours": max(1, ttl_seconds // 3600),
        },
    )
    try:
        send_mail(
            _MAIL_SUBJECTS[template],
            body,
            str(getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@masheed.local")),
            [user.email],
        )
    except Exception:
        logger.exception(
            "auth.mail_failed",
            extra={"event": "auth.mail_failed", "template": template},
        )


def validate_password_policy(user: User, password: str) -> None:
    """Apply the configured policy; a rejection is a field error, never a 500."""
    try:
        validate_password(password, cast(Any, user))
    except ValidationError as error:
        raise DomainValidationError(
            "the password does not meet the policy", fields={"password": list(error.messages)}
        ) from error
