"""Reports API — ``docs/api.md`` §6, numbers defined by ``docs/reports.md``.

The views validate the query string, call one selector and render it; no figure is computed
here, so the CSV export and the JSON rows cannot disagree. Scope is enforced by the selector,
which answers ``403 forbidden`` for a cross-department filter instead of an empty list.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import StreamingHttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.pagination import CursorPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from academy.api.pagination import AcademyPagination
from academy.audit import service as audit
from academy.authorization.core import Access, Capability
from academy.authorization.django import AcademyPermission
from academy.reports import csv_export, selectors

PRIVATE = {"Cache-Control": "private, no-store"}


def _access(request: Request) -> Access:
    return request.auth


# --- query strings ----------------------------------------------------------


FROM = OpenApiParameter("from", OpenApiTypes.DATE, OpenApiParameter.QUERY, required=False)
TO = OpenApiParameter("to", OpenApiTypes.DATE, OpenApiParameter.QUERY, required=False)


class ReportFiltersSerializer(serializers.Serializer):
    course = serializers.UUIDField(required=False)
    department_ref = serializers.CharField(required=False, allow_blank=True, max_length=64)


class SummaryQuerySerializer(ReportFiltersSerializer):
    group_by = serializers.ChoiceField(choices=list(selectors.GROUPINGS), required=False)


class OverdueQuerySerializer(ReportFiltersSerializer):
    min_days_overdue = serializers.IntegerField(required=False, min_value=0)


class CompletionQuerySerializer(ReportFiltersSerializer):
    status = serializers.ChoiceField(choices=list(selectors.COMPLETION_STATUSES), required=False)


class ExportQuerySerializer(CompletionQuerySerializer):
    columns = serializers.CharField(required=False, allow_blank=True)


def _filters(request: Request, serializer: Any) -> dict[str, Any]:
    """The documented filter names, with the empty string read as "not set".

    ``from``/``to`` are read straight from the query string: the selectors validate them, and
    ``from`` cannot be a serializer field name because it is a Python keyword.
    """
    data = serializer.validated_data
    return {
        "course_id": data.get("course"),
        "department_ref": data.get("department_ref") or None,
        "start": request.query_params.get("from") or None,
        "end": request.query_params.get("to") or None,
    }


# --- response shapes --------------------------------------------------------


class SummaryRowSerializer(serializers.Serializer):
    group_key = serializers.CharField()
    group_label = serializers.CharField()
    eligible = serializers.IntegerField()
    completed = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    not_started = serializers.IntegerField()
    overdue = serializers.IntegerField()
    completion_percent = serializers.DecimalField(max_digits=4, decimal_places=1)
    average_completion_days = serializers.DecimalField(
        max_digits=6, decimal_places=1, allow_null=True
    )
    mandatory_eligible = serializers.IntegerField()


class SummaryTotalsSerializer(serializers.Serializer):
    eligible = serializers.IntegerField()
    completed = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    not_started = serializers.IntegerField()
    overdue = serializers.IntegerField()
    completion_percent = serializers.DecimalField(max_digits=4, decimal_places=1)
    average_completion_days = serializers.DecimalField(
        max_digits=6, decimal_places=1, allow_null=True
    )
    mandatory_eligible = serializers.IntegerField()


class SummaryResponseSerializer(serializers.Serializer):
    rows = SummaryRowSerializer(many=True)
    totals = SummaryTotalsSerializer()
    generated_at = serializers.DateTimeField()


class OverdueRowSerializer(serializers.Serializer):
    enrollment_id = serializers.UUIDField()
    user_ref = serializers.CharField()
    course_title = serializers.CharField()
    due_at = serializers.DateTimeField()
    days_overdue = serializers.IntegerField()
    progress_percent = serializers.DecimalField(max_digits=4, decimal_places=1)
    last_activity_at = serializers.DateTimeField(allow_null=True)
    mandatory = serializers.BooleanField()


class CompletionRowSerializer(serializers.Serializer):
    enrollment_id = serializers.UUIDField()
    user_ref = serializers.CharField()
    course_title = serializers.CharField()
    version_number = serializers.IntegerField()
    status = serializers.CharField()
    progress_percent = serializers.DecimalField(max_digits=4, decimal_places=1)
    completed_at = serializers.DateTimeField(allow_null=True)
    method = serializers.CharField(allow_null=True)
    due_at = serializers.DateTimeField(allow_null=True)
    days_overdue = serializers.IntegerField()


# --- pagination -------------------------------------------------------------


class ReportCursorPagination(CursorPagination):
    """Opt-in cursor paging; ``ACADEMY_CURSOR_PAGE_SIZE`` rows per page (§4 of reports.md)."""

    ordering = ("pk",)
    cursor_query_param = "cursor"

    def get_page_size(self, request: Any) -> int | None:
        return int(getattr(settings, "ACADEMY_CURSOR_PAGE_SIZE", 50))


# --- views ------------------------------------------------------------------


class ReportSummaryView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.VIEW_REPORTS
    throttle_scope = "read"

    @extend_schema(
        parameters=[SummaryQuerySerializer, FROM, TO], responses=SummaryResponseSerializer
    )
    def get(self, request: Request) -> Response:
        query = SummaryQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        payload = selectors.summary(
            _access(request),
            group_by=query.validated_data.get("group_by") or "course",
            **_filters(request, query),
        )
        return Response(
            SummaryResponseSerializer(payload).data,
            headers=PRIVATE,
        )


class ReportOverdueView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.VIEW_REPORTS
    throttle_scope = "read"

    @extend_schema(
        parameters=[OverdueQuerySerializer, FROM, TO],
        responses=OverdueRowSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        query = OverdueQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        rows = selectors.overdue(
            _access(request),
            min_days_overdue=query.validated_data.get("min_days_overdue") or 0,
            **_filters(request, query),
        )
        paginator = AcademyPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        payload = [selectors.overdue_payload(row) for row in page]
        response = paginator.get_paginated_response(OverdueRowSerializer(payload, many=True).data)
        response["Cache-Control"] = "private, no-store"
        return response


class ReportCompletionView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.VIEW_REPORTS
    throttle_scope = "read"

    @extend_schema(
        parameters=[CompletionQuerySerializer, FROM, TO],
        responses=CompletionRowSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        query = CompletionQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        rows = selectors.completion(
            _access(request),
            status=query.validated_data.get("status") or "all",
            **_filters(request, query),
        )
        cursor = request.query_params.get("cursor")
        paginator: Any = ReportCursorPagination() if cursor is not None else AcademyPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        payload = [selectors.completion_payload(row) for row in page]
        response = paginator.get_paginated_response(
            CompletionRowSerializer(payload, many=True).data
        )
        response["Cache-Control"] = "private, no-store"
        return response


class ReportExportView(APIView):
    permission_classes = [AcademyPermission]
    academy_capability = Capability.VIEW_REPORTS
    throttle_scope = "export"

    @extend_schema(
        parameters=[ExportQuerySerializer, FROM, TO],
        responses={(200, "text/csv"): OpenApiTypes.STR},
    )
    def get(self, request: Request) -> StreamingHttpResponse:
        query = ExportQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        columns = _columns(data.get("columns"))
        start_at = request.query_params.get("from") or None
        end_at = request.query_params.get("to") or None
        access = _access(request)
        rows = selectors.completion(
            access,
            status=data.get("status") or "all",
            **_filters(request, query),
        )
        audit.record(
            organization_id=access.principal.organization_id,
            actor_ref=access.principal.user_ref,
            action="report.exported",
            object_type="Report",
            object_id="completion",
            metadata={
                "course_id": str(data["course"]) if data.get("course") else None,
                "department_ref": data.get("department_ref") or None,
                "status": data.get("status") or "all",
                "from_date": start_at,
                "to_date": end_at,
                "columns": ",".join(columns),
            },
        )
        payload = (selectors.completion_payload(row) for row in rows.iterator())
        response = StreamingHttpResponse(
            csv_export.stream(payload, columns), content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{csv_export.filename(start_at, end_at)}"'
        )
        response["Cache-Control"] = "private, no-store"
        return response


def _columns(selected: str | None) -> tuple[str, ...]:
    """The requested allowlist in the requested order; unknown names are refused."""
    if not selected:
        return selectors.EXPORT_COLUMNS
    requested = [name.strip() for name in selected.split(",") if name.strip()]
    unknown = [name for name in requested if name not in selectors.EXPORT_COLUMNS]
    if unknown:
        raise serializers.ValidationError(
            {"columns": [f"unknown column {name!r}" for name in unknown]},
            code="validation_error",
        )
    if not requested:
        return selectors.EXPORT_COLUMNS
    return tuple(dict.fromkeys(requested))
