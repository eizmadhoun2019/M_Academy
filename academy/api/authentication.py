"""API authentication bridge.

The identity layer (T-014/T-015) verifies the request and stores the resolved
:class:`~academy.authorization.core.Access` on ``request.academy_access``. This class only
refuses requests without it, so a missing context is a 401 instead of an unscoped request.
"""

from __future__ import annotations

from typing import Any

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import NotAuthenticated

from academy.access.principals import (
    session_email_unverified,
    session_mfa_enrollment_required,
    session_without_membership,
)
from academy.authorization.core import Access
from academy.exceptions import (
    AccessSuspended,
    EmailUnverified,
    InactiveAccount,
    MembershipInactive,
    MFAEnrollmentRequired,
)

#: The auth routes themselves stay reachable, so an account that must enrol can enrol (T-027 CP2).
_SELF_SERVICE_PREFIX = "/api/v1/academy/auth/"


class AcademyAccessAuthentication(BaseAuthentication):
    """Authenticate only when the request already carries a resolved access."""

    def authenticate(self, request: Any) -> tuple[Any, Access]:
        # A role that mandates a second factor refuses tenant data until one is enrolled. The
        # auth routes stay reachable, so the account can enrol or sign out.
        self_service = str(getattr(request, "path", "")).startswith(_SELF_SERVICE_PREFIX)
        if not self_service and session_mfa_enrollment_required(request):
            raise MFAEnrollmentRequired("enrol a second factor before using the API")
        access = getattr(request, "academy_access", None)
        if not isinstance(access, Access):
            # A signed-in account that has not verified its address cannot reach tenant data.
            if session_email_unverified(request):
                raise EmailUnverified("verify the account email before using the API")
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
