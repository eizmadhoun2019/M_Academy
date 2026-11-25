"""Report selectors — every definition and column of ``docs/reports.md``.

The three read endpoints and the CSV export share these annotations, so ``completion_percent``
or ``days_overdue`` cannot drift between the screen and the file. Scope follows §6: a
department-scoped ``academy.view_reports`` holder sees the enrollments of their departments plus
the general courses (``owner_department_ref IS NULL``), and a cross-department filter is a
``403 forbidden`` instead of an empty list, because the caller asked for a department by name.

Each function runs a fixed number of queries: the per-enrollment figures are annotations
(``Exists`` / ``Subquery`` / conditional ``Count``), never a loop over rows.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.core.cache import cache
from django.db.models import (
    Avg,
    CharField,
    Count,
    DurationField,
    Exists,
    ExpressionWrapper,
    F,
    IntegerField,
    Max,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce, Extract
from django.utils import timezone

from academy.adapters.loader import load_adapter
from academy.authorization.core import Access, Capability
from academy.exceptions import DomainValidationError, Forbidden, InvalidRange
from academy.models import CompletionRecord, Course, Enrollment, Lesson, LessonProgress

GROUPINGS = ("course", "department_ref")
COMPLETION_STATUSES = ("active", "completed", "overdue", "all")
SUMMARY_COLUMNS = (
    "group_key",
    "group_label",
    "eligible",
    "completed",
    "in_progress",
    "not_started",
    "overdue",
    "completion_percent",
    "average_completion_days",
    "mandatory_eligible",
)
OVERDUE_COLUMNS = (
    "enrollment_id",
    "user_ref",
    "course_title",
    "due_at",
    "days_overdue",
    "progress_percent",
    "last_activity_at",
    "mandatory",
)
COMPLETION_COLUMNS = (
    "enrollment_id",
    "user_ref",
    "course_title",
    "version_number",
    "status",
    "progress_percent",
    "completed_at",
    "method",
    "due_at",
    "days_overdue",
)
EXPORT_COLUMNS = COMPLETION_COLUMNS

#: One decimal, half-up: ``50 / 150`` is ``33.3``, never ``33`` or ``33.3333``.
_ONE_DECIMAL = Decimal("0.1")
_SECONDS_PER_DAY = Decimal(86400)
_LABEL_TTL = 60


def directory() -> Any:
    """The organization seam, resolved on use like every other reader (ADR-012)."""
    return load_adapter("organization")()


# --- scope and window -------------------------------------------------------


def require_reports(access: Access) -> None:
    """The endpoint's class-level permission only proves the capability exists somewhere."""
    if not access.granted(Capability.VIEW_REPORTS):
        raise Forbidden("missing capability academy.view_reports")


def _scope_q(access: Access) -> Q:
    """Enrollments inside the caller's report scope (``docs/reports.md`` §6)."""
    if access.covers_all_departments(Capability.VIEW_REPORTS):
        return Q()
    refs = sorted(access.capabilities[Capability.VIEW_REPORTS].departments)
    return Q(course__owner_department_ref__in=refs) | Q(course__owner_department_ref__isnull=True)


def _require_department(access: Access, department_ref: str | None) -> None:
    if department_ref is None:
        return
    if not access.allows(Capability.VIEW_REPORTS, department_ref=department_ref):
        raise Forbidden("the department is outside your report scope")


def _require_course(access: Access, organization_id: Any, course_id: Any) -> None:
    """A named course is read only when it is in scope; a general course always is."""
    if course_id is None:
        return
    course = Course.objects.for_org(organization_id).filter(pk=course_id).first()
    if course is None:
        # Same answer for missing and out of scope: no cross-department hint.
        raise Forbidden("the course is outside your report scope")
    if course.owner_department_ref is None or access.covers_all_departments(
        Capability.VIEW_REPORTS
    ):
        return
    if not access.allows(Capability.VIEW_REPORTS, department_ref=course.owner_department_ref):
        raise Forbidden("the course is outside your report scope")


