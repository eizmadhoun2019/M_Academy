"""Response shapes the skeleton exposes today (``docs/api.md`` §3)."""

from __future__ import annotations

from rest_framework import serializers


class CapabilityScopeSerializer(serializers.Serializer):
    capability = serializers.CharField()
    scope_type = serializers.ChoiceField(choices=["organization", "department"])
    departments = serializers.ListField(child=serializers.CharField(), required=False)


class CapabilitiesSerializer(serializers.Serializer):
    user_ref = serializers.CharField()
    organization_id = serializers.UUIDField()
    capabilities = CapabilityScopeSerializer(many=True)
