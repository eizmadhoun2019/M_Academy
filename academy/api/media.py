"""Media management API — ``docs/api.md`` §4."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from academy.authorization.core import Access, Capability
from academy.authorization.django import AcademyPermission
from academy.exceptions import MediaUploadError
from academy.media import service
from academy.models import MediaAsset


def _access(request: Request) -> Access:
    return request.auth


def _org(request: Request) -> Any:
    return _access(request).principal.organization_id


class MediaUploadSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=[item.value for item in MediaAsset.Kind])
    original_filename = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True
    )
    content_type = serializers.CharField(max_length=100)
    size_bytes = serializers.IntegerField(min_value=0)


class MediaSerializer(serializers.ModelSerializer):
    # A plain read-only string keeps the media status out of the shared enum namespace: the
    # asset state machine is documented in docs/domain-model.md §5, not in the schema enums.
    status = serializers.CharField(read_only=True)

    class Meta:
        model = MediaAsset
        fields = [
            "id",
            "kind",
            "status",
            "storage_key",
            "original_filename",
            "content_type",
            "size_bytes",
            "checksum_sha256",
            "duration_seconds",
            "renditions",
            "error_code",
            "attempt_count",
            "ready_at",
            "created_by_ref",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class MediaUploadCreateView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(request=MediaUploadSerializer, responses=MediaSerializer)
    def post(self, request: Request) -> Response:
        serializer = MediaUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        access = _access(request)
        try:
            asset = service.create_upload(
                access,
                kind=str(data["kind"]),
                original_filename=data.get("original_filename"),
                content_type=str(data["content_type"]),
                size_bytes=int(data["size_bytes"]),
            )
        except MediaUploadError:
            raise  # handled by academy_exception_handler? It's AcademyError subclass -> yes
        upload_url = getattr(asset, "upload_url", None)
        if upload_url is None:
            upload_url = service.presigned_upload_url(asset)
        payload = dict(MediaSerializer(asset).data)
        payload["upload_url"] = upload_url
        return Response(payload, status=status.HTTP_201_CREATED)


class MediaDetailView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(responses=MediaSerializer)
    def get(self, request: Request, media_id: Any) -> Response:
        access = _access(request)
        asset = service.require_asset(access, _org(request), media_id)
        return Response(MediaSerializer(asset).data)


class MediaCompleteView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(request=None, responses=MediaSerializer)
    def post(self, request: Request, media_id: Any) -> Response:
        access = _access(request)
        asset = service.require_asset(access, _org(request), media_id)
        asset = service.complete_upload(access, asset)
        return Response(MediaSerializer(asset).data)


class MediaRetryView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.MANAGE_CONTENT
    throttle_scope = "write"

    @extend_schema(request=None, responses=MediaSerializer)
    def post(self, request: Request, media_id: Any) -> Response:
        access = _access(request)
        asset = service.require_asset(access, _org(request), media_id)
        asset = service.retry_upload(access, asset)
        return Response(MediaSerializer(asset).data)


class PlaybackView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.LEARN
    throttle_scope = "read"

    @extend_schema(request=None, responses=None)
    def post(self, request: Request, enrollment_id: Any, lesson_id: Any) -> Response:
        access = _access(request)
        payload = service.playback_urls(access, enrollment_id, lesson_id)
        response = Response(payload)
        response["Cache-Control"] = "private, no-store"
        return response
