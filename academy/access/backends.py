"""Email + password authentication backend (D-033, ``docs/security.md`` §2).

The email is the login attribute, never a relation key: it is matched case-insensitively and the
outcome is identical for an unknown address and a wrong password. An unknown account still pays
for one hash verification, so response time does not reveal whether the address exists.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth.hashers import check_password, make_password

from academy.models import User

#: Computed once; verifying against it makes the "no such account" path cost the same as a real
#: password check, without holding any account's secret.
_DUMMY_HASH = make_password("academy-timing-equalizer")


class EmailPasswordBackend:
    """Authenticate an active Academy account by email and password."""

    def authenticate(
        self,
        request: Any = None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> User | None:
        email = str(username or kwargs.get("email") or "").strip().lower()
        secret = password or ""
        if not email:
            return None
        user = User.objects.filter(email__iexact=email).first()
        if user is None or not user.has_usable_password():
            check_password(secret, _DUMMY_HASH)
            return None
        if not user.check_password(secret) or not user.is_active:
            return None
        return user

    def get_user(self, user_id: Any) -> User | None:
        if user_id is None:
            return None
        user = User.objects.filter(pk=user_id).first()
        return user if user is not None and user.is_active else None