def parse_bound(value: Any, name: str) -> datetime | None:
    """A ``from``/``to`` date as an inclusive UTC day boundary (``docs/reports.md`` §1)."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        moment = datetime.combine(value, time.min, tzinfo=UTC)
    else:
        try:
            moment = datetime.combine(date.fromisoformat(str(value)), time.min, tzinfo=UTC)
        except ValueError as exc:
            raise DomainValidationError(
                f"{name} must be an ISO-8601 date", fields={name: ["invalid_date"]}
            ) from exc
    return moment + timedelta(days=1) if name == "to" else moment


def window(start: Any, end: Any) -> tuple[datetime | None, datetime | None]:
    """Validate and return the half-open window ``[start, end)`` of the filters."""
    low = parse_bound(start, "from")
    high = parse_bound(end, "to")
    if low is not None and high is not None and low >= high:
        raise InvalidRange("'from' must be on or before 'to'")
    return low, high


def _apply_window(
    rows: QuerySet[Enrollment], field: str, start: datetime | None, end: datetime | None
) -> QuerySet[Enrollment]:
    if start is not None:
        rows = rows.filter(**{f"{field}__gte": start})
    if end is not None:
        rows = rows.filter(**{f"{field}__lt": end})
    return rows


def _eligible(
    access: Access, *, course_id: Any = None, department_ref: str | None = None
) -> QuerySet[Enrollment]:
    """Eligible enrollments (``active``/``completed``) inside scope and filters."""
    require_reports(access)
    organization_id = access.principal.organization_id
    _require_department(access, department_ref)
    _require_course(access, organization_id, course_id)
    rows = Enrollment.objects.for_org(organization_id).filter(
        Q(status=Enrollment.Status.ACTIVE) | Q(status=Enrollment.Status.COMPLETED)
    )
    rows = rows.filter(_scope_q(access))
    if course_id is not None:
        rows = rows.filter(course_id=course_id)
    if department_ref is not None:
        rows = rows.filter(course__owner_department_ref=department_ref)
    return rows


# --- per-enrollment figures -------------------------------------------------


def _started() -> Exists:
    return Exists(
        LessonProgress.objects.filter(
            organization_id=OuterRef("organization_id"),
            enrollment=OuterRef("pk"),
            watched_seconds__gt=0,
        )
    )


def _completed_lessons() -> Count:
    return Count("lesson_progress", filter=Q(lesson_progress__completed_at__isnull=False))


def _lessons_in_version() -> Subquery:
    lessons = (
        Lesson.objects.filter(
            organization_id=OuterRef("organization_id"),
            section__version=OuterRef("course_version_id"),
        )
        .order_by()
        .values("section__version")
        .annotate(total=Count("pk"))
        .values("total")
    )
    return Subquery(lessons, output_field=IntegerField())


def _annotated(rows: QuerySet[Enrollment]) -> QuerySet[Enrollment]:
    """Attach the two figures §1 needs per enrollment, in one query."""
    return rows.annotate(
        completed_lessons=_completed_lessons(),
        lessons_in_version=Coalesce(_lessons_in_version(), Value(0)),
        last_activity_at=Max("lesson_progress__last_heartbeat_at"),
    )


def one_decimal(numerator: Any, denominator: Any) -> Decimal:
    """``numerator / denominator × 100`` with one decimal, ``0.0`` when nothing to divide."""
    try:
        denominator_value = Decimal(str(denominator))
        numerator_value = Decimal(str(numerator))
    except Exception:  # pragma: no cover - values come from the database as numbers
        return Decimal("0.0")
    if denominator_value == 0:
        return Decimal("0.0")
    return (numerator_value / denominator_value * 100).quantize(
        _ONE_DECIMAL, rounding=ROUND_HALF_UP
    )


def progress_percent(row: Any) -> Decimal:
    return one_decimal(row.completed_lessons, row.lessons_in_version)


def days_overdue(due_at: datetime | None, now: datetime) -> int:
    """``floor((now − due) / 1 day)``, minimum 0 (§1); a learner at ``due`` is not overdue."""
    if due_at is None or due_at >= now:
        return 0
    return max(0, (now - due_at).days)


def average_days(seconds: Any) -> Decimal | None:
    if seconds is None:
        return None
    return (Decimal(str(seconds)) / _SECONDS_PER_DAY).quantize(_ONE_DECIMAL, rounding=ROUND_HALF_UP)


# --- labels -----------------------------------------------------------------


def _department_labels(organization_id: Any) -> dict[str, str]:
    """Department names for display only, cached 60 s, empty when the Hub is unavailable."""
    key = f"academy:reports:departments:{organization_id}"
    cached = cache.get(key)
    if isinstance(cached, dict):
        return cached
    try:
        labels = {row.ref: row.name for row in directory().departments(organization_id)}
    except Exception:
        # A directory outage must not fail a report: the key stands in for the name.
        labels = {}
    cache.set(key, labels, _LABEL_TTL)
    return labels


def _course_labels(organization_id: Any, keys: Sequence[Any]) -> dict[str, str]:
    found = Course.objects.for_org(organization_id).filter(pk__in=list(keys))
    return {str(row.pk): row.title for row in found}


def _labels(access: Access, group_by: str, keys: Sequence[Any]) -> dict[str, str]:
    organization_id = access.principal.organization_id
    if group_by == "course":
        return _course_labels(organization_id, keys)
    labels = _department_labels(organization_id)
    general = _organization_name()
    return {str(key or ""): general if not key else labels.get(str(key), str(key)) for key in keys}


def _organization_name() -> str:
    from django.conf import settings

    return str(getattr(settings, "ACADEMY_ORGANIZATION_NAME", "")).strip() or "Academy"


# --- summary ----------------------------------------------------------------


def _summary_aggregates() -> dict[str, Any]:
    now = timezone.now()
    return {
        "eligible": Count("pk"),
        "completed": Count("pk", filter=Q(status=Enrollment.Status.COMPLETED)),
        "in_progress": Count("pk", filter=Q(status=Enrollment.Status.ACTIVE, started=True)),
        "overdue": Count(
            "pk",
            filter=Q(
                status=Enrollment.Status.ACTIVE,
                due_at__isnull=False,
                due_at__lt=now,
            ),
        ),
        "mandatory_eligible": Count("pk", filter=Q(mandatory=True)),
        "average_seconds": Avg("age_seconds", filter=Q(status=Enrollment.Status.COMPLETED)),
    }


def _summary_row(group_key: Any, values: Mapping[str, Any], label: str) -> dict[str, Any]:
    eligible = int(values["eligible"])
    completed = int(values["completed"])
    in_progress = int(values["in_progress"])
    return {
        "group_key": str(group_key or ""),
        "group_label": label,
        "eligible": eligible,
        "completed": completed,
        "in_progress": in_progress,
        "not_started": eligible - completed - in_progress,
        "overdue": int(values["overdue"]),
        "completion_percent": one_decimal(completed, eligible),
        "average_completion_days": average_days(values["average_seconds"]),
        "mandatory_eligible": int(values["mandatory_eligible"]),
    }


def _totals(values: Mapping[str, Any]) -> dict[str, Any]:
    eligible = int(values["eligible"])
    completed = int(values["completed"])
    in_progress = int(values["in_progress"])
    return {
        "eligible": eligible,
        "completed": completed,
        "in_progress": in_progress,
        "not_started": eligible - completed - in_progress,
        "overdue": int(values["overdue"]),
        # Summed counts, never the mean of the row percentages (§2).
        "completion_percent": one_decimal(completed, eligible),
        "average_completion_days": average_days(values["average_seconds"]),
        "mandatory_eligible": int(values["mandatory_eligible"]),
    }


def summary(
    access: Access,
    *,
    group_by: str = "course",
    course_id: Any = None,
    department_ref: str | None = None,
    start: Any = None,
    end: Any = None,
) -> dict[str, Any]:
    """``GET /manage/reports/summary/`` — §2, grouped and totalled in two queries."""
    if group_by not in GROUPINGS:
        raise DomainValidationError(
            "group_by must be one of the documented values", fields={"group_by": list(GROUPINGS)}
        )
    low, high = window(start, end)
    field = "course_id" if group_by == "course" else "course__owner_department_ref"

    rows = _apply_window(
        _eligible(access, course_id=course_id, department_ref=department_ref),
        "created_at",
        low,
        high,
    )
    seconds = Extract(
        ExpressionWrapper(F("completed_at") - F("created_at"), output_field=DurationField()),
        "epoch",
    )
    annotated = rows.annotate(started=_started(), age_seconds=seconds)
    grouped = list(annotated.values(field).annotate(**_summary_aggregates()).order_by(field))
    labels = _labels(access, group_by, [row[field] for row in grouped])
    payload_rows = [
        _summary_row(row[field], row, labels.get(str(row[field] or ""), str(row[field] or "")))
        for row in grouped
    ]

    totals_values = annotated.aggregate(**_summary_aggregates())
    return {
        "rows": payload_rows,
        "totals": _totals(totals_values),
        "generated_at": timezone.now(),
    }


# --- overdue ----------------------------------------------------------------


def overdue(
    access: Access,
    *,
    course_id: Any = None,
    department_ref: str | None = None,
    min_days_overdue: int = 0,
    start: Any = None,
    end: Any = None,
) -> QuerySet[Enrollment]:
    """``GET /manage/reports/overdue/`` — §3, one query, sorted by ``due_at`` (days desc)."""
    low, high = window(start, end)
    if min_days_overdue < 0:
        raise DomainValidationError(
            "min_days_overdue cannot be negative", fields={"min_days_overdue": ["min_value"]}
        )
    now = timezone.now()
    rows = _eligible(access, course_id=course_id, department_ref=department_ref).filter(
        status=Enrollment.Status.ACTIVE, due_at__isnull=False, due_at__lt=now
    )
    if min_days_overdue:
        rows = rows.filter(due_at__lte=now - timedelta(days=min_days_overdue))
    rows = _apply_window(rows, "due_at", low, high)
    rows = rows.select_related("course", "course_version")
    # days_overdue falls as due_at rises, so this is the documented order without a sort key.
    return _annotated(rows).order_by("due_at", "pk")


def overdue_payload(row: Any, now: datetime | None = None) -> dict[str, Any]:
    """One §3 row; ``row`` is an annotated enrollment, not the bare model."""
    moment = now or timezone.now()
    return {
        "enrollment_id": row.pk,
        "user_ref": row.user_ref,
        "course_title": row.course.title,
        "due_at": row.due_at,
        "days_overdue": days_overdue(row.due_at, moment),
        "progress_percent": progress_percent(row),
        "last_activity_at": row.last_activity_at,
        "mandatory": row.mandatory,
    }


# --- completion -------------------------------------------------------------


def _method() -> Subquery:
    records = CompletionRecord.objects.filter(enrollment=OuterRef("pk")).order_by().values("method")
    return Subquery(records[:1], output_field=CharField(max_length=16))


def completion(
    access: Access,
    *,
    status: str = "all",
    course_id: Any = None,
    department_ref: str | None = None,
    start: Any = None,
    end: Any = None,
) -> QuerySet[Enrollment]:
    """``GET /manage/reports/completion/`` — §4, window on ``completed_at`` (§1)."""
    if status not in COMPLETION_STATUSES:
        raise DomainValidationError(
            "status must be one of the documented values",
            fields={"status": list(COMPLETION_STATUSES)},
        )
    low, high = window(start, end)
    require_reports(access)
    organization_id = access.principal.organization_id
    _require_department(access, department_ref)
    _require_course(access, organization_id, course_id)
    rows: QuerySet[Enrollment] = Enrollment.objects.for_org(organization_id).filter(
        _scope_q(access)
    )
    if course_id is not None:
        rows = rows.filter(course_id=course_id)
    if department_ref is not None:
        rows = rows.filter(course__owner_department_ref=department_ref)
    now = timezone.now()
    if status == "completed":
        rows = rows.filter(status=Enrollment.Status.COMPLETED)
    elif status == "active":
        rows = rows.filter(status=Enrollment.Status.ACTIVE)
    elif status == "overdue":
        rows = rows.filter(status=Enrollment.Status.ACTIVE, due_at__isnull=False, due_at__lt=now)
    rows = _apply_window(rows, "completed_at", low, high)
    annotated: Any = rows.select_related("course", "course_version").annotate(method=_method())
    return _annotated(annotated).order_by("course__title", "user_ref", "pk")


def completion_payload(row: Any, now: datetime | None = None) -> dict[str, Any]:
    """One §4 row; ``row`` is an annotated enrollment, not the bare model."""
    moment = now or timezone.now()
    return {
        "enrollment_id": row.pk,
        "user_ref": row.user_ref,
        "course_title": row.course.title,
        "version_number": row.course_version.version_number,
        "status": row.status,
        "progress_percent": progress_percent(row),
        "completed_at": row.completed_at,
        "method": row.method,
        "due_at": row.due_at,
        "days_overdue": days_overdue(row.due_at, moment),
    }
