"""Session registry: absolute expiry, idle timeout and owner-visible revocation — T-027 CP2.

The Django session still holds the identity; this table only records that the key exists, when it
was last active, when it must die, and whether the owner revoked it. A session with no live row
resolves to no principal, so "sign out everywhere" is one update instead of waiting for a cookie
to expire.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone

from academy.access.net import client_ip, truncated_ip
from academy.models import User, UserSession

#: A last-seen write per request would double the write load; five minutes is enough for the
#: documented 30-minute idle window.
_TOUCH_SECONDS = 300


def key_hash(key: str | None) -> str:
    return hashlib.sha256((key or "").encode("utf-8")).hexdigest()


def _idle_seconds() -> int:
    return int(getattr(settings, "ACADEMY_SESSION_IDLE_SECONDS", 1800))


def _absolute_seconds() -> int:
    return int(getattr(settings, "SESSION_COOKIE_AGE", 28800))


def start(user: User, key: str | None, *, request: Any = None) -> UserSession:
    """Register a freshly rotated session key with its absolute expiry."""
    moment = timezone.now()
    agent = str(getattr(getattr(request, "META", {}), "get", lambda *_: "")("HTTP_USER_AGENT", ""))
    family = " ".join(agent.split()[:1])[:40] or "unknown"
    return UserSession.objects.create(
        user=user,
        session_key_hash=key_hash(key),
        last_seen_at=moment,
        expires_at=moment + timedelta(seconds=_absolute_seconds()),
        ip_prefix=truncated_ip(client_ip(request)) if request is not None else "",
        user_agent_family=family,
    )


def live(request: Any) -> UserSession | None:
    """The row of a live session: present, not revoked, inside the absolute and idle windows.

    A write that is due updates ``last_seen_at``, so the idle clock is server-side and coarse.
    """
    key = getattr(getattr(request, "session", None), "session_key", None)
    if not key:
        return None
    row = UserSession.objects.filter(session_key_hash=key_hash(key)).first()
    if row is None or row.revoked_at is not None:
        return None
    moment = timezone.now()
    if row.expires_at <= moment or row.last_seen_at + timedelta(seconds=_idle_seconds()) <= moment:
        UserSession.objects.filter(pk=row.pk, revoked_at__isnull=True).update(revoked_at=moment)
        return None
    if moment - row.last_seen_at >= timedelta(seconds=_TOUCH_SECONDS):
        UserSession.objects.filter(pk=row.pk).update(last_seen_at=moment)
        row.last_seen_at = moment
    return row


def revoke(row: UserSession, *, now: datetime | None = None) -> None:
    UserSession.objects.filter(pk=row.pk, revoked_at__isnull=True).update(
        revoked_at=now or timezone.now()
    )


def revoke_others(user: User, *, keep_key: str | None = None, now: datetime | None = None) -> int:
    """End every live session of the account except the one that keeps ``keep_key``."""
    rows = UserSession.objects.filter(user=user, revoked_at__isnull=True)
    if keep_key:
        rows = rows.exclude(session_key_hash=key_hash(keep_key))
    return rows.update(revoked_at=now or timezone.now())


def revoke_all(user: User, *, now: datetime | None = None) -> int:
    return revoke_others(user, now=now)
