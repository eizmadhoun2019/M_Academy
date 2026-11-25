"""Publish validation — ``docs/api.md`` §8.

The validator returns every reason, not the first one, so an author can fix a version in one
editing pass. It never mutates anything; the publish service decides what the reasons forbid.
"""

from __future__ import annotations

from typing import Any

from academy.models import CourseVersion, Lesson, Section
from academy.models.media import MediaAsset

MIN_SECTIONS = 2
MIN_LESSONS = 2


def _next_position_ok(positions: list[int]) -> bool:
    return positions == list(range(1, len(positions) + 1))


def validate_for_publish(version: CourseVersion) -> list[dict[str, Any]]:
    """Every publish rule this version breaks, as ``{code, section_id?, lesson_id?}``."""
    reasons: list[dict[str, Any]] = []
    sections = list(Section.objects.for_org(version.organization_id).filter(version=version))
    sections.sort(key=lambda section: section.position)
    lessons = list(Lesson.objects.for_org(version.organization_id).filter(section__version=version))
    lessons.sort(key=lambda lesson: (lesson.section_id, lesson.position))

    if len(sections) < MIN_SECTIONS:
        reasons.append({"code": "too_few_sections"})
    if len(lessons) < MIN_LESSONS:
        reasons.append({"code": "too_few_lessons"})
    if not _next_position_ok([section.position for section in sections]):
        reasons.append({"code": "position_gap"})

    for section in sections:
        section_lessons = [lesson for lesson in lessons if lesson.section_id == section.pk]
        if not section_lessons:
            reasons.append({"code": "section_without_lessons", "section_id": str(section.pk)})
        if not _next_position_ok([lesson.position for lesson in section_lessons]):
            reasons.append({"code": "position_gap", "section_id": str(section.pk)})

    assets: dict[Any, MediaAsset] = {}
    for lesson in lessons:
        if not lesson.title.strip():
            reasons.append({"code": "lesson_without_title", "lesson_id": str(lesson.pk)})
        if lesson.content_type == Lesson.ContentType.TEXT:
            if not (lesson.body or "").strip():
                reasons.append({"code": "text_lesson_empty", "lesson_id": str(lesson.pk)})
            continue
        if lesson.media_asset_id is None:
            reasons.append({"code": "lesson_media_missing", "lesson_id": str(lesson.pk)})
            continue
        asset = assets.get(lesson.media_asset_id)
        if asset is None:
            asset = MediaAsset.objects.for_org(version.organization_id).get(
                pk=lesson.media_asset_id
            )
            assets[lesson.media_asset_id] = asset
        if asset.status != MediaAsset.Status.READY:
            reasons.append({"code": "lesson_media_not_ready", "lesson_id": str(lesson.pk)})

    if version.cover_media_id is not None:
        cover = (
            MediaAsset.objects.for_org(version.organization_id)
            .filter(pk=version.cover_media_id)
            .first()
        )
        if cover is None or cover.status != MediaAsset.Status.READY:
            reasons.append({"code": "cover_media_invalid"})

    return reasons
