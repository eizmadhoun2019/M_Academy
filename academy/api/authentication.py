"""API authentication bridge.

The identity layer (T-014/T-015) verifies the request and stores the resolved
:class:`~academy.authorization.core.Access` on ``request.academy_access``. This class only
refuses requests without it, so a missing context is a 401 instead of an unscoped request.
"""

from __future__ import annotations

from typing import Any

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import NotAuthenticated

from academy.authorization.core import Access


class AcademyAccessAuthentication(BaseAuthentication):
    """Authenticate only when the request already carries a resolved access."""

    def authenticate(self, request: Any) -> tuple[Any, Access]:
        access = getattr(request, "academy_access", None)
        if not isinstance(access, Access):
            raise NotAuthenticated("no verified Academy identity")
        return (access.principal, access)

    def authenticate_header(self, request: Any) -> str:
        return "Academy"
