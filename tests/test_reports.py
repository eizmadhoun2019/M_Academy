"""T-022 acceptance: scoped reports and the formula-safe CSV export.

The numbers come from ``docs/reports.md``; these tests pin one column at a time so a change to
an annotation fails here instead of surprising a manager in a spreadsheet. The HTTP half runs
over signed Hub identities in ``grants_only`` — the production mode (D-027).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import Client, override_settings
from django.utils import timezone
from factories import (
    make_completion,
    make_course,
    make_enrollment,
    make_grant,
    make_lesson,
    make_progress,
    make_section,
    make_version,
)

from academy.audit import service as audit
from academy.authorization.core import Access, Capability, Principal, Scope
from academy.exceptions import Forbidden, InvalidRange
from academy.models import AuditEvent, Course, Enrollment, Lesson
from academy.reports import csv_export, selectors
from host_hub.fake import DEFAULT_KID, sign_identity
from host_stub.organization import StubDirectory

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
SECRET = "test-identity-secret-that-is-at-least-32-bytes"
KID = DEFAULT_KID
SUMMARY = "/api/v1/academy/manage/reports/summary/"
OVERDUE = "/api/v1/academy/manage/reports/overdue/"
COMPLETION = "/api/v1/academy/manage/reports/completion/"
EXPORT = "/api/v1/academy/manage/reports/export.csv"

HUB = dict(
    ACADEMY_ACCESS_MODE="hub",
    ACADEMY_HUB_IDENTITY_KEYS={KID: SECRET},
    ACADEMY_HUB_WEBHOOK_KEYS={KID: SECRET},
    ACADEMY_AUTHORIZATION_MODE="grants_only",
)


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    cache.clear()


def access(
    *,
    departments: tuple[str, ...] = ("dep-1",),
    everything: bool = False,
    capabilities: tuple[Capability, ...] = (Capability.VIEW_REPORTS,),
    user_ref: str = "u-manager",
) -> Access:
    principal = Principal(
        user_ref=user_ref, organization_id=ORG, department_refs=frozenset(departments)
    )
    scope = Scope.everything() if everything else Scope.for_departments(list(departments))
    return Access(
        principal=principal, capabilities={capability: scope for capability in capabilities}
    )


def course_with_lessons(*, lessons: int = 2, owner: str | None = "dep-1") -> tuple[Course, Any]:
    course = make_course(ORG, title="Safety", owner_department_ref=owner)
    version = make_version(ORG, course=course)
    section = make_section(ORG, version=version)
    for position in range(1, lessons + 1):
        make_lesson(ORG, section=section, position=position, title=f"Lesson {position}")
    return course, version


def completed_enrollment(
    course: Course,
    version: Any,
    *,
    user_ref: str = "u-1",
    days: int = 10,
    days_ago: int = 20,
) -> Enrollment:
    completed_at = timezone.now() - timedelta(days=days_ago)
    started = completed_at - timedelta(days=days)
    return make_enrollment(
        ORG,
        course=course,
        version=version,
        user_ref=user_ref,
        status=Enrollment.Status.COMPLETED,
        completed_at=completed_at,
        created_at=started,
    )


# --- summary ----------------------------------------------------------------


def test_summary_reports_every_documented_column(db: Any) -> None:
    course, version = course_with_lessons(lessons=2)
    completed_enrollment(course, version, user_ref="u-done", days=10)

    in_progress = make_enrollment(ORG, course=course, version=version, user_ref="u-mid")
    make_progress(
        ORG,
        enrollment=in_progress,
        lesson=Lesson.objects.filter(section__version=version).order_by("position").first(),
        watched_seconds=5,
        completed_at=timezone.now(),
    )
    make_enrollment(ORG, course=course, version=version, user_ref="u-idle")
    overdue = make_enrollment(
        ORG,
        course=course,
        version=version,
        user_ref="u-late",
        due_at=timezone.now() - timedelta(days=3),
        mandatory=False,
    )
    # Cancelled enrollments are not eligible (§1).
    make_enrollment(
        ORG,
        course=course,
        version=version,
        user_ref="u-gone",
        status=Enrollment.Status.CANCELLED,
        cancelled_at=timezone.now(),
        mandatory=False,
    )

    payload = selectors.summary(access())
    assert len(payload["rows"]) == 1
    row = payload["rows"][0]
    assert row["group_key"] == str(course.pk) and row["group_label"] == "Safety"
    assert row["eligible"] == 4
    assert row["completed"] == 1
    assert row["in_progress"] == 1
    assert row["not_started"] == 2
    assert row["overdue"] == 1
    assert str(row["completion_percent"]) == "25.0"
    assert str(row["average_completion_days"]) == "10.0"
    assert row["mandatory_eligible"] == 3
    assert overdue.pk  # kept for the FK order above

    totals = payload["totals"]
    assert totals["eligible"] == 4 and totals["completed"] == 1
    assert totals["not_started"] == 2 and str(totals["completion_percent"]) == "25.0"


def test_summary_totals_sum_counts_instead_of_averaging_percentages(db: Any) -> None:
    small, small_version = course_with_lessons(lessons=1)
    big, big_version = course_with_lessons(lessons=1)
    completed_enrollment(small, small_version, user_ref="u-1")
    for ref in ("u-2", "u-3", "u-4"):
        make_enrollment(ORG, course=small, version=small_version, user_ref=ref)
    completed_enrollment(big, big_version, user_ref="u-9")

    payload = selectors.summary(access(everything=True))
    assert [row["group_label"] for row in payload["rows"]] == ["Safety", "Safety"]
    assert {str(row["completion_percent"]) for row in payload["rows"]} == {"25.0", "100.0"}
    # 2 of 5, not the mean of 25 % and 100 %.
    assert str(payload["totals"]["completion_percent"]) == "40.0"


def test_summary_has_no_average_until_something_completes(db: Any) -> None:
    course, version = course_with_lessons()
    make_enrollment(ORG, course=course, version=version)

    row = selectors.summary(access())["rows"][0]
    assert row["average_completion_days"] is None


def test_average_days_only_counts_rows_inside_the_window(db: Any) -> None:
    course, version = course_with_lessons()
    completed_enrollment(course, version, user_ref="u-old", days=100)
    recent = timezone.now() - timedelta(days=2)
    enrollment = make_enrollment(
        ORG,
        course=course,
        version=version,
        user_ref="u-new",
        status=Enrollment.Status.COMPLETED,
        created_at=recent,
        completed_at=recent + timedelta(days=2),
    )
    payload = selectors.summary(
        access(), start=(timezone.now() - timedelta(days=10)).date().isoformat()
    )
    assert [row["eligible"] for row in payload["rows"]] == [1]
    assert str(payload["rows"][0]["average_completion_days"]) == "2.0"
    assert enrollment.pk


def test_summary_runs_the_same_number_of_queries_for_any_row_count(
    db: Any, django_assert_num_queries: Any
) -> None:
    for index in range(5):
        course, version = course_with_lessons(lessons=1)
        make_enrollment(ORG, course=course, version=version, user_ref=f"u-{index}")
    with django_assert_num_queries(3):
        selectors.summary(access())


def org_name() -> str:
    return str(settings.ACADEMY_ORGANIZATION_NAME)


def test_department_grouping_labels_refs_and_the_general_courses(
    db: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = StubDirectory()
    stub.add_department(ORG, "dep-1", "Training")
    monkeypatch.setattr(selectors, "directory", lambda: stub)
    owned, owned_version = course_with_lessons(owner="dep-1")
    general, general_version = course_with_lessons(owner=None)
    make_enrollment(ORG, course=owned, version=owned_version)
    make_enrollment(ORG, course=general, version=general_version)

    rows = selectors.summary(access(), group_by="department_ref")["rows"]
    assert [row["group_label"] for row in rows] == ["Training", org_name()]
    assert [row["group_key"] for row in rows] == ["dep-1", ""]
    assert [row["eligible"] for row in rows] == [1, 1]


def test_department_labels_fall_back_to_the_key_when_the_hub_is_down(
    db: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = StubDirectory()

    def broken(organization_id: Any) -> Any:
        raise RuntimeError("hub unavailable")

    monkeypatch.setattr(stub, "departments", broken)
    monkeypatch.setattr(selectors, "directory", lambda: stub)
    course, version = course_with_lessons(owner="dep-9")
    make_enrollment(ORG, course=course, version=version)

    row = selectors.summary(access(everything=True), group_by="department_ref")["rows"][0]
    assert row["group_label"] == "dep-9"


# --- scope ------------------------------------------------------------------


def test_a_department_scope_sees_its_courses_and_the_general_ones(db: Any) -> None:
    mine, mine_version = course_with_lessons(owner="dep-1")
    general, general_version = course_with_lessons(owner=None)
    other, other_version = course_with_lessons(owner="dep-2")
    for course, version in (
        (mine, mine_version),
        (general, general_version),
        (other, other_version),
    ):
        make_enrollment(ORG, course=course, version=version)

    keys = {row["group_key"] for row in selectors.summary(access())["rows"]}
    assert keys == {str(mine.pk), str(general.pk)}


def test_a_cross_department_filter_is_forbidden_not_empty(db: Any) -> None:
    course, version = course_with_lessons(owner="dep-2")
    make_enrollment(ORG, course=course, version=version)
    with pytest.raises(Forbidden):
        selectors.summary(access(), department_ref="dep-2")
    with pytest.raises(Forbidden):
        selectors.completion(access(), course_id=course.pk)


def test_reports_need_the_capability(db: Any) -> None:
    with pytest.raises(Forbidden):
        selectors.summary(access(capabilities=(Capability.ASSIGN,)))


def test_an_organization_scope_reads_every_department(db: Any) -> None:
    for owner in ("dep-1", "dep-2"):
        course, version = course_with_lessons(owner=owner)
        make_enrollment(ORG, course=course, version=version)
    payload = selectors.summary(access(everything=True), department_ref="dep-2")
    assert [row["eligible"] for row in payload["rows"]] == [1]


# --- overdue ----------------------------------------------------------------


def test_overdue_rows_are_active_past_due_and_sorted_by_lateness(db: Any) -> None:
    course, version = course_with_lessons(lessons=4)
    lesson = Lesson.objects.filter(section__version=version).order_by("position").first()
    late = make_enrollment(
        ORG,
        course=course,
        version=version,
        user_ref="u-late",
        due_at=timezone.now() - timedelta(days=10, hours=2),
    )
    later = make_enrollment(
        ORG,
        course=course,
        version=version,
        user_ref="u-later",
        due_at=timezone.now() - timedelta(days=2),
    )
    make_enrollment(
        ORG,
        course=course,
        version=version,
        user_ref="u-future",
        due_at=timezone.now() + timedelta(hours=1),
    )
    make_enrollment(ORG, course=course, version=version, user_ref="u-nodue")
    completed_enrollment(course, version, user_ref="u-done")
    make_progress(
        ORG,
        enrollment=late,
        lesson=lesson,
        completed_at=timezone.now(),
        last_heartbeat_at=timezone.now(),
    )
    rows = [selectors.overdue_payload(row) for row in selectors.overdue(access())]

    assert [row["user_ref"] for row in rows] == ["u-late", "u-later"]
    assert [row["days_overdue"] for row in rows] == [10, 2]
    assert str(rows[0]["progress_percent"]) == "25.0"
    assert rows[0]["last_activity_at"] is not None
    assert rows[1]["last_activity_at"] is None
    assert later.pk


def test_overdue_min_days_filters_by_floor(db: Any) -> None:
    course, version = course_with_lessons(lessons=1)
    make_enrollment(
        ORG,
        course=course,
        version=version,
        user_ref="u-a",
        due_at=timezone.now() - timedelta(days=5),
    )
    make_enrollment(
        ORG,
        course=course,
        version=version,
        user_ref="u-b",
        due_at=timezone.now() - timedelta(days=1),
    )
    rows = [
        selectors.overdue_payload(row)["user_ref"]
        for row in selectors.overdue(access(), min_days_overdue=3)
    ]
    assert rows == ["u-a"]


def test_progress_percent_is_zero_when_the_version_has_no_lessons(db: Any) -> None:
    course = make_course(ORG, owner_department_ref="dep-1")
    version = make_version(ORG, course=course)
    make_enrollment(
        ORG,
        course=course,
        version=version,
        user_ref="u-a",
        due_at=timezone.now() - timedelta(days=2),
    )
    only = selectors.overdue(access()).first()
    assert only is not None
    row = selectors.overdue_payload(only)
    assert str(row["progress_percent"]) == "0.0"


# --- completion -------------------------------------------------------------


def test_completion_all_keeps_cancelled_rows_and_status_filters_them_out(db: Any) -> None:
    course, version = course_with_lessons(lessons=1)
    keep = make_enrollment(ORG, course=course, version=version, user_ref="u-keep")
    make_enrollment(
        ORG,
        course=course,
        version=version,
        user_ref="u-gone",
        status=Enrollment.Status.CANCELLED,
        cancelled_at=timezone.now(),
    )
    assert sorted(row.user_ref for row in selectors.completion(access())) == ["u-gone", "u-keep"]
    active = list(selectors.completion(access(), status="active"))
    assert [row.user_ref for row in active] == ["u-keep"]
    assert selectors.completion_payload(active[0])["method"] is None
    assert keep.pk


def test_completion_reports_method_and_version(db: Any) -> None:
    course, version = course_with_lessons(lessons=1)
    enrollment = completed_enrollment(course, version, user_ref="u-done")
    make_completion(ORG, enrollment=enrollment, method="admin_override")

    payload = selectors.completion_payload(selectors.completion(access(), status="completed").get())
    assert payload["version_number"] == 1
    assert payload["method"] == "admin_override"
    assert payload["status"] == Enrollment.Status.COMPLETED
    assert payload["completed_at"] == enrollment.completed_at


def test_completion_window_uses_completed_at(db: Any) -> None:
    course, version = course_with_lessons(lessons=1)
    completed_enrollment(course, version, user_ref="u-old", days=10, days_ago=400)
    recent = timezone.now() - timedelta(days=1)
    make_enrollment(
        ORG,
        course=course,
        version=version,
        user_ref="u-new",
        status=Enrollment.Status.COMPLETED,
        created_at=recent - timedelta(days=30),
        completed_at=recent,
    )
    since = (recent - timedelta(days=3)).date().isoformat()
    rows = [row.user_ref for row in selectors.completion(access(), start=since)]
    assert rows == ["u-new"]


def test_a_reversed_window_is_an_invalid_range(db: Any) -> None:
    with pytest.raises(InvalidRange):
        selectors.summary(access(), start="2026-02-01", end="2026-01-01")


# --- CSV --------------------------------------------------------------------


def test_csv_cells_starting_like_a_formula_are_neutralised() -> None:
    row = {
        "enrollment_id": "id-1",
        "user_ref": "=1+1",
        "course_title": "@SUM(A1:A9)",
        "version_number": 2,
        "status": "-2+3",
        "progress_percent": "50.0",
        "completed_at": None,
        "method": "\tcmd",
        "due_at": None,
        "days_overdue": 0,
    }
    cells = csv_export.cells(row, selectors.EXPORT_COLUMNS)
    assert cells[1] == "'=1+1"
    assert cells[2] == "'@SUM(A1:A9)"
    assert cells[4] == "'-2+3"
    assert cells[7] == "'\tcmd"
    assert cells[5] == "50.0"


def test_csv_formats_types_without_a_locale() -> None:
    moment = datetime(2026, 11, 25, 12, 30, tzinfo=UTC)
    assert csv_export.format_cell(None) == ""
    assert csv_export.format_cell(True) == "true"
    assert csv_export.format_cell(False) == "false"
    assert csv_export.format_cell(moment) == "2026-11-25T12:30:00Z"
    assert csv_export.format_cell(selectors.one_decimal(1, 3)) == "33.3"


def test_csv_stream_starts_with_a_bom_and_ends_lines_with_crlf() -> None:
    body = "".join(
        csv_export.stream(
            [{"enrollment_id": "a", "user_ref": "u-1"}],
            ("enrollment_id", "user_ref"),
        )
    )
    assert body.startswith("\ufeff")
    assert body.splitlines()[0].lstrip("\ufeff") == "enrollment_id,user_ref"
    assert "\r\n" in body and "a,u-1" in body


def test_the_export_filename_carries_the_window() -> None:
    assert csv_export.filename("2026-01-01", "2026-01-31") == (
        "academy-completion-2026-01-01-2026-01-31.csv"
    )
    assert csv_export.filename() == "academy-completion-all-all.csv"


# --- HTTP -------------------------------------------------------------------


def grant(
    user_ref: str,
    capability: str = "view_reports",
    scope_type: str = "department",
    ref: str = "dep-1",
) -> None:
    make_grant(
        ORG,
        user_ref=user_ref,
        capability=capability,
        scope_type=scope_type,
        scope_ref=None if scope_type == "organization" else ref,
    )


def call(
    client: Client,
    method: str,
    path: str,
    *,
    query: str = "",
    user_ref: str = "u-manager",
    role: str = "department_manager",
) -> Any:
    target = f"{path}?{query}" if query else path
    token = sign_identity(
        method=method,
        target=target,
        organization_id=ORG,
        user_ref=user_ref,
        role=role,
        kid=KID,
        secret=SECRET,
    )
    url = f"{path}?{query}" if query else path
    with override_settings(**HUB):
        return client.get(url, HTTP_X_MASHEED_IDENTITY=token)


def test_summary_route_answers_with_the_scope_of_the_caller(db: Any) -> None:
    grant("u-manager")
    course, version = course_with_lessons(lessons=1)
    make_enrollment(ORG, course=course, version=version)

    response = call(Client(), "GET", SUMMARY)
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["rows"][0]["group_key"] == str(course.pk)
    assert body["totals"]["eligible"] == 1
    assert response["Cache-Control"] == "private, no-store"


def test_summary_route_refuses_a_cross_department_filter(db: Any) -> None:
    grant("u-manager")
    response = call(Client(), "GET", SUMMARY, query="department_ref=dep-2")
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_summary_route_reports_an_invalid_range(db: Any) -> None:
    grant("u-manager")
    response = call(Client(), "GET", SUMMARY, query="from=2026-02-01&to=2026-01-01")
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_range"


def test_the_routes_need_view_reports(db: Any) -> None:
    grant("u-manager", capability="assign")
    assert call(Client(), "GET", SUMMARY).status_code == 403
    assert call(Client(), "GET", EXPORT).status_code == 403


def test_completion_route_pages_and_accepts_a_cursor(db: Any) -> None:
    grant("u-manager")
    course, version = course_with_lessons(lessons=1)
    for ref in ("u-1", "u-2"):
        make_enrollment(ORG, course=course, version=version, user_ref=ref)

    page = call(Client(), "GET", COMPLETION).json()
    assert len(page["results"]) == 2
    with override_settings(ACADEMY_CURSOR_PAGE_SIZE=1):
        first = call(Client(), "GET", COMPLETION, query="cursor=").json()
        assert len(first["results"]) == 1 and first["next"]


def test_export_streams_a_bom_file_and_records_the_export(db: Any) -> None:
    grant("u-manager")
    course, version = course_with_lessons(lessons=1)
    enrollment = completed_enrollment(course, version, user_ref="=calc")
    make_completion(ORG, enrollment=enrollment, method="lessons")

    response = call(Client(), "GET", EXPORT, query="from=2026-01-01&to=2026-12-31&status=completed")
    assert response.status_code == 200, response.content
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert response["Content-Disposition"] == (
        'attachment; filename="academy-completion-2026-01-01-2026-12-31.csv"'
    )
    assert response["Cache-Control"] == "private, no-store"
    body = b"".join(response.streaming_content).decode("utf-8-sig")
    header, *rows = body.split("\r\n")
    assert header.split(",") == list(selectors.EXPORT_COLUMNS)
    assert len(rows) >= 2 and rows[0].startswith(f"{enrollment.pk},")
    assert "'=calc" in body

    event = AuditEvent.objects.for_org(ORG).get(action="report.exported")
    assert event.object_type == "Report"
    payload = json.loads(json.dumps(event.metadata))
    assert payload["status"] == "completed"
    assert payload["from_date"] == "2026-01-01"
    assert "user_ref" not in payload


def test_export_refuses_an_unknown_column(db: Any) -> None:
    grant("u-manager")
    response = call(Client(), "GET", EXPORT, query="columns=user_ref,email")
    assert response.status_code == 400


def test_the_audit_helper_still_accepts_the_export_metadata(db: Any) -> None:
    """Guards the shape above: ids and names only, never a learner or a free-text label."""
    audit.record(
        organization_id=ORG,
        actor_ref="u-manager",
        action="report.exported",
        object_type="Report",
        object_id="completion",
        metadata={"department_ref": "dep-1", "status": "all"},
    )
    assert AuditEvent.objects.for_org(ORG).filter(action="report.exported").count() == 1
