"""T-020 acceptance: heartbeat, anti-skip and the completion flow (``docs/domain-model.md`` §7).

The matrix of §9 is written against the service first — the clock, the ceiling and the merged
ranges are the server's, so a test moves ``last_heartbeat_at`` instead of waiting — and the same
behaviour is then checked through the API over a signed Hub identity in ``grants_only`` mode.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest
from django.test import Client, override_settings
from django.utils import timezone
from factories import (
    make_course,
    make_enrollment,
    make_grant,
    make_lesson,
    make_media,
    make_progress,
    make_section,
    make_version,
)

from academy import progress
from academy.assignments import gating
from academy.authorization.core import Access, Capability, Principal, Scope
from academy.events.handlers import subscribe, unsubscribe
from academy.events.types import DomainEvent
from academy.exceptions import (
    AcknowledgmentNotRequired,
    DomainValidationError,
    EnrollmentIncomplete,
    Forbidden,
    LessonLocked,
    LessonNotEligible,
    NotFound,
    ProgressSkipRejected,
    StateConflict,
)
from academy.models import (
    AuditEvent,
    CompletionRecord,
    Course,
    CourseVersion,
    Enrollment,
    Lesson,
    LessonProgress,
)

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
SECRET = "test-identity-secret-that-is-at-least-32-bytes"
KID = "test-kid-1"
HUB = dict(
    ACADEMY_ACCESS_MODE="hub",
    ACADEMY_HUB_IDENTITY_KEYS={KID: SECRET},
    ACADEMY_AUTHORIZATION_MODE="grants_only",
)


# --- fixtures and helpers ---------------------------------------------------


@pytest.fixture(autouse=True)
def _frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin ``timezone.now`` for this module.

    The anti-skip ceiling is derived from the wall clock, so a loaded machine that spends a
    tenth of a second between ``seeded()`` and ``beat()`` moves ``skippable_seconds`` by that
    much and turns every "exactly 22 s" assertion into a coin flip. Frozen, the numbers are the
    ones the document states.
    """
    moment = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: moment)


def learner(user_ref: str = "u-1") -> Access:
    principal = Principal(
        user_ref=user_ref, organization_id=ORG, department_refs=frozenset({"dep-1"})
    )
    return Access(principal=principal, capabilities={Capability.LEARN: Scope.everything()})


def administrator(*capabilities: Capability) -> Access:
    principal = Principal(
        user_ref="u-admin", organization_id=ORG, department_refs=frozenset({"dep-1"})
    )
    scope = Scope.everything()
    return Access(
        principal=principal,
        capabilities={capability: scope for capability in capabilities or (Capability.ADMIN,)},
    )


def video_lesson(
    organization_id: UUID,
    section: Any,
    position: int,
    *,
    duration: float | None = 100,
    required: bool = True,
) -> Lesson:
    asset = None
    if duration is not None:
        asset = make_media(
            organization_id,
            kind="video",
            status="ready",
            storage_key=f"org/videos/{position}.mp4",
            duration_seconds=duration,
        )
    return make_lesson(
        organization_id,
        section=section,
        title=f"Lesson {position}",
        position=position,
        content_type="video",
        media_asset=asset,
        required=required,
    )


def course_with(
    *,
    lessons: int = 2,
    durations: list[float | None] | None = None,
    acknowledgment_required: bool = False,
    optional_lesson: bool = False,
) -> tuple[Course, CourseVersion, list[Lesson]]:
    """A published course; content is built in the draft because publish freezes it."""
    course = make_course(ORG)
    version = make_version(ORG, course=course)
    version.acknowledgment_required = acknowledgment_required
    version.save(update_fields=["acknowledgment_required", "updated_at"])
    section = make_section(ORG, version=version)
    built: list[Lesson] = []
    for position in range(1, lessons + 1):
        duration = 100.0 if durations is None else durations[position - 1]
        built.append(video_lesson(ORG, section, position, duration=duration))
    if optional_lesson:
        built.append(video_lesson(ORG, section, lessons + 1, required=False))
    version.status = CourseVersion.Status.PUBLISHED
    version.published_at = timezone.now()
    version.published_by_ref = "u-author"
    version.save(update_fields=["status", "published_at", "published_by_ref", "updated_at"])
    return course, version, built


def enrolled(version: CourseVersion, lessons: list[Lesson], *, user_ref: str = "u-1") -> Enrollment:
    return make_enrollment(ORG, course=version.course, version=version, user_ref=user_ref)


