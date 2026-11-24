"""Shared fixtures: two organizations and one small course graph.

The organization IDs are fixed so a failing isolation test always names the same tenants, and
every fixture builds through :mod:`factories` so a schema change is fixed in one place.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from factories import (
    make_course,
    make_enrollment,
    make_lesson,
    make_section,
    make_version,
)

from academy.models import Course, CourseVersion, Enrollment, Lesson, Section

ORG_ID = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
OTHER_ORG_ID = UUID("2f5e3d1a-0c4b-4a8e-9f2d-6b7c8d9e0f11")


@pytest.fixture
def org_id() -> UUID:
    return ORG_ID


@pytest.fixture
def other_org_id() -> UUID:
    return OTHER_ORG_ID


@pytest.fixture
def course(org_id: UUID) -> Course:
    return make_course(org_id)


@pytest.fixture
def version(org_id: UUID, course: Course) -> CourseVersion:
    return make_version(org_id, course=course)


@pytest.fixture
def section(org_id: UUID, version: CourseVersion) -> Section:
    return make_section(org_id, version=version)


@pytest.fixture
def lesson(org_id: UUID, section: Section) -> Lesson:
    return make_lesson(org_id, section=section)


@pytest.fixture
def enrollment(org_id: UUID, course: Course, version: CourseVersion) -> Enrollment:
    return make_enrollment(org_id, course=course, version=version)
