"""T-019 acceptance: assignments, auto-enrolment on ``member_changed`` and gating.

The services run against a hand-built ``Access`` and a seeded directory stub, so scope rules
and expansion are exercised without HTTP; the API half runs in ``grants_only`` over signed Hub
identities, which is the production mode (D-027).
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from django.core.cache import cache
from django.test import Client, override_settings
from django.utils import timezone
from factories import (
    make_assignment,
    make_course,
    make_enrollment,
    make_grant,
    make_lesson,
    make_progress,
    make_section,
    make_version,
)

from academy.adapters.organization import DirectoryUser
from academy.assignments import expansion, gating, service
from academy.authorization.core import Access, Capability, Principal, Scope
from academy.events.handlers import subscribe, unsubscribe
from academy.events.types import DomainEvent
from academy.exceptions import (
    DomainValidationError,
    Forbidden,
    LessonLocked,
    NotFound,
    StateConflict,
    TargetEmpty,
)
from academy.media.service import playback_urls
from academy.models import AuditEvent, Course, CourseVersion, Enrollment
from host_hub.fake import DEFAULT_KID, sign_identity, sign_webhook
from host_stub.organization import StubDirectory

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
SECRET = "test-identity-secret-that-is-at-least-32-bytes"
KID = DEFAULT_KID
ASSIGNMENTS = "/api/v1/academy/manage/assignments/"
PREVIEW = f"{ASSIGNMENTS}preview/"
MY_COURSES = "/api/v1/academy/my/courses/"
MY_ENROLLMENTS = "/api/v1/academy/my/enrollments/"

HUB = dict(
    ACADEMY_ACCESS_MODE="hub",
    ACADEMY_HUB_IDENTITY_KEYS={KID: SECRET},
    ACADEMY_HUB_WEBHOOK_KEYS={KID: SECRET},
    ACADEMY_AUTHORIZATION_MODE="grants_only",
)


# --- fixtures and helpers ---------------------------------------------------


def access(
    *,
    user_ref: str = "u-manager",
    departments: tuple[str, ...] = ("dep-1",),
    capabilities: tuple[Capability, ...] = (Capability.ASSIGN,),
    everything: bool = False,
) -> Access:
    principal = Principal(
        user_ref=user_ref, organization_id=ORG, department_refs=frozenset(departments)
    )
    granted = {
        capability: (Scope.everything() if everything else Scope.for_departments(list(departments)))
        for capability in capabilities
    }
    return Access(principal=principal, capabilities=granted)


def admin(**overrides: Any) -> Access:
    return access(user_ref="u-admin", capabilities=tuple(Capability), everything=True, **overrides)


def member(user_ref: str, departments: tuple[str, ...], role: str = "employee") -> DirectoryUser:
    return DirectoryUser(
        user_ref=user_ref,
        display_name="Test member",
        email=None,
        language="ar",
        role=role,
        department_refs=departments,
        manager_ref=None,
        is_active=True,
    )


@pytest.fixture
def directory(monkeypatch: pytest.MonkeyPatch) -> StubDirectory:
    stub = StubDirectory()
    stub.add_department(ORG, "dep-1", "Training")
    stub.add_department(ORG, "dep-2", "Operations")
    stub.add_department(ORG, "dep-empty", "Empty")
    stub.add_role(ORG, "employee", "Employee")
    for ref, departments in (("u-1", ("dep-1",)), ("u-2", ("dep-1",)), ("u-3", ("dep-2",))):
        stub.add_user(ORG, member(ref, departments))
    monkeypatch.setattr(expansion, "directory", lambda: stub)
    return stub


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    cache.clear()


def published_course(
    organization_id: UUID = ORG,
    *,
    lessons: int = 1,
    optional_lesson: bool = False,
    status: str = CourseVersion.Status.PUBLISHED,
) -> tuple[Course, CourseVersion]:
    course = make_course(organization_id)
    version = make_version(organization_id, course=course)
    section = make_section(organization_id, version=version)
    for position in range(1, lessons + 1):
        make_lesson(organization_id, section=section, title=f"Lesson {position}", position=position)
    if optional_lesson:
        make_lesson(
            organization_id,
            section=section,
            title="Optional",
            position=lessons + 1,
            required=False,
        )
    # Content is built while the version is a draft; the freeze trigger rejects inserts after
    # a publish, exactly as the publish service does it (docs/domain-model.md §5).
    if status == CourseVersion.Status.PUBLISHED:
        version.status = status
        version.published_at = timezone.now()
        version.published_by_ref = "u-author"
        version.save(update_fields=["status", "published_at", "published_by_ref", "updated_at"])
    return course, version


def lesson_rows(version: CourseVersion) -> list[Any]:
    return gating.ordered_lessons(make_enrollment(ORG, course=version.course, version=version))


# --- expansion and creation -------------------------------------------------


def test_a_department_assignment_enrolls_its_members(db: Any, directory: StubDirectory) -> None:
    course, version = published_course()
    assignment = service.create_assignment(
        access(), course=course, target_type="department", target_ref="dep-1", mandatory=True
    )
    rows = Enrollment.objects.for_org(ORG).filter(assignment=assignment).order_by("user_ref")
    assert [row.user_ref for row in rows] == ["u-1", "u-2"]
    assert {row.course_version_id for row in rows} == {version.pk}
    assert {row.status for row in rows} == {Enrollment.Status.ACTIVE}
    assert AuditEvent.objects.for_org(ORG).filter(action="assignment.created").count() == 1


def test_the_preview_counts_the_same_members_the_write_enrolls(
    db: Any, directory: StubDirectory
) -> None:
    preview = expansion.expand_target(ORG, "department", "dep-1")
    assert preview.count == 2 and preview.capped is False
    assignment = service.create_assignment(
        access(), course=published_course()[0], target_type="department", target_ref="dep-1"
    )
    assert assignment.enrollments.count() == preview.count


def test_the_expansion_is_capped_and_says_so(
    db: Any, directory: StubDirectory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(expansion, "MAX_RECIPIENTS", 1)
    preview = expansion.expand_target(ORG, "department", "dep-1")
    assert preview.count == 1
    assert preview.capped is True


def test_an_organization_target_unions_every_role(db: Any, directory: StubDirectory) -> None:
    directory.add_role(ORG, "manager", "Manager")
    directory.add_user(ORG, member("u-9", ("dep-2",), role="manager"))
    preview = expansion.expand_target(ORG, "organization", None)
    assert preview.user_refs == ("u-1", "u-2", "u-3", "u-9")


def test_an_empty_target_is_refused(db: Any, directory: StubDirectory) -> None:
    with pytest.raises(TargetEmpty) as raised:
        service.create_assignment(
            admin(), course=published_course()[0], target_type="department", target_ref="dep-empty"
        )
    assert raised.value.code == "target_empty"


def test_a_target_outside_the_scope_is_not_found(db: Any, directory: StubDirectory) -> None:
    manager = access(departments=("dep-2",))
    with pytest.raises(NotFound):
        service.create_assignment(
            manager, course=published_course()[0], target_type="department", target_ref="dep-1"
        )


def test_a_role_target_needs_organization_wide_scope(db: Any, directory: StubDirectory) -> None:
    with pytest.raises(Forbidden):
        service.create_assignment(
            access(), course=published_course()[0], target_type="role", target_ref="employee"
        )
    assignment = service.create_assignment(
        admin(), course=published_course()[0], target_type="role", target_ref="employee"
    )
    assert assignment.enrollments.count() == 3


def test_a_course_without_a_published_version_cannot_be_assigned(
    db: Any, directory: StubDirectory
) -> None:
    course = make_course(ORG)
    make_version(ORG, course=course, status=CourseVersion.Status.DRAFT)
    with pytest.raises(StateConflict) as raised:
        service.create_assignment(
            access(), course=course, target_type="department", target_ref="dep-1"
        )
    assert raised.value.code == "course_not_published"


def test_an_archived_course_cannot_be_assigned(db: Any, directory: StubDirectory) -> None:
    course, _ = published_course()
    course.status = Course.Status.ARCHIVED
    course.save(update_fields=["status", "updated_at"])
    with pytest.raises(StateConflict) as raised:
        service.create_assignment(
            access(), course=course, target_type="department", target_ref="dep-1"
        )
    assert raised.value.code == "course_not_published"


def test_a_second_active_assignment_to_the_same_target_conflicts(
    db: Any, directory: StubDirectory
) -> None:
    course = published_course()[0]
    service.create_assignment(access(), course=course, target_type="department", target_ref="dep-1")
    with pytest.raises(StateConflict):
        service.create_assignment(
            access(), course=course, target_type="department", target_ref="dep-1"
        )


def test_an_organization_target_must_not_carry_a_reference(
    db: Any, directory: StubDirectory
) -> None:
    with pytest.raises(DomainValidationError):
        service.create_assignment(
            admin(), course=published_course()[0], target_type="organization", target_ref="x"
        )


def test_the_created_assignment_is_announced_once_for_the_batch(
    db: Any, directory: StubDirectory, django_capture_on_commit_callbacks: Any
) -> None:
    seen: list[DomainEvent] = []
    subscribe("assignment.created", seen.append)
    try:
        with django_capture_on_commit_callbacks(execute=True):
            service.create_assignment(
                access(), course=published_course()[0], target_type="department", target_ref="dep-1"
            )
    finally:
        unsubscribe("assignment.created", seen.append)
    assert len(seen) == 1
    assert seen[0].payload["recipients"] == 2


# --- cancellation -----------------------------------------------------------


def test_cancelling_an_assignment_cancels_its_enrollments(
    db: Any, directory: StubDirectory
) -> None:
    manager = access()
    assignment = service.create_assignment(
        manager, course=published_course()[0], target_type="department", target_ref="dep-1"
    )
    service.cancel_assignment(manager, assignment)
    rows = list(Enrollment.objects.for_org(ORG).filter(assignment=assignment))
    assert {row.status for row in rows} == {Enrollment.Status.CANCELLED}
    assert {row.cancel_reason for row in rows} == {Enrollment.CancelReason.UNASSIGNED}
    assert AuditEvent.objects.for_org(ORG).filter(action="assignment.cancelled").count() == 1
    # A repeat is a no-op rather than a second cancellation.
    service.cancel_assignment(manager, assignment)
    assert AuditEvent.objects.for_org(ORG).filter(action="assignment.cancelled").count() == 1


def test_cancelling_one_enrollment_is_audited(db: Any, directory: StubDirectory) -> None:
    manager = access()
    service.create_assignment(
        manager, course=published_course()[0], target_type="department", target_ref="dep-1"
    )
    enrollment = Enrollment.objects.for_org(ORG).get(user_ref="u-1")
    service.cancel_enrollment(manager, enrollment)
    enrollment.refresh_from_db()
    assert enrollment.status == Enrollment.Status.CANCELLED
    assert enrollment.cancel_reason == Enrollment.CancelReason.REMOVED_FROM_TARGET
    assert AuditEvent.objects.for_org(ORG).filter(action="enrollment.cancelled").count() == 1


def test_a_completed_enrollment_cannot_be_cancelled(db: Any, directory: StubDirectory) -> None:
    manager = access()
    service.create_assignment(
        manager, course=published_course()[0], target_type="department", target_ref="dep-1"
    )
    enrollment = Enrollment.objects.for_org(ORG).get(user_ref="u-1")
    enrollment.status = Enrollment.Status.COMPLETED
    enrollment.completed_at = timezone.now()
    enrollment.save(update_fields=["status", "completed_at", "updated_at"])
    with pytest.raises(StateConflict):
        service.cancel_enrollment(manager, enrollment)


# --- member_changed / member_deactivated ------------------------------------


def test_member_changed_enrolls_the_member_once(db: Any, directory: StubDirectory) -> None:
    service.create_assignment(
        access(), course=published_course()[0], target_type="department", target_ref="dep-1"
    )
    directory.add_user(ORG, member("u-7", ("dep-1",)))

    first = service.sync_member(ORG, "u-7", department_refs=("dep-1",), role="employee")
    second = service.sync_member(ORG, "u-7", department_refs=("dep-1",), role="employee")

    assert first == {"enrolled": 1, "cancelled": 0}
    assert second == {"enrolled": 0, "cancelled": 0}
    assert Enrollment.objects.for_org(ORG).filter(user_ref="u-7").count() == 1


def test_member_changed_cancels_what_the_member_left(db: Any, directory: StubDirectory) -> None:
    service.create_assignment(
        access(), course=published_course()[0], target_type="department", target_ref="dep-1"
    )
    result = service.sync_member(ORG, "u-1", department_refs=("dep-2",), role="employee")
    assert result == {"enrolled": 0, "cancelled": 1}
    enrollment = Enrollment.objects.for_org(ORG).get(user_ref="u-1")
    assert enrollment.status == Enrollment.Status.CANCELLED
    assert enrollment.cancel_reason == Enrollment.CancelReason.REMOVED_FROM_TARGET


def test_returning_to_the_department_creates_a_new_row(db: Any, directory: StubDirectory) -> None:
    service.create_assignment(
        access(), course=published_course()[0], target_type="department", target_ref="dep-1"
    )
    service.sync_member(ORG, "u-1", department_refs=("dep-2",), role="employee")
    service.sync_member(ORG, "u-1", department_refs=("dep-1",), role="employee")
    rows = Enrollment.objects.for_org(ORG).filter(user_ref="u-1").order_by("created_at")
    assert [row.status for row in rows] == [
        Enrollment.Status.CANCELLED,
        Enrollment.Status.ACTIVE,
    ]


def test_member_deactivated_cancels_every_active_enrollment(
    db: Any, directory: StubDirectory
) -> None:
    service.create_assignment(
        access(), course=published_course()[0], target_type="department", target_ref="dep-1"
    )
    assert service.sync_member(ORG, "u-1", is_active=False) == {"enrolled": 0, "cancelled": 1}
    enrollment = Enrollment.objects.for_org(ORG).get(user_ref="u-1")
    assert enrollment.cancel_reason == Enrollment.CancelReason.DEACTIVATED
    # The other member of the department is untouched.
    assert Enrollment.objects.for_org(ORG).get(user_ref="u-2").status == Enrollment.Status.ACTIVE


def test_the_webhook_drives_the_same_enrollment(
    db: Any, directory: StubDirectory, client: Client
) -> None:
    service.create_assignment(
        access(), course=published_course()[0], target_type="department", target_ref="dep-1"
    )
    directory.add_user(ORG, member("u-5", ("dep-1",)))
    body = {
        "event_id": str(uuid4()),
        "type": "member_changed",
        "organization_id": str(ORG),
        "user_ref": "u-5",
        "occurred_at": 1795132800,
        "department_refs": ["dep-1"],
        "role": "employee",
        "is_active": True,
    }
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    token = sign_webhook(raw, organization_id=ORG, kid=KID, secret=SECRET)
    with override_settings(**HUB):
        response = client.generic(
            "POST",
            "/internal/hub/webhooks/",
            data=raw,
            content_type="application/json",
            HTTP_X_MASHEED_WEBHOOK=token,
        )
    assert response.status_code == 200, response.content
    assert Enrollment.objects.for_org(ORG).filter(user_ref="u-5").exists()


def test_member_changed_on_a_cancelled_assignment_adds_nothing(
    db: Any, directory: StubDirectory
) -> None:
    manager = access()
    assignment = service.create_assignment(
        manager, course=published_course()[0], target_type="department", target_ref="dep-1"
    )
    service.cancel_assignment(manager, assignment)
    directory.add_user(ORG, member("u-8", ("dep-1",)))
    assert service.sync_member(ORG, "u-8", department_refs=("dep-1",)) == {
        "enrolled": 0,
        "cancelled": 0,
    }


# --- gating -----------------------------------------------------------------


def test_gating_locks_behind_an_incomplete_required_lesson(db: Any) -> None:
    course, version = published_course(lessons=3, optional_lesson=True)
    enrollment = make_enrollment(ORG, course=course, version=version)
    ordered = gating.ordered_lessons(enrollment)
    first, second, third = ordered[0], ordered[1], ordered[3]

    states = gating.state_for(ordered, set())
    assert states[first.pk] == (False, False)
    assert states[second.pk] == (True, False)
    assert states[third.pk] == (False, False)

    completed = {first.pk}
    states = gating.state_for(ordered, completed)
    assert states[second.pk] == (False, False)
    assert states[third.pk] == (False, False)


def test_a_non_required_lesson_never_locks_anything(db: Any) -> None:
    course, version = published_course(lessons=2, optional_lesson=True)
    enrollment = make_enrollment(ORG, course=course, version=version)
    ordered = gating.ordered_lessons(enrollment)
    gating.require_accessible(enrollment, ordered[2])
    with pytest.raises(LessonLocked) as raised:
        gating.require_accessible(enrollment, ordered[1])
    assert raised.value.fields["next_lesson_id"] == str(ordered[0].pk)


def test_a_locked_lesson_cannot_be_played(db: Any) -> None:
    course, version = published_course(lessons=2)
    enrollment = make_enrollment(ORG, course=course, version=version, user_ref="u-1")
    ordered = gating.ordered_lessons(enrollment)
    learner = access(user_ref="u-1", capabilities=(Capability.LEARN,))
    with pytest.raises(LessonLocked):
        playback_urls(learner, enrollment.pk, ordered[1].pk)


def test_progress_percent_counts_only_required_lessons(db: Any) -> None:
    course, version = published_course(lessons=2, optional_lesson=True)
    enrollment = make_enrollment(ORG, course=course, version=version)
    ordered = gating.ordered_lessons(enrollment)
    assert gating.progress_percent(ordered, set()) == 0
    assert gating.progress_percent(ordered, {ordered[0].pk}) == 50


def test_the_outline_marks_the_next_lesson(db: Any) -> None:
    course, version = published_course(lessons=2)
    enrollment = make_enrollment(ORG, course=course, version=version)
    ordered = gating.ordered_lessons(enrollment)
    make_progress(ORG, enrollment=enrollment, lesson=ordered[0], completed_at=timezone.now())
    sections = gating.outline(enrollment)
    lessons = sections[0]["lessons"]
    assert [lesson["completed"] for lesson in lessons] == [True, False]
    assert [lesson["locked"] for lesson in lessons] == [False, False]


# --- API --------------------------------------------------------------------


def grant(
    user_ref: str, capability: str, scope_type: str = "department", scope_ref: str = "dep-1"
) -> None:
    make_grant(
        ORG,
        user_ref=user_ref,
        capability=capability,
        scope_type=scope_type,
        scope_ref=scope_ref,
    )


def call(
    client: Client,
    method: str,
    path: str,
    *,
    user_ref: str = "u-manager",
    body: dict[str, Any] | None = None,
    role: str = "department_manager",
    headers: dict[str, str] | None = None,
) -> Any:
    token = sign_identity(
        method=method,
        target=path,
        organization_id=ORG,
        user_ref=user_ref,
        role=role,
        kid=KID,
        secret=SECRET,
    )
    extra: dict[str, Any] = {"HTTP_X_MASHEED_IDENTITY": token}
    for name, value in (headers or {}).items():
        extra[f"HTTP_{name.upper().replace('-', '_')}"] = value
    payload = json.dumps(body) if body is not None else None
    with override_settings(**HUB):
        return client.generic(method, path, data=payload, content_type="application/json", **extra)


def test_the_api_creates_an_assignment_idempotently(db: Any, directory: StubDirectory) -> None:
    grant("u-manager", "assign")
    course = published_course()[0]
    body = {"course_id": str(course.pk), "target_type": "department", "target_ref": "dep-1"}
    first = call(Client(), "POST", ASSIGNMENTS, body=body, headers={"Idempotency-Key": "k-1"})
    assert first.status_code == 201, first.content
    assert first.json()["enrollment_count"] == 2
    replay = call(Client(), "POST", ASSIGNMENTS, body=body, headers={"Idempotency-Key": "k-1"})
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert Enrollment.objects.for_org(ORG).count() == 2


def test_the_api_requires_an_idempotency_key(db: Any, directory: StubDirectory) -> None:
    grant("u-manager", "assign")
    body = {
        "course_id": str(published_course()[0].pk),
        "target_type": "department",
        "target_ref": "dep-1",
    }
    response = call(Client(), "POST", ASSIGNMENTS, body=body)
    assert response.status_code == 400


def test_the_api_previews_a_target(db: Any, directory: StubDirectory) -> None:
    grant("u-manager", "assign")
    response = call(
        Client(), "POST", PREVIEW, body={"target_type": "department", "target_ref": "dep-1"}
    )
    assert response.status_code == 200, response.content
    assert response.json() == {"count": 2, "capped": False}


def test_the_api_cancels_an_assignment(db: Any, directory: StubDirectory) -> None:
    grant("u-manager", "assign")
    body = {
        "course_id": str(published_course()[0].pk),
        "target_type": "department",
        "target_ref": "dep-1",
    }
    created = call(Client(), "POST", ASSIGNMENTS, body=body, headers={"Idempotency-Key": "k-2"})
    cancelled = call(Client(), "DELETE", f"{ASSIGNMENTS}{created.json()['id']}/")
    assert cancelled.status_code == 204
    assert Enrollment.objects.for_org(ORG).filter(status=Enrollment.Status.ACTIVE).count() == 0


def test_an_out_of_scope_assignment_is_not_found(db: Any, directory: StubDirectory) -> None:
    grant("u-3", "assign", scope_ref="dep-2")
    foreign = make_assignment(ORG, course=published_course()[0])
    response = call(Client(), "DELETE", f"{ASSIGNMENTS}{foreign.pk}/", user_ref="u-3")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_the_roster_lists_the_department_enrollments(db: Any, directory: StubDirectory) -> None:
    grant("u-manager", "assign")
    course = published_course()[0]
    body = {"course_id": str(course.pk), "target_type": "department", "target_ref": "dep-1"}
    call(Client(), "POST", ASSIGNMENTS, body=body, headers={"Idempotency-Key": "k-3"})
    response = call(Client(), "GET", f"/api/v1/academy/manage/courses/{course.pk}/enrollments/")
    assert response.status_code == 200, response.content
    assert [row["user_ref"] for row in response.json()["results"]] == ["u-1", "u-2"]


def test_a_learner_sees_their_own_course_only(db: Any, directory: StubDirectory) -> None:
    grant("u-manager", "assign")
    grant("u-1", "learn")
    grant("u-2", "learn")
    course = published_course()[0]
    body = {"course_id": str(course.pk), "target_type": "department", "target_ref": "dep-1"}
    call(Client(), "POST", ASSIGNMENTS, body=body, headers={"Idempotency-Key": "k-4"})

    mine = call(Client(), "GET", MY_COURSES, user_ref="u-1", role="employee")
    assert mine.status_code == 200, mine.content
    assert [row["user_ref"] for row in mine.json()["results"]] == ["u-1"]
    assert mine["Cache-Control"] == "private, no-store"

    enrollment = Enrollment.objects.for_org(ORG).get(user_ref="u-2")
    detail = call(
        Client(), "GET", f"{MY_ENROLLMENTS}{enrollment.pk}/", user_ref="u-1", role="employee"
    )
    assert detail.status_code == 404


def test_the_enrollment_detail_carries_the_outline(db: Any, directory: StubDirectory) -> None:
    grant("u-manager", "assign")
    grant("u-1", "learn")
    course = published_course(lessons=2)[0]
    body = {"course_id": str(course.pk), "target_type": "department", "target_ref": "dep-1"}
    created = call(Client(), "POST", ASSIGNMENTS, body=body, headers={"Idempotency-Key": "k-5"})
    enrollment = Enrollment.objects.for_org(ORG).get(
        user_ref="u-1", assignment_id=created.json()["id"]
    )
    detail = call(
        Client(), "GET", f"{MY_ENROLLMENTS}{enrollment.pk}/", user_ref="u-1", role="employee"
    )
    assert detail.status_code == 200, detail.content
    sections = detail.json()["sections"]
    assert [lesson["locked"] for lesson in sections[0]["lessons"]] == [False, True]


def test_an_anonymous_caller_is_401(db: Any) -> None:
    with override_settings(**HUB):
        response = Client().get(ASSIGNMENTS)
    assert response.status_code == 401


def test_a_caller_without_the_capability_is_403(db: Any, directory: StubDirectory) -> None:
    grant("u-1", "learn")
    response = call(Client(), "GET", ASSIGNMENTS, user_ref="u-1", role="employee")
    assert response.status_code == 403


def test_the_audit_metadata_stays_within_the_contract(db: Any, directory: StubDirectory) -> None:
    service.create_assignment(
        access(), course=published_course()[0], target_type="department", target_ref="dep-1"
    )
    row = AuditEvent.objects.for_org(ORG).get(action="assignment.created")
    assert set(row.metadata) == {"course_id", "target_type", "recipients", "capped"}
