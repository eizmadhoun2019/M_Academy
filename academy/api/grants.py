"""Administration grants — ``docs/api.md`` §7.

Listing is read-only and tenant-scoped; creation and revocation go through the grant service so
the last-admin guard and the audit row are never bypassed by an HTTP caller.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from django.core.cache import cache
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from academy.api.pagination import AcademyPagination
from academy.authorization.core import Access, Capability
from academy.authorization.django import AcademyPermission
from academy.exceptions import Conflict, NotFound
from academy.grants.service import grant, revoke
from academy.models import PermissionGrant

IDEMPOTENCY_TTL = 24 * 60 * 60


class GrantSerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()

    class Meta:
        model = PermissionGrant
        fields = [
            "id",
            "user_ref",
            "capability",
            "scope_type",
            "scope_ref",
            "granted_by_ref",
            "created_at",
            "expires_at",
            "revoked_at",
            "revoked_by_ref",
            "state",
        ]
        read_only_fields = fields

    def get_state(self, row: PermissionGrant) -> str:
        if row.revoked_at is not None:
            return "revoked"
        if row.expires_at is not None and row.expires_at <= timezone.now():
            return "expired"
        return "active"


class GrantCreateSerializer(serializers.Serializer):
    user_ref = serializers.RegexField(regex=r"^[A-Za-z0-9_-]{1,64}$", max_length=64)
    capability = serializers.ChoiceField(choices=[item.value for item in Capability])
    scope_type = serializers.ChoiceField(choices=["organization", "department"])
    scope_ref = serializers.CharField(max_length=64, required=False, allow_null=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        scope_ref = attrs.get("scope_ref")
        if attrs["scope_type"] == "department" and not scope_ref:
            raise serializers.ValidationError({"scope_ref": "required for a department grant"})
        if attrs["scope_type"] == "organization" and scope_ref:
            raise serializers.ValidationError(
                {"scope_ref": "an organization grant cannot carry a department reference"}
            )
        return attrs


def _organization(request: Request) -> Any:
    access: Access = request.auth
    return access.principal.organization_id


def _actor(request: Request) -> str:
    access: Access = request.auth
    return access.principal.user_ref


def _replay_key(request: Request, organization_id: Any) -> str | None:
    key = request.headers.get("Idempotency-Key", "").strip()
    if not key:
        return None
    return f"macademy:idempotency:grant:{organization_id}:{key}"


@extend_schema(request=GrantCreateSerializer, responses=GrantSerializer)
class GrantListCreateView(APIView):
    """List grants, or grant a capability (audited in the same transaction)."""

    permission_classes = [AcademyPermission]
    academy_capability = Capability.ADMIN
    throttle_scope = "write"

    @extend_schema(responses=GrantSerializer(many=True))
    def get(self, request: Request) -> Response:
        rows = PermissionGrant.objects.for_org(_organization(request)).order_by(
            "user_ref", "created_at"
        )
        user_ref = request.query_params.get("user_ref")
        capability = request.query_params.get("capability")
        state_filter = request.query_params.get("state")
        if user_ref:
            rows = rows.filter(user_ref=user_ref)
        if capability:
            rows = rows.filter(capability=str(capability).removeprefix("academy."))
        if state_filter == "revoked":
            rows = rows.filter(revoked_at__isnull=False)
        elif state_filter == "active":
            rows = rows.filter(revoked_at__isnull=True)
        elif state_filter == "expired":
            rows = rows.filter(revoked_at__isnull=True, expires_at__isnull=False)
        paginator = AcademyPagination()
        page = paginator.paginate_queryset(list(rows), request, view=self)
        return paginator.get_paginated_response(GrantSerializer(page, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = GrantCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        organization_id = _organization(request)
        cache_key = _replay_key(request, organization_id)
        digest = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
        if cache_key is not None:
            stored = cache.get(cache_key)
            if isinstance(stored, dict):
                if stored.get("digest") != digest:
                    raise Conflict("this Idempotency-Key was used for a different request")
                existing = PermissionGrant.objects.for_org(organization_id).get(
                    pk=stored["grant_id"]
                )
                return Response(GrantSerializer(existing).data, status=status.HTTP_200_OK)
        row = grant(
            organization_id=organization_id,
            actor_ref=_actor(request),
            user_ref=str(data["user_ref"]),
            capability=str(data["capability"]),
            scope_type=str(data["scope_type"]),
            scope_ref=data.get("scope_ref"),
            expires_at=data.get("expires_at"),
        )
        if cache_key is not None:
            cache.set(cache_key, {"digest": digest, "grant_id": str(row.pk)}, IDEMPOTENCY_TTL)
        return Response(GrantSerializer(row).data, status=status.HTTP_201_CREATED)


class GrantRevokeView(APIView):
    """Revoke one grant; 409 ``last_admin`` protects the final administrator."""

    permission_classes = [AcademyPermission]
    academy_capability = Capability.ADMIN
    throttle_scope = "write"

    @extend_schema(responses=GrantSerializer)
    def delete(self, request: Request, grant_id: Any) -> Response:
        organization_id = _organization(request)
        if not PermissionGrant.objects.for_org(organization_id).filter(pk=grant_id).exists():
            raise NotFound("grant not found")
        row = revoke(organization_id=organization_id, actor_ref=_actor(request), grant_id=grant_id)
        return Response(GrantSerializer(row).data)
