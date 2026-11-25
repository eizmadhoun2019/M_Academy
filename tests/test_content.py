"""T-017 acceptance: content services, publish validation and the management API.

Services are tested with a hand-built ``Access`` so scope rules are exercised without HTTP;
the API half runs in ``grants_only`` over signed Hub identities, the production mode (D-027).
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import pytest
from django.test import Client, override_settings
from factories import (
    make_course,
    make_grant,
    make_lesson,
    make_media,
    make_section,
    make_version,
)

from academy.authorization.core import Access, Capability, Principal, Scope
from academy.content import service
from academy.content.validation import validate_for_publish
from academy.exceptions import Forbidden, NotFound, PublishInvalid, StateConflict
from academy.models import AuditEvent, Course, CourseVersion, Lesson, Section
from host_hub.fake import DEFAULT_KID, sign_identity

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
SECRET = "test-identity-secret-that-is-at-least-32-bytes"
KID = DEFAULT_KID
COURSES = "/api/v1/academy/manage/courses/"

HUB = dict(
    ACADEMY_ACCESS_MODE="hub",
    ACADEMY_HUB_IDENTITY_KEYS={KID: SECRET},
    ACADEMY_HUB_WEBHOOK_KEYS={KID: SECRET},
    ACADEMY_AUTHORIZATION_MODE="grants_only",
)


def access(
    *,
    user_ref: str = "u-manager",
    departments: tuple[str, ...] = ("dep-1",),
    capabilities: tuple[Capability, ...] = (Capability.MANAGE_CONTENT,),
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


def manager(**overrides: Any) -> Access:
    return access(**overrides)


def admin() -> Access:
    return access(user_ref="u-admin", capabilities=tuple(Capability), everything=True)


def valid_version(**overrides: Any) -> CourseVersion:
    course = make_course(ORG, **overrides)
    version = make_version(ORG, course=course)
    first = make_section(ORG, version=version, title="One", position=1)
    second = make_section(ORG, version=version, title="Two", position=2)
    make_lesson(ORG, section=first, position=1, title="A", body="Read")
    make_lesson(ORG, section=second, position=1, title="B", body="Read")
    return version


# --- services ---------------------------------------------------------------


def test_create_course_opens_draft_version_one(db: Any) -> None:
    course = service.create_course(
        manager(), title=" Safety ", description="Basics", owner_department_ref="dep-1"
    )
    version = CourseVersion.objects.get(course=course)
    assert course.title == "Safety"
    assert version.version_number == 1
    assert version.status == CourseVersion.Status.DRAFT
    assert AuditEvent.objects.filter(action="course.created", object_id=str(course.pk)).exists()


def test_a_general_course_needs_an_administrator(db: Any) -> None:
    with pytest.raises(Forbidden):
        service.create_course(manager(), title="General")
    course = service.create_course(admin(), title="General")
    assert course.owner_department_ref is None


def test_a_course_outside_the_department_scope_is_not_found(db: Any) -> None:
    foreign = make_course(ORG, owner_department_ref="dep-9")
    with pytest.raises(NotFound):
        service.require_course(manager(), ORG, foreign.pk)
    assert service.list_courses(manager()) == []


def test_a_platform_course_is_admin_only(db: Any) -> None:
    general = make_course(ORG, title="General")
    with pytest.raises(NotFound):
        service.require_course(manager(everything=True), ORG, general.pk)


def test_clone_copies_the_tree_and_numbers_the_version(db: Any) -> None:
    version = valid_version()
    service.publish_version(admin(), version)
    clone = service.clone_version(admin(), version.course)
    assert clone.version_number == 2
    assert clone.status == CourseVersion.Status.DRAFT
    assert clone.sections.count() == 2
    assert Lesson.objects.filter(section__version=clone).count() == 2
    with pytest.raises(StateConflict) as error:
        service.clone_version(admin(), version.course)
    assert error.value.code == "draft_exists"


def test_publish_rejects_a_thin_version_with_every_reason(db: Any) -> None:
    course = make_course(ORG)
    version = make_version(ORG, course=course)
    section = make_section(ORG, version=version, position=3)
    make_lesson(ORG, section=section, content_type="text", body="")
    codes = {reason["code"] for reason in validate_for_publish(version)}
    assert {"too_few_sections", "too_few_lessons", "position_gap"} <= codes
    with pytest.raises(PublishInvalid) as error:
        service.publish_version(admin(), version)
    assert error.value.code == "publish_invalid"
    assert len(error.value.fields["items"]) >= 3


def test_lesson_media_rules(db: Any) -> None:
    course = make_course(ORG)
    version = make_version(ORG, course=course)
    first = make_section(ORG, version=version, position=1)
    second = make_section(ORG, version=version, position=2)
    make_lesson(ORG, section=first, content_type="video", body=None, position=1)
    processing = make_media(ORG, status="uploaded", storage_key="k")
    make_lesson(
        ORG,
        section=second,
        content_type="video",
        body=None,
        media_asset=processing,
        position=1,
    )
    codes = {(reason["code"], reason.get("lesson_id")) for reason in validate_for_publish(version)}
    assert any(code == "lesson_media_missing" for code, _ in codes)
    assert any(code == "lesson_media_not_ready" for code, _ in codes)


def test_text_lesson_without_body_is_reported(db: Any) -> None:
    course = make_course(ORG)
    version = make_version(ORG, course=course)
    first = make_section(ORG, version=version, position=1)
    second = make_section(ORG, version=version, position=2)
    make_lesson(ORG, section=first, body="Read", position=1)
    lesson = make_lesson(ORG, section=second, body=" ", position=1)
    reasons = validate_for_publish(version)
    assert {"code": "text_lesson_empty", "lesson_id": str(lesson.pk)} in reasons


def test_publish_archives_the_previous_version(db: Any) -> None:
    version = valid_version()
    service.publish_version(admin(), version)
    version.refresh_from_db()
    assert version.status == CourseVersion.Status.PUBLISHED
    assert version.published_by_ref == "u-admin"
    assert version.course.status == Course.Status.PUBLISHED

    second = service.clone_version(admin(), version.course)
    service.publish_version(admin(), second)
    second.refresh_from_db()
    version.refresh_from_db()
    assert second.status == CourseVersion.Status.PUBLISHED
    assert version.status == CourseVersion.Status.ARCHIVED
    assert AuditEvent.objects.filter(action="course.published").count() == 2


def test_published_versions_are_frozen(db: Any) -> None:
    version = valid_version()
    service.publish_version(admin(), version)
    with pytest.raises(StateConflict) as error:
        service.create_section(admin(), version, title="Late")
    assert error.value.code == "version_published"
    lesson = Lesson.objects.filter(section__version=version).first()
    assert lesson is not None
    with pytest.raises(StateConflict):
        service.update_lesson(admin(), lesson, {"title": "Renamed"})
    with pytest.raises(StateConflict):
        service.discard_version(admin(), version)


def test_discard_removes_only_a_draft(db: Any) -> None:
    version = valid_version()
    service.discard_version(admin(), version)
    assert not CourseVersion.objects.filter(pk=version.pk).exists()


def test_archive_course_archives_the_published_version(db: Any) -> None:
    version = valid_version()
    service.publish_version(admin(), version)
    service.archive_course(admin(), version.course)
    version.refresh_from_db()
    version.course.refresh_from_db()
    assert version.status == CourseVersion.Status.ARCHIVED
    assert version.course.status == Course.Status.ARCHIVED


def test_owner_department_is_locked_while_published(db: Any) -> None:
    version = valid_version(owner_department_ref="dep-1")
    service.publish_version(admin(), version)
    with pytest.raises(StateConflict) as error:
        service.update_course(admin(), version.course, owner_department_ref="dep-2")
    assert error.value.code == "course_published_locked"
    updated = service.update_course(admin(), version.course, title="Renamed")
    assert updated.title == "Renamed"


def test_reorder_sections_requires_the_full_list(db: Any) -> None:
    version = valid_version()
    rows = list(Section.objects.filter(version=version).order_by("position"))
    with pytest.raises(StateConflict) as error:
        service.reorder_sections(admin(), version, [rows[0].pk])
    assert error.value.code == "position_mismatch"
    ordered = service.reorder_sections(admin(), version, [rows[1].pk, rows[0].pk])
    assert [row.pk for row in ordered] == [rows[1].pk, rows[0].pk]
    assert Section.objects.get(pk=rows[0].pk).position == 2


def test_reorder_lessons_within_a_section(db: Any) -> None:
    version = valid_version()
    section = Section.objects.filter(version=version).first()
    assert section is not None
    second_lesson = make_lesson(ORG, section=section, position=2, title="Second", body="Read")
    first_lesson = Lesson.objects.get(section=section, position=1)
    service.reorder_lessons(admin(), section, [second_lesson.pk, first_lesson.pk])
    assert Lesson.objects.get(pk=first_lesson.pk).position == 2
    with pytest.raises(StateConflict):
        service.reorder_lessons(admin(), section, [first_lesson.pk])


# --- API --------------------------------------------------------------------


def call(
    client: Client,
    method: str,
    path: str,
    *,
    user_ref: str = "u-manager",
    body: dict[str, Any] | None = None,
) -> Any:
    token = sign_identity(
        method=method,
        target=path,
        organization_id=ORG,
        user_ref=user_ref,
        role="employee",
        kid=KID,
        secret=SECRET,
    )
    extra: dict[str, Any] = {"HTTP_X_MASHEED_IDENTITY": token}
    payload = json.dumps(body) if body is not None else None
    with override_settings(**HUB):
        if method == "POST":
            return client.post(path, data=payload, content_type="application/json", **extra)
        if method == "PATCH":
            return client.patch(path, data=payload, content_type="application/json", **extra)
        if method == "DELETE":
            return client.delete(path, **extra)
        return client.get(path, **extra)


def grant_manager(user_ref: str = "u-manager", departments: tuple[str, ...] = ("dep-1",)) -> None:
    for department in departments:
        make_grant(
            ORG,
            user_ref=user_ref,
            capability="manage_content",
            scope_type="department",
            scope_ref=department,
        )


def test_the_api_creates_lists_and_patches_a_course(db: Any) -> None:
    grant_manager()
    created = call(
        Client(), "POST", COURSES, body={"title": "Fire safety", "owner_department_ref": "dep-1"}
    )
    assert created.status_code == 201, created.content
    course_id = created.json()["id"]
    listing = call(Client(), "GET", COURSES)
    assert listing.status_code == 200
    assert [row["id"] for row in listing.json()["results"]] == [course_id]
    patched = call(Client(), "PATCH", f"{COURSES}{course_id}/", body={"title": "Fire drill"})
    assert patched.status_code == 200
    assert patched.json()["title"] == "Fire drill"


def test_a_caller_without_the_capability_is_refused(db: Any) -> None:
    response = call(Client(), "GET", COURSES)
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_a_foreign_course_is_not_found(db: Any) -> None:
    grant_manager()
    foreign = make_course(ORG, owner_department_ref="dep-9")
    response = call(Client(), "GET", f"{COURSES}{foreign.pk}/")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_publish_returns_422_with_each_reason(db: Any) -> None:
    grant_manager()
    course = make_course(ORG, owner_department_ref="dep-1")
    version = make_version(ORG, course=course)
    response = call(Client(), "POST", f"/api/v1/academy/manage/versions/{version.pk}/publish/")
    assert response.status_code == 422, response.content
    payload = response.json()
    assert payload["code"] == "publish_invalid"
    codes = {item["code"] for item in payload["fields"]["items"]}
    assert "too_few_sections" in codes


def test_the_section_and_lesson_api_round_trip(db: Any) -> None:
    grant_manager()
    created = call(
        Client(), "POST", COURSES, body={"title": "Course", "owner_department_ref": "dep-1"}
    )
    course_id = created.json()["id"]
    version_id = call(Client(), "GET", f"{COURSES}{course_id}/").json()["draft_version_id"]

    first = call(
        Client(),
        "POST",
        f"/api/v1/academy/manage/versions/{version_id}/sections/",
        body={"title": "One"},
    )
    second = call(
        Client(),
        "POST",
        f"/api/v1/academy/manage/versions/{version_id}/sections/",
        body={"title": "Two"},
    )
    assert first.status_code == second.status_code == 201
    section_id = first.json()["id"]
    lesson = call(
        Client(),
        "POST",
        f"/api/v1/academy/manage/sections/{section_id}/lessons/",
        body={"title": "Read", "content_type": "text", "body": "Text"},
    )
    assert lesson.status_code == 201, lesson.content
    reorder = call(
        Client(),
        "POST",
        f"/api/v1/academy/manage/versions/{version_id}/sections/reorder/",
        body={"ids": [second.json()["id"], section_id]},
    )
    assert reorder.status_code == 200
    assert [row["title"] for row in reorder.json()] == ["Two", "One"]
    tree = call(Client(), "GET", f"/api/v1/academy/manage/versions/{version_id}/")
    assert tree.status_code == 200
    assert len(tree.json()["sections"]) == 2
    assert tree.json()["sections"][1]["lessons"][0]["title"] == "Read"


def test_discard_and_clone_over_http(db: Any) -> None:
    grant_manager()
    version = valid_version(owner_department_ref="dep-1")
    service.publish_version(admin(), version)
    cloned = call(Client(), "POST", f"{COURSES}{version.course_id}/versions/")
    assert cloned.status_code == 201
    assert cloned.json()["version_number"] == 2
    again = call(Client(), "POST", f"{COURSES}{version.course_id}/versions/")
    assert again.status_code == 409
    assert again.json()["code"] == "draft_exists"
    discarded = call(
        Client(), "POST", f"/api/v1/academy/manage/versions/{cloned.json()['id']}/discard/"
    )
    assert discarded.status_code == 204
