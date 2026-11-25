"""DRF throttles keyed by the verified ``user_ref`` (``docs/api.md`` §1, §6 of configuration)."""

from __future__ import annotations

from typing import Any

from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle


class AcademyAnonThrottle(AnonRateThrottle):
    """Unauthenticated traffic is limited per client address."""

    scope = "anon"


class AcademyUserThrottle(ScopedRateThrottle):
    """Use the view's ``throttle_scope`` and the verified identity as the bucket."""

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        access = getattr(request, "academy_access", None)
        if access is None:
            return None
        return self.cache_format % {"scope": self.scope, "ident": access.principal.user_ref}
