"""TOTP second factor, recovery codes and login challenges — T-027 CP2.

``docs/security.md`` §2 fixes the rules implemented here: RFC 6238 TOTP with a 30-second step
and ±1 step of drift, a secret encrypted at rest with ``ACADEMY_MFA_ENCRYPTION_KEY``, ten
single-use recovery codes stored hashed, enrolment behind a password re-entry, and a disabling
that needs a current second factor. A correct password on an enrolled account creates no session
until the challenge is answered; the challenge itself lives in the cache for five minutes and is
consumed by the first attempt, so a stolen challenge cannot be replayed.

Nothing in this module writes a secret, a code or an address to a log.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from typing import Any

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.utils import timezone

from academy.exceptions import AdapterNotConfigured, DomainValidationError, MFAInvalid
from academy.models import MFADevice, RecoveryCode, User

#: One cache entry per open challenge; the value is the account id, never a secret.
CHALLENGE_PREFIX = "academy:mfa:challenge:"

#: Ten codes, regenerated as a set (docs/domain-model.md §2.0.11).
RECOVERY_CODE_COUNT = 10


def _fernet() -> Fernet:
    """The cipher for TOTP secrets; a missing key is a deployment error, not a fallback.

    The configured value is hashed to the 32 bytes Fernet needs, so an operator can supply any
    long random string instead of a pre-formatted key.
    """
    value = str(getattr(settings, "ACADEMY_MFA_ENCRYPTION_KEY", "") or "")
    if not value:
        raise AdapterNotConfigured(
            "ACADEMY_MFA_ENCRYPTION_KEY is required to enrol a second factor"
        )
    material = base64.urlsafe_b64encode(hashlib.sha256(value.encode("utf-8")).digest())
    return Fernet(material)


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_secret(blob: str) -> str:
    try:
        return _fernet().decrypt(blob.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as error:
        raise MFAInvalid("the stored second factor cannot be read") from error


def normalize_code(raw: Any) -> str:
    """Codes are compared without separators and case, so ``123 456`` equals ``123456``."""
    return "".join(ch for ch in str(raw or "") if ch.isalnum()).lower()


def provisioning_uri(secret: str, email: str) -> str:
    issuer = str(getattr(settings, "ACADEMY_MFA_ISSUER", "Masheed Academy"))
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def active_device(user: User) -> MFADevice | None:
    """The account's confirmed device, if it has one."""
    return MFADevice.objects.filter(user=user, confirmed_at__isnull=False).first()


def enabled(user: User) -> bool:
    return MFADevice.objects.filter(user=user, confirmed_at__isnull=False).exists()


def required_roles() -> frozenset[str]:
    """The configured role codes that must present a second factor."""
    value: Any = getattr(settings, "ACADEMY_MFA_REQUIRED_ROLES", ())
    if isinstance(value, str):
        value = value.split(",")
    return frozenset(str(role).strip() for role in value if str(role).strip())


def requires_enrollment(user: User, roles: Any) -> bool:
    """True when one of the account's roles mandates MFA and no device is confirmed yet."""
    wanted = required_roles()
    if not wanted.intersection(roles or ()):
        return False
    return not enabled(user)


def enroll(user: User, password: str) -> tuple[MFADevice, str, str]:
    """Start enrolment: re-verify the password and return the secret and otpauth URI once."""
    if not user.check_password(password):
        raise DomainValidationError(
            "the password is not correct", fields={"password": ["incorrect"]}
        )
    if enabled(user):
        raise DomainValidationError(
            "a second factor is already enrolled", fields={"mfa": ["already_enrolled"]}
        )
    secret = pyotp.random_base32()
    encrypted = encrypt_secret(secret)
    MFADevice.objects.filter(user=user, confirmed_at__isnull=True).delete()
    device = MFADevice.objects.create(user=user, secret_encrypted=encrypted)
    return device, secret, provisioning_uri(secret, user.email)


def confirm(user: User, code: Any) -> list[str]:
    """Confirm the pending device and return ten recovery codes, shown once."""
    device = (
        MFADevice.objects.filter(user=user, confirmed_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if device is None:
        raise DomainValidationError(
            "start enrolment before confirming it", fields={"mfa": ["not_enrolled"]}
        )
    normalized = normalize_code(code)
    if not normalized or not pyotp.TOTP(decrypt_secret(device.secret_encrypted)).verify(
        normalized, valid_window=1
    ):
        raise DomainValidationError("the code is not valid", fields={"code": ["invalid"]})

    moment = timezone.now()
    device.confirmed_at = moment
    device.last_used_at = moment
    device.save(update_fields=["confirmed_at", "last_used_at", "updated_at"])

    RecoveryCode.objects.filter(user=user).delete()
    codes = [secrets.token_hex(5) for _ in range(RECOVERY_CODE_COUNT)]
    RecoveryCode.objects.bulk_create(
        [RecoveryCode(user=user, code_hash=make_password(normalize_code(raw))) for raw in codes]
    )
    return codes


def _consume_recovery_code(user: User, normalized: str) -> bool:
    """Check the unused codes of one account; Argon2 hashes rule out a direct lookup."""
    for row in RecoveryCode.objects.filter(user=user, used_at__isnull=True).only("id", "code_hash"):
        if check_password(normalized, row.code_hash):
            claimed = RecoveryCode.objects.filter(pk=row.pk, used_at__isnull=True).update(
                used_at=timezone.now()
            )
            return claimed == 1
    return False


def verify_second_factor(user: User, code: Any) -> bool:
    """A current TOTP code or one unused recovery code; a recovery code is spent on success."""
    normalized = normalize_code(code)
    if not normalized:
        return False
    device = active_device(user)
    if device is not None and pyotp.TOTP(decrypt_secret(device.secret_encrypted)).verify(
        normalized, valid_window=1
    ):
        MFADevice.objects.filter(pk=device.pk).update(last_used_at=timezone.now())
        return True
    return _consume_recovery_code(user, normalized)


def disable(user: User, password: str, code: Any) -> None:
    """Remove the device and its codes; both the password and a current factor are required."""
    if not user.check_password(password):
        raise DomainValidationError(
            "the password is not correct", fields={"password": ["incorrect"]}
        )
    if not verify_second_factor(user, code):
        raise DomainValidationError("the second factor is not valid", fields={"code": ["invalid"]})
    MFADevice.objects.filter(user=user).delete()
    RecoveryCode.objects.filter(user=user).delete()


def open_challenge(user: User) -> str:
    """A five-minute single-use challenge that completes a password-only sign-in."""
    challenge_id = uuid.uuid4().hex
    ttl = int(getattr(settings, "ACADEMY_MFA_CHALLENGE_TTL_SECONDS", 300))
    cache.set(f"{CHALLENGE_PREFIX}{challenge_id}", str(user.pk), timeout=ttl)
    return challenge_id


def consume_challenge(challenge_id: Any) -> User | None:
    """Claim a challenge once; a replayed, expired or unknown id resolves to no account."""
    key_id = str(challenge_id or "")
    if not key_id:
        return None
    key = f"{CHALLENGE_PREFIX}{key_id}"
    value = cache.get(key)
    if value is None:
        return None
    cache.delete(key)
    try:
        return User.objects.filter(pk=uuid.UUID(str(value))).first()
    except (TypeError, ValueError):
        return None