def seeded(
    enrollment: Enrollment,
    lesson: Lesson,
    *,
    position: float = 0.0,
    watched: list[list[float]] | None = None,
    frontier: float = 0.0,
    seconds_since_heartbeat: float | None = 10.0,
    completed_at: Any = None,
) -> LessonProgress:
    watched = watched or []
    return make_progress(
        ORG,
        enrollment=enrollment,
        lesson=lesson,
        watched_ranges=watched,
        watched_seconds=sum(end - start for start, end in watched),
        position_seconds=position,
        frontier_seconds=frontier,
        last_heartbeat_at=(
            None
            if seconds_since_heartbeat is None
            else timezone.now() - timedelta(seconds=seconds_since_heartbeat)
        ),
        completed_at=completed_at,
    )


def beat(
    enrollment: Enrollment,
    lesson: Lesson,
    *,
    start: float,
    end: float,
    rate: float = 1.0,
    user_ref: str = "u-1",
) -> dict[str, float]:
    return progress.record_heartbeat(
        learner(user_ref),
        enrollment.pk,
        lesson.pk,
        from_seconds=start,
        to_seconds=end,
        playback_rate=rate,
    )


# --- heartbeat and anti-skip (§7.2–§7.4) -----------------------------------


def test_a_forward_skip_is_rejected_on_the_first_heartbeat(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)

    with pytest.raises(ProgressSkipRejected) as raised:
        beat(enrollment, lessons[0], start=0, end=60)

    assert raised.value.code == "progress_skip_rejected"
    assert raised.value.fields["allowed_seconds"] == pytest.approx(progress.SKIP_TOLERANCE_SECONDS)
    row = LessonProgress.objects.for_org(ORG).get(enrollment=enrollment, lesson=lessons[0])
    assert row.skip_attempts == 1
    assert float(row.position_seconds) == 0.0
    assert float(row.watched_seconds) == 0.0


def test_the_first_heartbeat_credits_nothing_and_only_moves_the_position(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)

    state = beat(enrollment, lessons[0], start=0, end=progress.SKIP_TOLERANCE_SECONDS)

    # §7.3 step 4: the tolerance widens the ceiling, it does not hand out coverage — the first
    # heartbeat has no elapsed window to credit, so the learner has to earn the rest.
    assert state["watched_seconds"] == 0.0
    assert state["position_seconds"] == pytest.approx(progress.SKIP_TOLERANCE_SECONDS)
    assert state["skippable_seconds"] == pytest.approx(progress.SKIP_TOLERANCE_SECONDS)


