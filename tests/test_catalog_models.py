"""T-006 acceptance: the catalog schema, its constraints and its freeze triggers.

The database is the last line of defence, so each rule from ``docs/domain-model.md`` §2.1–§2.5
is tested by writing the row it forbids rather than by trusting the service that will write it
later.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.utils import timezone

from academy.models import Course, CourseVersion, Lesson, MediaAsset, Section

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
def section(version: CourseVersion) -> Section:
    return Section.objects.create(organization_id=ORG, version=version, title="Intro", position=1)


def publish(version: CourseVersion) -> CourseVersion:
    version.status = CourseVersion.Status.PUBLISHED
    version.published_at = timezone.now()
    version.published_by_ref = "u-10"
    version.save()
    return version


def make_media(**overrides: object) -> MediaAsset:
    values: dict[str, object] = {
        "organization_id": ORG,
        "kind": MediaAsset.Kind.VIDEO,
        "status": MediaAsset.Status.AWAITING_UPLOAD,
        "created_by_ref": "u-10",
    }
    values.update(overrides)
    return MediaAsset.objects.create(**values)


def make_lesson(section: Section, **overrides: object) -> Lesson:
    values: dict[str, object] = {
        "organization_id": ORG,
        "section": section,
        "title": "Lesson one",
        "position": 1,
        "content_type": Lesson.ContentType.TEXT,
        "body": "Read this.",
    }
    values.update(overrides)
    return Lesson.objects.create(**values)


def test_rows_are_scoped_by_organization(course: Course) -> None:
    Course.objects.create(organization_id=OTHER_ORG, title="Other", created_by_ref="u-99")

    assert list(Course.objects.for_org(ORG).values_list("title", flat=True)) == ["Sample course"]
    assert Course.objects.count() == 2


def test_a_course_title_cannot_be_blank() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Course.objects.create(organization_id=ORG, title="   ", created_by_ref="u-10")


def test_a_course_status_must_be_known(course: Course) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Course.objects.filter(pk=course.pk).update(status="deleted")


def test_version_numbers_start_at_one(version: CourseVersion) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseVersion.objects.create(
            organization_id=ORG, course=version.course, version_number=0, created_by_ref="u-10"
        )


def test_a_version_number_is_unique_per_course(version: CourseVersion) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseVersion.objects.create(
            organization_id=ORG, course=version.course, version_number=1, created_by_ref="u-10"
        )


def test_only_one_version_of_a_course_is_published(version: CourseVersion) -> None:
    publish(version)
    second = CourseVersion.objects.create(
        organization_id=ORG, course=version.course, version_number=2, created_by_ref="u-10"
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        publish(second)


def test_a_published_version_must_be_stamped(version: CourseVersion) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        CourseVersion.objects.filter(pk=version.pk).update(status="published")


def test_section_positions_start_at_one(version: CourseVersion) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Section.objects.create(organization_id=ORG, version=version, title="Zero", position=0)


def test_two_sections_cannot_share_a_position(version: CourseVersion, section: Section) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Section.objects.create(organization_id=ORG, version=version, title="Dup", position=1)
        # The constraint is DEFERRABLE INITIALLY DEFERRED (so reordering can move positions
        # in one transaction); asking for an immediate check proves it exists.
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS section_position_per_version IMMEDIATE")


def test_lesson_positions_are_unique_inside_a_section(section: Section) -> None:
    make_lesson(section)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_lesson(section, title="Dup")
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS lesson_position_per_section IMMEDIATE")


def test_lesson_watch_percent_stays_in_range(section: Section) -> None:
    for value in (49, 101):
        with pytest.raises(IntegrityError), transaction.atomic():
            make_lesson(section, required_watch_percent=value)


def test_lesson_content_type_must_be_known(section: Section) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_lesson(section, content_type="audio")


def test_a_pdf_lesson_needs_a_body(section: Section) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_lesson(section, content_type="pdf", body=None)


def test_a_ready_asset_needs_a_storage_key() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_media(status="ready", content_type="image/png")


def test_a_ready_video_needs_a_positive_duration() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_media(
            status="ready",
            storage_key=f"org/{ORG}/media/{ORG}/original.mp4",
            duration_seconds=0,
        )


def test_a_failed_asset_needs_an_error_code() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_media(status="failed")


def test_a_ready_asset_saves(version: CourseVersion) -> None:
    asset = make_media(
        status="ready",
        storage_key=f"org/{ORG}/media/{ORG}/original.mp4",
        duration_seconds="12.500",
        ready_at=timezone.now(),
    )

    assert asset.renditions == {}
    assert asset.attempt_count == 0


def test_a_published_version_content_is_frozen(version: CourseVersion) -> None:
    publish(version)

    with pytest.raises(DatabaseError, match="courseversion_immutable"), transaction.atomic():
        CourseVersion.objects.filter(pk=version.pk).update(acknowledgment_required=True)


def test_a_published_version_cannot_return_to_draft(version: CourseVersion) -> None:
    publish(version)

    with pytest.raises(DatabaseError, match="courseversion_immutable"), transaction.atomic():
        CourseVersion.objects.filter(pk=version.pk).update(status="draft")


def test_a_published_version_may_be_archived_and_stays_archived(version: CourseVersion) -> None:
    publish(version)

    CourseVersion.objects.filter(pk=version.pk).update(status="archived")

    with pytest.raises(DatabaseError, match="courseversion_immutable"), transaction.atomic():
        CourseVersion.objects.filter(pk=version.pk).update(status="published")


def test_a_draft_version_is_editable(version: CourseVersion) -> None:
    CourseVersion.objects.filter(pk=version.pk).update(acknowledgment_required=True)

    assert CourseVersion.objects.get(pk=version.pk).acknowledgment_required is True


def test_a_section_cannot_be_added_to_a_published_version(version: CourseVersion) -> None:
    publish(version)

    with pytest.raises(DatabaseError, match="version_content_frozen"), transaction.atomic():
        Section.objects.create(organization_id=ORG, version=version, title="Late", position=1)


def test_a_section_of_a_published_version_cannot_change(version: CourseVersion) -> None:
    section = Section.objects.create(
        organization_id=ORG, version=version, title="Intro", position=1
    )
    publish(version)

    with pytest.raises(DatabaseError, match="version_content_frozen"), transaction.atomic():
        Section.objects.filter(pk=section.pk).update(title="Renamed")


def test_a_section_of_a_published_version_cannot_be_deleted(version: CourseVersion) -> None:
    section = Section.objects.create(
        organization_id=ORG, version=version, title="Intro", position=1
    )
    publish(version)

    with pytest.raises(DatabaseError, match="version_content_frozen"), transaction.atomic():
        section.delete()


def test_a_lesson_of_a_published_version_is_frozen(version: CourseVersion) -> None:
    section = Section.objects.create(
        organization_id=ORG, version=version, title="Intro", position=1
    )
    lesson = make_lesson(section)
    publish(version)

    with pytest.raises(DatabaseError, match="version_content_frozen"), transaction.atomic():
        Lesson.objects.filter(pk=lesson.pk).update(title="Renamed")
    with pytest.raises(DatabaseError, match="version_content_frozen"), transaction.atomic():
        make_lesson(section, title="Late", position=2)
    with pytest.raises(DatabaseError, match="version_content_frozen"), transaction.atomic():
        lesson.delete()


def test_draft_sections_and_lessons_remain_editable(version: CourseVersion) -> None:
    section = Section.objects.create(
        organization_id=ORG, version=version, title="Intro", position=1
    )
    lesson = make_lesson(section)

    Section.objects.filter(pk=section.pk).update(title="Renamed")
    make_lesson(section, title="Second", position=2)

    assert Lesson.objects.for_org(ORG).count() == 2
    assert Lesson.objects.get(pk=lesson.pk).title == "Lesson one"
