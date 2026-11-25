"""Sequential gating — ``docs/domain-model.md`` §7.5, the rule behind ``lesson_locked``.

Reading order is ``section.position`` then ``lesson.position`` inside the version the
enrollment is pinned to. A required lesson is locked while any required lesson earlier in that
order is incomplete; a non-required lesson can be opened at any time and does not gate later
ones (§7.5 rule 3). The outline and the playback path both ask this module, so the lock is
never a UI-only affordance.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any
from uuid import UUID

from academy.exceptions import LessonLocked, NotFound
from academy.models import Enrollment, Lesson, LessonProgress, Section


def ordered_lessons(enrollment: Enrollment) -> list[Lesson]:
    """Every lesson of the enrolled version, in reading order."""
    version = enrollment.course_version
    sections: Sequence[Section] = sorted(
        Section.objects.for_org(enrollment.organization_id).filter(version=version),
        key=lambda row: row.position,
    )
    lessons = Lesson.objects.for_org(enrollment.organization_id).filter(section__version=version)
    by_section: dict[UUID, list[Lesson]] = {}
    for lesson in lessons:
        by_section.setdefault(lesson.section_id, []).append(lesson)
    ordered: list[Lesson] = []
    for section in sections:
        ordered.extend(sorted(by_section.get(section.pk, []), key=lambda row: row.position))
    return ordered


def completed_lesson_ids(enrollment: Enrollment) -> set[UUID]:
    """Lessons of this enrollment that carry a completion timestamp."""
    rows = LessonProgress.objects.for_org(enrollment.organization_id).filter(
        enrollment=enrollment, completed_at__isnull=False
    )
    return {row.lesson_id for row in rows}


def blocking_lesson(lesson_ids: Iterable[UUID], completed: set[UUID]) -> UUID | None:
    """The first *required* lesson in the chain that is still incomplete, if any.

    ``lesson_ids`` must already be the required lessons of the version in reading order and
    end at the lesson being opened.
    """
    for lesson_id in lesson_ids:
        if lesson_id not in completed:
            return lesson_id
    return None


def state_for(ordered: Sequence[Lesson], completed: set[UUID]) -> dict[UUID, tuple[bool, bool]]:
    """``lesson_id → (locked, completed)`` for one enrollment; one pass over the chain."""
    states: dict[UUID, tuple[bool, bool]] = {}
    earlier_required_incomplete = False
    for lesson in ordered:
        states[lesson.pk] = (
            earlier_required_incomplete and lesson.required,
            lesson.pk in completed,
        )
        if lesson.required and lesson.pk not in completed:
            earlier_required_incomplete = True
    return states


def require_accessible(enrollment: Enrollment, lesson: Lesson) -> None:
    """Raise ``lesson_locked`` with ``next_lesson_id`` when the lesson may not be opened yet."""
    ordered = ordered_lessons(enrollment)
    position = next((index for index, row in enumerate(ordered) if row.pk == lesson.pk), None)
    if position is None:
        raise NotFound("lesson not found")
    completed = completed_lesson_ids(enrollment)
    if not lesson.required:
        return
    blocker = blocking_lesson((row.pk for row in ordered[:position] if row.required), completed)
    if blocker is not None:
        raise LessonLocked(blocker, "the previous required lesson is not complete")


def progress_percent(ordered: Sequence[Lesson], completed: set[UUID]) -> int:
    """Share of the *required* lessons that are complete (0 when there are none)."""
    required = [lesson for lesson in ordered if lesson.required]
    if not required:
        return 0
    done = sum(1 for lesson in required if lesson.pk in completed)
    return round(done * 100 / len(required))


def outline(enrollment: Enrollment) -> list[dict[str, Any]]:
    """Sections and lessons with ``locked`` / ``completed`` for the learner-facing detail."""
    ordered = ordered_lessons(enrollment)
    completed = completed_lesson_ids(enrollment)
    states = state_for(ordered, completed)
    version = enrollment.course_version
    sections: Sequence[Section] = sorted(
        Section.objects.for_org(enrollment.organization_id).filter(version=version),
        key=lambda row: row.position,
    )
    by_section: dict[UUID, list[Lesson]] = {}
    for lesson in ordered:
        by_section.setdefault(lesson.section_id, []).append(lesson)
    payload: list[dict[str, Any]] = []
    for section in sections:
        payload.append(
            {
                "id": str(section.pk),
                "title": section.title,
                "position": section.position,
                "lessons": [
                    {
                        "id": str(lesson.pk),
                        "title": lesson.title,
                        "summary": lesson.summary,
                        "position": lesson.position,
                        "content_type": lesson.content_type,
                        "required": lesson.required,
                        "required_watch_percent": lesson.required_watch_percent,
                        "media_asset_id": (
                            str(lesson.media_asset_id) if lesson.media_asset_id else None
                        ),
                        "locked": states[lesson.pk][0],
                        "completed": states[lesson.pk][1],
                    }
                    for lesson in sorted(
                        by_section.get(section.pk, []), key=lambda row: row.position
                    )
                ],
            }
        )
    return payload


__all__ = [
    "blocking_lesson",
    "completed_lesson_ids",
    "ordered_lessons",
    "outline",
    "progress_percent",
    "require_accessible",
    "state_for",
]
