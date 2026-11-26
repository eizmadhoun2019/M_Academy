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


class DepartmentContextSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name_ar = serializers.CharField()


class OrganizationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name_ar = serializers.CharField()
    name_en = serializers.CharField(allow_null=True)
    slug = serializers.CharField()
    status = serializers.CharField()
    default_language = serializers.CharField()
    timezone = serializers.CharField()
    reminder_hour = serializers.IntegerField()


class MembershipContextSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    department = DepartmentContextSerializer(allow_null=True)


class OrganizationContextSerializer(serializers.Serializer):
    """The caller's single company — ``docs/api.md`` §4."""

    organization = OrganizationSerializer()
    membership = MembershipContextSerializer()