def test_a_paused_gap_is_not_credited_beyond_the_heartbeat_window(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    seeded(
        enrollment,
        lessons[0],
        position=50,
        watched=[[0, 50]],
        frontier=50,
        seconds_since_heartbeat=600,
    )

    with pytest.raises(ProgressSkipRejected) as raised:
        beat(enrollment, lessons[0], start=50, end=200)
    # A ten-minute pause is worth one window of 60 s, not ten minutes of coverage.
    assert raised.value.fields["allowed_seconds"] == pytest.approx(50 + 60 + 2)

    state = beat(enrollment, lessons[0], start=50, end=100)
    assert state["watched_seconds"] == pytest.approx(100.0)


def test_credit_is_clamped_to_the_maximum_playback_rate(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    seeded(enrollment, lessons[0], seconds_since_heartbeat=10)

    state = beat(enrollment, lessons[0], start=0, end=20, rate=3.0)

    assert state["watched_seconds"] == pytest.approx(20.0)
    assert state["skippable_seconds"] == pytest.approx(22.0)


def test_faster_than_the_rate_allows_is_a_skip(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    seeded(enrollment, lessons[0], seconds_since_heartbeat=10)

    with pytest.raises(ProgressSkipRejected):
        beat(enrollment, lessons[0], start=0, end=25, rate=3.0)


def test_a_rate_below_the_minimum_credits_nothing(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    seeded(enrollment, lessons[0], seconds_since_heartbeat=10)

    state = beat(enrollment, lessons[0], start=0, end=3, rate=0.4)

    assert state["watched_seconds"] == 0.0
    assert state["position_seconds"] == pytest.approx(3.0)


def test_a_rewind_credits_nothing_and_keeps_the_high_water_mark(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    seeded(
        enrollment,
        lessons[0],
        position=50,
        watched=[[0, 50]],
        frontier=50,
        seconds_since_heartbeat=10,
    )

    state = beat(enrollment, lessons[0], start=20, end=30)

    assert state["watched_seconds"] == pytest.approx(50.0)
    assert state["position_seconds"] == pytest.approx(50.0)
    assert state["frontier_seconds"] == pytest.approx(50.0)


def test_a_duplicate_heartbeat_is_a_no_op(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    seeded(
        enrollment,
        lessons[0],
        position=30,
        watched=[[0, 30]],
        frontier=30,
        seconds_since_heartbeat=0,
    )

    first = beat(enrollment, lessons[0], start=15, end=30)
    second = beat(enrollment, lessons[0], start=15, end=30)

    assert first == second
    assert first["watched_seconds"] == pytest.approx(30.0)
    assert LessonProgress.objects.for_org(ORG).get(enrollment=enrollment).skip_attempts == 0


def test_a_gap_after_the_frontier_is_covered_but_not_reached(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    seeded(enrollment, lessons[0], seconds_since_heartbeat=10)

    state = beat(enrollment, lessons[0], start=5, end=10)

    assert state["watched_seconds"] == pytest.approx(5.0)
    assert state["frontier_seconds"] == 0.0
    assert state["coverage_percent"] == pytest.approx(5.0)


def test_heartbeats_are_not_audited(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)

    beat(enrollment, lessons[0], start=0, end=2)

    assert AuditEvent.objects.for_org(ORG).count() == 0


def test_a_locked_lesson_records_no_progress(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)

    with pytest.raises(LessonLocked):
        beat(enrollment, lessons[1], start=0, end=2)
    assert not LessonProgress.objects.for_org(ORG).filter(enrollment=enrollment).exists()


def test_progress_on_someone_elses_enrollment_is_not_found(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons, user_ref="u-1")

    with pytest.raises(NotFound):
        beat(enrollment, lessons[0], start=0, end=2, user_ref="u-2")


# --- lesson completion (§7.6) ----------------------------------------------


def test_a_lesson_below_its_threshold_is_not_eligible(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    seeded(
        enrollment,
        lessons[0],
        position=50,
        watched=[[0, 50]],
        frontier=50,
        seconds_since_heartbeat=0,
    )

    with pytest.raises(LessonNotEligible) as raised:
        progress.complete_lesson(learner(), enrollment.pk, lessons[0].pk)

    assert raised.value.code == "lesson_not_eligible"
    assert raised.value.fields == {"coverage_percent": 50.0, "required_percent": 90}
    assert (
        not LessonProgress.objects.for_org(ORG)
        .filter(enrollment=enrollment, completed_at__isnull=False)
        .exists()
    )


def test_a_lesson_at_its_threshold_completes_once(
    db: Any, django_capture_on_commit_callbacks: Any
) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    seeded(
        enrollment,
        lessons[0],
        position=95,
        watched=[[0, 95]],
        frontier=95,
        seconds_since_heartbeat=0,
    )
    seen: list[DomainEvent] = []
    subscribe("lesson.completed", seen.append)
    try:
        with django_capture_on_commit_callbacks(execute=True):
            first = progress.complete_lesson(learner(), enrollment.pk, lessons[0].pk)
            second = progress.complete_lesson(learner(), enrollment.pk, lessons[0].pk)
    finally:
        unsubscribe("lesson.completed", seen.append)

    assert first["completed_at"] == second["completed_at"]
    assert first["coverage_percent"] == pytest.approx(95.0)
    assert len(seen) == 1
    assert seen[0].payload["lesson_id"] == str(lessons[0].pk)


def test_a_text_lesson_completes_on_confirmation(db: Any) -> None:
    course = make_course(ORG)
    version = make_version(ORG, course=course)
    section = make_section(ORG, version=version)
    lesson = make_lesson(ORG, section=section, title="Read this", position=1)
    version.status = CourseVersion.Status.PUBLISHED
    version.published_at = timezone.now()
    version.published_by_ref = "u-author"
    version.save(update_fields=["status", "published_at", "published_by_ref", "updated_at"])
    enrollment = enrolled(version, [lesson])

    payload = progress.complete_lesson(learner(), enrollment.pk, lesson.pk)

    assert payload["completed_at"] is not None
    assert payload["coverage_percent"] == 0.0


# --- acknowledgment and enrollment completion (§7.7) -----------------------


def test_an_acknowledgment_on_a_version_that_does_not_require_one_is_refused(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)

    with pytest.raises(AcknowledgmentNotRequired):
        progress.acknowledge(learner(), enrollment.pk)


def test_the_acknowledgment_is_idempotent(db: Any) -> None:
    _, version, lessons = course_with(acknowledgment_required=True)
    enrollment = enrolled(version, lessons)

    first = progress.acknowledge(learner(), enrollment.pk)
    second = progress.acknowledge(learner(), enrollment.pk)

    assert first["acknowledged"] is True
    assert first["acknowledged_at"] == second["acknowledged_at"]


def test_completion_needs_every_required_lesson(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    make_progress(ORG, enrollment=enrollment, lesson=lessons[0], completed_at=timezone.now())

    with pytest.raises(EnrollmentIncomplete) as raised:
        progress.complete_enrollment(learner(), enrollment.pk)

    assert raised.value.code == "enrollment_incomplete"
    assert raised.value.fields["blocking_lesson_ids"] == [str(lessons[1].pk)]
    assert not CompletionRecord.objects.for_org(ORG).filter(enrollment=enrollment).exists()


def test_completion_needs_the_acknowledgment_the_version_asks_for(db: Any) -> None:
    _, version, lessons = course_with(acknowledgment_required=True)
    enrollment = enrolled(version, lessons)
    for lesson in lessons:
        make_progress(ORG, enrollment=enrollment, lesson=lesson, completed_at=timezone.now())

    with pytest.raises(EnrollmentIncomplete) as raised:
        progress.complete_enrollment(learner(), enrollment.pk)
    assert raised.value.fields["acknowledgment_required"] is True

    progress.acknowledge(learner(), enrollment.pk)
    payload = progress.complete_enrollment(learner(), enrollment.pk)
    assert payload["status"] == Enrollment.Status.COMPLETED


def test_enrollment_completion_is_idempotent(
    db: Any, django_capture_on_commit_callbacks: Any
) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    for lesson in lessons:
        make_progress(ORG, enrollment=enrollment, lesson=lesson, completed_at=timezone.now())
    seen: list[DomainEvent] = []
    subscribe("enrollment.completed", seen.append)
    try:
        with django_capture_on_commit_callbacks(execute=True):
            first = progress.complete_enrollment(learner(), enrollment.pk)
            second = progress.complete_enrollment(learner(), enrollment.pk)
    finally:
        unsubscribe("enrollment.completed", seen.append)

    assert first["completed_at"] == second["completed_at"]
    assert CompletionRecord.objects.for_org(ORG).filter(enrollment=enrollment).count() == 1
    assert len(seen) == 1
    assert seen[0].payload["method"] == CompletionRecord.Method.LESSONS


# --- admin override (§5, ARCHITECTURE §7) ----------------------------------


def test_an_admin_override_completes_and_is_audited_once(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    admin = administrator(Capability.ADMIN)

    first = progress.override_complete_enrollment(
        admin, enrollment.pk, reason="completed in a classroom session"
    )
    second = progress.override_complete_enrollment(admin, enrollment.pk, reason="repeat")

    assert first["method"] == CompletionRecord.Method.ADMIN_OVERRIDE
    assert first["completed_at"] == second["completed_at"]
    enrollment.refresh_from_db()
    assert enrollment.status == Enrollment.Status.COMPLETED
    record = CompletionRecord.objects.for_org(ORG).get(enrollment=enrollment)
    assert record.method == CompletionRecord.Method.ADMIN_OVERRIDE
    assert record.actor_ref == "u-admin"
    rows = AuditEvent.objects.for_org(ORG).filter(action="enrollment.completed_override")
    assert rows.count() == 1
    assert set(rows[0].metadata) == {"course_id", "course_version_id", "method"}


def test_the_override_needs_the_admin_capability(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)

    with pytest.raises(Forbidden):
        progress.override_complete_enrollment(learner(), enrollment.pk, reason="not allowed")


def test_the_override_needs_a_reason(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)

    with pytest.raises(DomainValidationError):
        progress.override_complete_enrollment(
            administrator(Capability.ADMIN), enrollment.pk, reason="   "
        )


def test_a_cancelled_enrollment_cannot_be_completed(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    enrollment.status = Enrollment.Status.CANCELLED
    enrollment.cancelled_at = timezone.now()
    enrollment.cancel_reason = Enrollment.CancelReason.UNASSIGNED
    enrollment.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])

    with pytest.raises(StateConflict):
        progress.override_complete_enrollment(
            administrator(Capability.ADMIN), enrollment.pk, reason="override"
        )


# --- API --------------------------------------------------------------------


def grant(user_ref: str, capability: str, scope_type: str = "department") -> None:
    make_grant(
        ORG,
        user_ref=user_ref,
        capability=capability,
        scope_type=scope_type,
        scope_ref="" if scope_type == "organization" else "dep-1",
    )


def call(
    client: Client,
    method: str,
    path: str,
    *,
    user_ref: str = "u-1",
    role: str = "employee",
    body: dict[str, Any] | None = None,
) -> Any:
    from host_hub.fake import sign_identity

    token = sign_identity(
        method=method,
        target=path,
        organization_id=ORG,
        user_ref=user_ref,
        role=role,
        kid=KID,
        secret=SECRET,
    )
    payload = json.dumps(body) if body is not None else None
    with override_settings(**HUB):
        return client.generic(
            method,
            path,
            data=payload,
            content_type="application/json",
            HTTP_X_MASHEED_IDENTITY=token,
        )


def test_the_heartbeat_endpoint_returns_the_server_state(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    seeded(enrollment, lessons[0], seconds_since_heartbeat=10)
    grant("u-1", "learn")
    path = f"/api/v1/academy/enrollments/{enrollment.pk}/lessons/{lessons[0].pk}/progress/"

    response = call(Client(), "POST", path, body={"from_seconds": 0, "to_seconds": 10})

    assert response.status_code == 200, response.content
    assert response.json()["watched_seconds"] == pytest.approx(10.0)
    assert response["Cache-Control"] == "private, no-store"


def test_the_heartbeat_endpoint_rejects_a_skip(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    grant("u-1", "learn")
    path = f"/api/v1/academy/enrollments/{enrollment.pk}/lessons/{lessons[0].pk}/progress/"

    response = call(Client(), "POST", path, body={"from_seconds": 0, "to_seconds": 90})

    assert response.status_code == 400, response.content
    body = response.json()
    assert body["code"] == "progress_skip_rejected"
    assert body["fields"]["allowed_seconds"] == pytest.approx(progress.SKIP_TOLERANCE_SECONDS)


def test_the_heartbeat_endpoint_refuses_a_locked_lesson(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    grant("u-1", "learn")
    path = f"/api/v1/academy/enrollments/{enrollment.pk}/lessons/{lessons[1].pk}/progress/"

    response = call(Client(), "POST", path, body={"from_seconds": 0, "to_seconds": 2})

    assert response.status_code == 403, response.content
    assert response.json()["code"] == "lesson_locked"


def test_the_lesson_completion_endpoint_reports_the_threshold(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    seeded(enrollment, lessons[0], seconds_since_heartbeat=0)
    grant("u-1", "learn")
    path = f"/api/v1/academy/enrollments/{enrollment.pk}/lessons/{lessons[0].pk}/complete/"

    response = call(Client(), "POST", path)

    assert response.status_code == 409, response.content
    body = response.json()
    assert body["code"] == "lesson_not_eligible"
    assert body["fields"]["required_percent"] == 90


def test_the_enrollment_completion_endpoint_answers_200_twice(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    for lesson in lessons:
        make_progress(ORG, enrollment=enrollment, lesson=lesson, completed_at=timezone.now())
    grant("u-1", "learn")
    path = f"/api/v1/academy/enrollments/{enrollment.pk}/complete/"

    first = call(Client(), "POST", path)
    second = call(Client(), "POST", path)

    assert first.status_code == 200, first.content
    assert second.status_code == 200
    assert first.json()["status"] == Enrollment.Status.COMPLETED
    assert first.json()["completed_at"] == second.json()["completed_at"]


def test_the_admin_override_endpoint_needs_admin(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    grant("u-1", "assign")
    path = f"/api/v1/academy/manage/enrollments/{enrollment.pk}/complete/"

    denied = call(Client(), "POST", path, body={"reason": "override"}, role="department_manager")
    assert denied.status_code == 403, denied.content

    grant("u-admin", "admin", scope_type="organization")
    allowed = call(
        Client(),
        "POST",
        path,
        user_ref="u-admin",
        role="platform_admin",
        body={"reason": "completed in a classroom session"},
    )
    assert allowed.status_code == 200, allowed.content
    assert allowed.json()["method"] == CompletionRecord.Method.ADMIN_OVERRIDE


def test_an_anonymous_heartbeat_is_401(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    path = f"/api/v1/academy/enrollments/{enrollment.pk}/lessons/{lessons[0].pk}/progress/"

    with override_settings(**HUB):
        response = Client().post(path, data=json.dumps({}), content_type="application/json")

    assert response.status_code == 401


def test_the_outline_and_the_heartbeat_agree_on_the_lock(db: Any) -> None:
    _, version, lessons = course_with()
    enrollment = enrolled(version, lessons)
    make_progress(ORG, enrollment=enrollment, lesson=lessons[0], completed_at=timezone.now())

    states = gating.state_for(
        gating.ordered_lessons(enrollment), gating.completed_lesson_ids(enrollment)
    )
    assert states[lessons[1].pk] == (False, False)
    assert (
        gating.progress_percent(
            gating.ordered_lessons(enrollment), gating.completed_lesson_ids(enrollment)
        )
        == 50
    )
