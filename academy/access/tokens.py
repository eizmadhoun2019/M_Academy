"""Single-use, hashed account tokens — T-027 CP1.

A verification or reset link carries a random token; the database stores only its SHA-256
digest, so a database read cannot replay the link. Consumption is one conditional ``UPDATE``
(``used_at IS NULL``), which makes two concurrent confirmations resolve to one winner, and an
expired row is refused before anything is written.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from django.utils import timezone

from academy.models import AccountToken, User


def digest(raw: str) -> str:
    """The stored form of a raw token; deterministic so lookup is one indexed read."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue(
    user: User,
    purpose: str,
    *,
    ttl_seconds: int,
    now: datetime | None = None,
) -> str:
    """Retire the account's live tokens of this purpose and return one new raw token."""
    moment = now or timezone.now()
    AccountToken.objects.filter(user=user, purpose=purpose, used_at__isnull=True).update(
        used_at=moment
    )
    raw = secrets.token_urlsafe(32)
    AccountToken.objects.create(
        user=user,
        purpose=purpose,
        token_hash=digest(raw),
        expires_at=moment + timedelta(seconds=ttl_seconds),
    )
    return raw


def consume(
    raw: str,
    purpose: str,
    *,
    now: datetime | None = None,
) -> AccountToken | None:
    """Claim a live token once; a replayed, expired or unknown token returns ``None``."""
    if not raw:
        return None
    moment = now or timezone.now()
    row = (
        AccountToken.objects.select_related("user")
        .filter(token_hash=digest(raw), purpose=purpose)
        .first()
    )
    if row is None or row.used_at is not None or row.expires_at <= moment:
        return None
    claimed = AccountToken.objects.filter(pk=row.pk, used_at__isnull=True).update(used_at=moment)
    if claimed != 1:
        return None
    row.used_at = moment
    return row
