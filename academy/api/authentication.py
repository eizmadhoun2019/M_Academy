"""API authentication bridge.

The identity layer (T-014/T-015) verifies the request and stores the resolved
:class:`~academy.authorization.core.Access` on ``request.academy_access``. This class only
refuses requests without it, so a missing context is a 401 instead of an unscoped request.
"""

from __future__ import annotations

from typing import Any

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import NotAuthenticated

from academy.access.principals import session_without_membership
from academy.authorization.core import Access
from academy.exceptions import AccessSuspended, InactiveAccount, MembershipInactive


class AcademyAccessAuthentication(BaseAuthentication):
    """Authenticate only when the request already carries a resolved access."""

    def authenticate(self, request: Any) -> tuple[Any, Access]:
        access = getattr(request, "academy_access", None)
        if not isinstance(access, Access):
            # A signed-in account with no active membership has an identity but no company.
            if session_without_membership(request):
                raise MembershipInactive("the account has no active company membership")
            raise NotAuthenticated("no verified Academy identity")
        # A suspended or inactive member holds an identity but no capability: refuse before
        # any view can answer, so every endpoint rejects the caller the same way (D-028).
        if access.denied_reason == "suspended":
            raise AccessSuspended("the account is suspended in Academy")
        if access.denied_reason == "inactive":
            raise InactiveAccount("the account is inactive")
        return (access.principal, access)

    def authenticate_header(self, request: Any) -> str:
        return "Academy"
