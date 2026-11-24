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

from academy.api.serializers import CapabilitiesSerializer
from academy.authorization.core import Access


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
