"""T-007 acceptance: the assignment, enrollment, progress and completion schema.

Each rule of ``docs/domain-model.md`` §2.6–§2.9 is tested by writing the row it forbids; the
service that will enforce the rest does not exist yet, so the database is the only witness.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from academy.models import (
    Assignment,
    CompletionRecord,
    Course,
    CourseVersion,
    Enrollment,
    Lesson,
    LessonProgress,
    Section,
)

pytestmark = pytest.mark.django_db

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
OTHER_ORG = UUID("2f5e3d1a-0c4b-4a8e-9f2d-6b7c8d9e0f11")


@pytest.fixture
def course() -> Course:
    return Course.objects.create(organization_id=ORG, title="Sample course", created_by_ref="u-10")


@pytest.fixture
def version(course: Course) -> CourseVersion:
    return CourseVersion.objects.create(
        organization_id=ORG, course=course, version_number=1, created_by_ref="u-10"
    )


@pytest.fixture
def assignment(course: Course) -> Assignment:
    return Assignment.objects.create(
        organization_id=ORG,
        course=course,
        target_type=Assignment.TargetType.DEPARTMENT,
        target_ref="dep-1",
        assigned_by_ref="u-10",
    )


@pytest.fixture
def enrollment(course: Course, version: CourseVersion) -> Enrollment:
    return Enrollment.objects.create(
        organization_id=ORG,
        course=course,
        course_version=version,
        user_ref="u-20",
    )


@pytest.fixture
def lesson(version: CourseVersion) -> Lesson:
    section = Section.objects.create(
        organization_id=ORG, version=version, title="Intro", position=1
    )
    return Lesson.objects.create(
        organization_id=ORG,
        section=section,
        title="Lesson one",
        position=1,
        content_type=Lesson.ContentType.TEXT,
        body="Read this.",
    )


def make_assignment(course: Course, **overrides: object) -> Assignment:
    values: dict[str, object] = {
        "organization_id": ORG,
        "course": course,
        "target_type": Assignment.TargetType.USER,
        "target_ref": "u-20",
        "assigned_by_ref": "u-10",
    }
    values.update(overrides)
    return Assignment.objects.create(**values)


def make_enrollment(course: Course, version: CourseVersion, **overrides: object) -> Enrollment:
    values: dict[str, object] = {
        "organization_id": ORG,
        "course": course,
        "course_version": version,
        "user_ref": "u-20",
    }
    values.update(overrides)
    return Enrollment.objects.create(**values)


def make_progress(enrollment: Enrollment, lesson: Lesson, **overrides: object) -> LessonProgress:
    values: dict[str, object] = {
        "organization_id": ORG,
        "enrollment": enrollment,
        "lesson": lesson,
    }
    values.update(overrides)
    return LessonProgress.objects.create(**values)


def make_completion(enrollment: Enrollment, **overrides: object) -> CompletionRecord:
    values: dict[str, object] = {
        "organization_id": ORG,
        "enrollment": enrollment,
        "course_id": enrollment.course.pk,
        "course_version_id": enrollment.course_version.pk,
        "user_ref": enrollment.user_ref,
        "completed_at": timezone.now(),
        "actor_ref": enrollment.user_ref,
    }
    values.update(overrides)
    return CompletionRecord.objects.create(**values)


def test_assignment_rows_are_scoped_by_organization(course: Course) -> None:
    make_assignment(course)
    Course.objects.create(organization_id=OTHER_ORG, title="Other", created_by_ref="u-99")

    assert Assignment.objects.for_org(ORG).count() == 1
    assert Assignment.objects.count() == 1


def test_assignment_target_type_must_be_known(course: Course) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_assignment(course, target_type="team")


def test_organization_target_must_not_carry_a_ref(course: Course) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_assignment(course, target_type=Assignment.TargetType.ORGANIZATION, target_ref="dep-1")


def test_every_other_target_needs_a_ref(course: Course) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_assignment(course, target_ref=None)


def test_one_active_assignment_per_target(course: Course) -> None:
    make_assignment(course)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_assignment(course)


def test_the_organization_target_is_unique_too(course: Course) -> None:
    make_assignment(course, target_type=Assignment.TargetType.ORGANIZATION, target_ref=None)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_assignment(course, target_type=Assignment.TargetType.ORGANIZATION, target_ref=None)


def test_a_cancelled_assignment_frees_its_target(course: Course) -> None:
    first = make_assignment(course)
    first.cancelled_at = timezone.now()
    first.save()

    second = make_assignment(course)

    assert Assignment.objects.filter(course=course, cancelled_at__isnull=True).count() == 1
    assert second.pk != first.pk


def test_an_assignment_cannot_be_cancelled_before_it_exists(course: Course) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_assignment(course, cancelled_at=timezone.now() - timedelta(days=1))


def test_enrollment_defaults(course: Course, version: CourseVersion) -> None:
    enrollment = make_enrollment(course, version)

    assert enrollment.status == Enrollment.Status.ACTIVE
    assert enrollment.mandatory is True
    assert enrollment.cancel_reason is None


def test_one_active_enrollment_per_learner_and_course(
    course: Course, version: CourseVersion
) -> None:
    make_enrollment(course, version)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_enrollment(course, version)


def test_another_learner_may_enroll_in_the_same_course(
    course: Course, version: CourseVersion
) -> None:
    make_enrollment(course, version)

    other = make_enrollment(course, version, user_ref="u-21")

    assert Enrollment.objects.for_org(ORG).count() == 2
    assert other.status == Enrollment.Status.ACTIVE


def test_a_cancelled_enrollment_does_not_block_a_new_one(
    course: Course, version: CourseVersion
) -> None:
    old = make_enrollment(course, version)
    old.status = Enrollment.Status.CANCELLED
    old.cancelled_at = timezone.now()
    old.cancel_reason = Enrollment.CancelReason.DEACTIVATED
    old.save()

    new = make_enrollment(course, version)

    assert new.pk != old.pk
    assert Enrollment.objects.filter(user_ref="u-20").count() == 2


def test_a_completed_enrollment_must_carry_its_completion_time(
    course: Course, version: CourseVersion
) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_enrollment(course, version, status=Enrollment.Status.COMPLETED)


def test_a_cancelled_enrollment_must_carry_its_cancellation_time(
    course: Course, version: CourseVersion
) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_enrollment(course, version, status=Enrollment.Status.CANCELLED)


def test_a_cancel_reason_must_be_known(course: Course, version: CourseVersion) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_enrollment(course, version, cancel_reason="manager_mood")


def test_progress_has_one_row_per_lesson(enrollment: Enrollment, lesson: Lesson) -> None:
    make_progress(enrollment, lesson)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_progress(enrollment, lesson)


def test_progress_defaults_are_empty(enrollment: Enrollment, lesson: Lesson) -> None:
    progress = make_progress(enrollment, lesson)

    assert progress.watched_ranges == []
    assert progress.watched_seconds == Decimal("0.0")
    assert progress.position_seconds == Decimal("0.0")
    assert progress.frontier_seconds == Decimal("0.0")
    assert progress.skip_attempts == 0
    assert progress.completed_at is None


def test_watched_seconds_cannot_be_negative(enrollment: Enrollment, lesson: Lesson) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_progress(enrollment, lesson, watched_seconds=Decimal("-1.0"))


def test_the_frontier_cannot_run_past_the_position(enrollment: Enrollment, lesson: Lesson) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_progress(
            enrollment,
            lesson,
            position_seconds=Decimal("10.0"),
            frontier_seconds=Decimal("11.0"),
        )


def test_a_frontier_inside_the_position_saves(enrollment: Enrollment, lesson: Lesson) -> None:
    progress = make_progress(
        enrollment,
        lesson,
        watched_ranges=[[0, 10]],
        watched_seconds=Decimal("10.0"),
        position_seconds=Decimal("10.0"),
        frontier_seconds=Decimal("10.0"),
    )

    assert progress.watched_ranges == [[0, 10]]


def test_one_completion_per_enrollment(enrollment: Enrollment) -> None:
    make_completion(enrollment)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_completion(enrollment)


def test_a_completion_snapshots_the_version(enrollment: Enrollment) -> None:
    record = make_completion(enrollment)

    assert record.course_id == enrollment.course.pk
    assert record.course_version_id == enrollment.course_version.pk
    assert record.method == CompletionRecord.Method.LESSONS


def test_a_completion_method_must_be_known(enrollment: Enrollment) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_completion(enrollment, method="import")


def test_a_completion_cannot_be_updated(enrollment: Enrollment) -> None:
    make_completion(enrollment)

    with pytest.raises(DatabaseError, match="completion_record_immutable"), transaction.atomic():
        CompletionRecord.objects.filter(enrollment=enrollment).update(actor_ref="u-99")


def test_a_completion_cannot_be_deleted(enrollment: Enrollment) -> None:
    record = make_completion(enrollment)

    with pytest.raises(DatabaseError, match="completion_record_immutable"), transaction.atomic():
        record.delete()
