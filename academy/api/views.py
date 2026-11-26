"""Skeleton endpoints — ``docs/api.md`` §3.

Only the endpoint whose data already exists (the caller's effective capabilities) is wired.
Learner, content, assignment and report routes arrive with the services they call.
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from academy.api.serializers import CapabilitiesSerializer, OrganizationContextSerializer
from academy.authorization.core import Access
from academy.exceptions import MembershipInactive
from academy.models import Membership, Organization


class MeCapabilitiesView(APIView):
    """Effective capabilities and scopes of the verified caller (``docs/api.md`` §3)."""

    @extend_schema(responses=CapabilitiesSerializer)
    def get(self, request: Request) -> Response:
        access: Access = request.auth
        capabilities: list[dict[str, Any]] = []
        for capability, scope in sorted(access.capabilities.items()):
            if scope.all_departments:
                capabilities.append({"capability": str(capability), "scope_type": "organization"})
            else:
                capabilities.append(
                    {
                        "capability": str(capability),
                        "scope_type": "department",
                        "departments": sorted(scope.departments),
                    }
                )
        payload: dict[str, Any] = {
            "user_ref": access.principal.user_ref,
            "organization_id": access.principal.organization_id,
            "capabilities": capabilities,
        }
        return Response(payload, headers={"Cache-Control": "private, no-store"})


class MeOrganizationView(APIView):
    """The caller's single company (``docs/api.md`` §4).

    The company is read from the membership that resolved the caller's access. A company id in
    the query string or a header is never read, so it cannot select a tenant; a caller with no
    active membership is refused with ``membership_inactive``.
    """

    @extend_schema(responses=OrganizationContextSerializer)
    def get(self, request: Request) -> Response:
        access: Access = request.auth
        membership_id = access.principal.membership_id
        row = (
            Membership.objects.select_related("department")
            .filter(pk=membership_id, status=Membership.Status.ACTIVE)
            .first()
            if membership_id is not None
            else None
        )
        if row is None:
            raise MembershipInactive("the account has no active company membership")
        organization = Organization.objects.filter(pk=row.organization_id).first()
        if organization is None:
            raise MembershipInactive("the membership's company no longer exists")
        department = row.department
        payload: dict[str, Any] = {
            "organization": {
                "id": organization.pk,
                "name_ar": organization.name_ar,
                "name_en": organization.name_en,
                "slug": organization.slug,
                "status": organization.status,
                "default_language": organization.default_language,
                "timezone": organization.timezone,
                "reminder_hour": organization.reminder_hour,
            },
            "membership": {
                "id": row.pk,
                "status": row.status,
                "department": (
                    {"id": department.pk, "name_ar": department.name_ar}
                    if department is not None
                    else None
                ),
            },
        }
        return Response(payload, headers={"Cache-Control": "private, no-store"})
