"""Learner progress API — ``docs/api.md`` §3 and §7.

The views only validate shape: the credit window, the gating check and the completion rules live
in :mod:`academy.progress`. Every response is personalised, so it is marked ``private, no-store``
and never cached.
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from academy import progress
from academy.authorization.core import Access, Capability
from academy.authorization.django import AcademyPermission


def _access(request: Request) -> Access:
    return request.auth


# --- serializers ------------------------------------------------------------


class HeartbeatSerializer(serializers.Serializer):
    from_seconds = serializers.FloatField(min_value=0)
    to_seconds = serializers.FloatField(min_value=0)
    playback_rate = serializers.FloatField(min_value=0, required=False, default=1.0)


class HeartbeatResponseSerializer(serializers.Serializer):
    position_seconds = serializers.FloatField()
    watched_seconds = serializers.FloatField()
    frontier_seconds = serializers.FloatField()
    coverage_percent = serializers.FloatField()
    skippable_seconds = serializers.FloatField()


class LessonCompletionSerializer(serializers.Serializer):
    lesson_id = serializers.UUIDField()
    completed_at = serializers.DateTimeField(allow_null=True)
    coverage_percent = serializers.FloatField()
    required_percent = serializers.IntegerField()


class AcknowledgmentSerializer(serializers.Serializer):
    enrollment_id = serializers.UUIDField()
    acknowledged = serializers.BooleanField()
    acknowledged_at = serializers.DateTimeField(allow_null=True)


class EnrollmentCompletionSerializer(serializers.Serializer):
    enrollment_id = serializers.UUIDField()
    status = serializers.CharField()
    completed_at = serializers.DateTimeField(allow_null=True)
    method = serializers.CharField()
    progress_percent = serializers.IntegerField()


class OverrideSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


def _private(payload: dict[str, Any], *, status_code: int = 200) -> Response:
    response = Response(payload, status=status_code)
    response["Cache-Control"] = "private, no-store"
    return response


# --- learner actions --------------------------------------------------------


class LessonProgressView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.LEARN
    throttle_scope = "heartbeat"

    @extend_schema(request=HeartbeatSerializer, responses=HeartbeatResponseSerializer)
    def post(self, request: Request, enrollment_id: Any, lesson_id: Any) -> Response:
        serializer = HeartbeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        payload = progress.record_heartbeat(
            _access(request),
            enrollment_id,
            lesson_id,
            from_seconds=float(data["from_seconds"]),
            to_seconds=float(data["to_seconds"]),
            playback_rate=float(data.get("playback_rate", 1.0)),
        )
        return _private(payload)


class LessonCompleteView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.LEARN
    throttle_scope = "write"

    @extend_schema(request=None, responses=LessonCompletionSerializer)
    def post(self, request: Request, enrollment_id: Any, lesson_id: Any) -> Response:
        payload = progress.complete_lesson(_access(request), enrollment_id, lesson_id)
        return _private(payload)


class AcknowledgeView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.LEARN
    throttle_scope = "write"

    @extend_schema(request=None, responses=AcknowledgmentSerializer)
    def post(self, request: Request, enrollment_id: Any) -> Response:
        payload = progress.acknowledge(_access(request), enrollment_id)
        return _private(payload)


class EnrollmentCompleteView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.LEARN
    throttle_scope = "write"

    @extend_schema(request=None, responses=EnrollmentCompletionSerializer)
    def post(self, request: Request, enrollment_id: Any) -> Response:
        payload = progress.complete_enrollment(_access(request), enrollment_id)
        return _private(payload)


# --- management: admin override --------------------------------------------


class EnrollmentOverrideCompleteView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.ADMIN
    throttle_scope = "write"

    @extend_schema(request=OverrideSerializer, responses=EnrollmentCompletionSerializer)
    def post(self, request: Request, enrollment_id: Any) -> Response:
        serializer = OverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = progress.override_complete_enrollment(
            _access(request),
            enrollment_id,
            reason=str(serializer.validated_data["reason"]),
        )
        return _private(payload)
