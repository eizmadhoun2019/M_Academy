"""Progress, anti-skip and completion — ``docs/domain-model.md`` §7 (REQ-09).

The constants of §7.1 are module-level here, deliberately outside the settings modules, so a
test can patch one clock window and exercise the algorithm without a deployment change.

The server owns every number: a heartbeat names an interval and a playback rate, nothing else.
The credit window comes from the wall clock between two heartbeats, the rate is clamped, and the
covered ranges are merged on the server before anything is stored — the client can only earn
coverage by staying connected (ADR-013, §7.9).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from academy.assignments import gating, selectors
from academy.audit import record as audit_record
from academy.authorization.core import Access, Capability
from academy.events.signals import emit_on_commit
from academy.exceptions import (
    AcknowledgmentNotRequired,
    DomainValidationError,
    EnrollmentIncomplete,
    Forbidden,
    LessonNotEligible,
    NotFound,
    ProgressSkipRejected,
    StateConflict,
)
from academy.models import CompletionRecord, Enrollment, Lesson, LessonProgress

# --- §7.1 constants ---------------------------------------------------------

HEARTBEAT_INTERVAL_SECONDS = 15
MAX_HEARTBEAT_GAP_SECONDS = 60
MAX_PLAYBACK_RATE = 2.0
MIN_PLAYBACK_RATE = 0.5
SKIP_TOLERANCE_SECONDS = 2.0
RANGE_MERGE_GAP_SECONDS = 0.5
RANGE_PRECISION = 0.1
DEFAULT_COMPLETE_PERCENT = 90

#: Decimal places implied by ``RANGE_PRECISION`` (0.1 → 1), never a second literal.
_DIGITS = len(str(RANGE_PRECISION).split(".")[1]) if "." in str(RANGE_PRECISION) else 0


# --- range arithmetic (§7.3 steps 7–8) --------------------------------------


def _round_seconds(value: float) -> float:
    return round(value, _DIGITS)


def merge_ranges(
    ranges: Iterable[Sequence[float]], *, limit: float | None = None
) -> list[list[float]]:
    """Sort, clamp and merge watched ranges into the ascending disjoint form of §2.8."""
    cleaned: list[tuple[float, float]] = []
    for start, end in ranges:
        start_value = max(0.0, float(start))
        end_value = max(0.0, float(end))
        if limit is not None:
            start_value = min(start_value, max(limit, 0.0))
            end_value = min(end_value, max(limit, 0.0))
        if end_value > start_value:
            cleaned.append((start_value, end_value))
    cleaned.sort()
    merged: list[list[float]] = []
    for start_value, end_value in cleaned:
        if merged and start_value - merged[-1][1] <= RANGE_MERGE_GAP_SECONDS:
            merged[-1][1] = max(merged[-1][1], end_value)
        else:
            merged.append([start_value, end_value])
    return [[_round_seconds(start), _round_seconds(end)] for start, end in merged]


def watched_total(ranges: Sequence[Sequence[float]]) -> float:
    """Exact sum of the merged ranges — the value cached in ``watched_seconds``."""
    return _round_seconds(sum(float(end) - float(start) for start, end in ranges))


def frontier_for(ranges: Sequence[Sequence[float]]) -> float:
    """End of the contiguous run that starts at 0; a later gap stops the run (§7.3 step 8)."""
    if not ranges:
        return 0.0
    if float(ranges[0][0]) > RANGE_MERGE_GAP_SECONDS:
        return 0.0
    frontier = float(ranges[0][1])
    for start, end in ranges[1:]:
        if float(start) - frontier > RANGE_MERGE_GAP_SECONDS:
            break
        frontier = max(frontier, float(end))
    return _round_seconds(frontier)


def coverage_percent(watched: float, duration: float) -> float:
    """``watched_seconds / duration_seconds × 100``; 0 when the lesson has no duration."""
    if duration <= 0:
        return 0.0
    return min(100.0, round(watched * 100.0 / duration, _DIGITS))


# --- lookups ----------------------------------------------------------------


def lesson_duration(lesson: Lesson) -> float:
    """Duration of the lesson's own rendition; text and PDF lessons report 0."""
    asset = lesson.media_asset
    if asset is None or asset.duration_seconds is None:
        return 0.0
    return float(asset.duration_seconds)


def _require_learner_enrollment(access: Access, enrollment_id: UUID) -> Enrollment:
    """The caller's own, still-usable enrollment; a cancelled one is not visible to writers."""
    enrollment = selectors.require_own_enrollment(access, enrollment_id)
    if enrollment.status == Enrollment.Status.CANCELLED:
        raise NotFound("enrollment not found")
    return enrollment


def _require_lesson(enrollment: Enrollment, lesson_id: UUID) -> Lesson:
    lesson = (
        Lesson.objects.for_org(enrollment.organization_id)
        .select_related("media_asset")
        .filter(pk=lesson_id)
        .first()
    )
    if lesson is None:
        raise NotFound("lesson not found")
    return lesson


def _progress_row(
    enrollment: Enrollment, lesson: Lesson, *, lock: bool = True
) -> LessonProgress | None:
    rows = LessonProgress.objects.for_org(enrollment.organization_id).filter(
        enrollment=enrollment, lesson=lesson
    )
    return (rows.select_for_update() if lock else rows).first()


# --- heartbeat (§7.2–§7.4) --------------------------------------------------


def record_heartbeat(
    access: Access,
    enrollment_id: UUID,
    lesson_id: UUID,
    *,
    from_seconds: float,
    to_seconds: float,
    playback_rate: float = 1.0,
) -> dict[str, float]:
    """Accept one playback interval, credit what the wall clock allows and return the state."""
    enrollment = _require_learner_enrollment(access, enrollment_id)
    lesson = _require_lesson(enrollment, lesson_id)
    # §7.5: a locked lesson never records progress, so the lock is not a UI-only affordance.
    gating.require_accessible(enrollment, lesson)
    organization_id = enrollment.organization_id

    with transaction.atomic():
        row = _progress_row(enrollment, lesson)
        if row is None:
            row = LessonProgress.objects.create(
                organization_id=organization_id, enrollment=enrollment, lesson=lesson
            )
        now = timezone.now()
        position = float(row.position_seconds)
        elapsed = (now - row.last_heartbeat_at).total_seconds() if row.last_heartbeat_at else 0.0
        credit_window = min(max(elapsed, 0.0), MAX_HEARTBEAT_GAP_SECONDS)
        rate = min(max(float(playback_rate), MIN_PLAYBACK_RATE), MAX_PLAYBACK_RATE)
        ceiling = position + credit_window * rate + SKIP_TOLERANCE_SECONDS

        duration = lesson_duration(lesson)
        limit = duration if duration > 0 else None
        rejected: float | None = None
        if float(to_seconds) > ceiling:
            # REQ-09: a forward jump is refused before it can become coverage, and only the abuse
            # metric changes. The clock is not reset, so a retry that waits long enough is
            # credited correctly; the increment is committed because the refusal is the fact
            # worth counting (§7.3 step 5, §9 abuse metric).
            row.skip_attempts += 1
            row.save(update_fields=["skip_attempts", "updated_at"])
            rejected = ceiling
        else:
            ranges = merge_ranges(row.watched_ranges or [], limit=limit)
            # Rewinding credits nothing; ``position_seconds`` keeps the high-water mark because
            # ``frontier_seconds <= position_seconds`` is a database check (§2.8), so the
            # position can never fall behind the coverage the learner already earned.
            position_after = max(position, float(to_seconds))
            if position_after > position and float(playback_rate) >= MIN_PLAYBACK_RATE:
                start = max(float(from_seconds), position)
                credited = max(0.0, min(position_after - start, credit_window * rate))
                if credited > 0:
                    ranges = merge_ranges([*ranges, [start, start + credited]], limit=limit)

            row.watched_ranges = ranges
            row.watched_seconds = Decimal(str(watched_total(ranges)))
            row.position_seconds = Decimal(str(_round_seconds(position_after)))
            row.frontier_seconds = Decimal(str(min(frontier_for(ranges), position_after)))
            row.last_heartbeat_at = now
            row.save(
                update_fields=[
                    "watched_ranges",
                    "watched_seconds",
                    "position_seconds",
                    "frontier_seconds",
                    "last_heartbeat_at",
                    "updated_at",
                ]
            )
            watched = float(row.watched_seconds)
            frontier = float(row.frontier_seconds)

    if rejected is not None:
        # Raised outside the atomic block so the skip counter survives the failed request.
        raise ProgressSkipRejected(rejected)

    return {
        "position_seconds": _round_seconds(position_after),
        "watched_seconds": watched,
        "frontier_seconds": frontier,
        "coverage_percent": coverage_percent(watched, duration),
        "skippable_seconds": _round_seconds(ceiling),
    }


# --- lesson completion (§7.6) ----------------------------------------------


def _lesson_payload(
    lesson: Lesson, *, completed_at: datetime | None, watched: float, duration: float, required: int
) -> dict[str, Any]:
    return {
        "lesson_id": str(lesson.pk),
        "completed_at": completed_at.isoformat() if completed_at else None,
        "coverage_percent": coverage_percent(watched, duration),
        "required_percent": required,
    }


def complete_lesson(access: Access, enrollment_id: UUID, lesson_id: UUID) -> dict[str, Any]:
    """Mark one lesson complete once its coverage reaches the lesson's threshold."""
    enrollment = _require_learner_enrollment(access, enrollment_id)
    lesson = _require_lesson(enrollment, lesson_id)
    gating.require_accessible(enrollment, lesson)
    organization_id = enrollment.organization_id
    duration = lesson_duration(lesson)
    required = lesson.required_watch_percent or DEFAULT_COMPLETE_PERCENT

    with transaction.atomic():
        row = _progress_row(enrollment, lesson)
        if row is not None and row.completed_at is not None:
            # §7.6 idempotency: the same completion comes back instead of a second one.
            return _lesson_payload(
                lesson,
                completed_at=row.completed_at,
                watched=float(row.watched_seconds),
                duration=duration,
                required=required,
            )
        watched = float(row.watched_seconds) if row is not None else 0.0
        coverage = coverage_percent(watched, duration)
        if duration > 0 and coverage < required:
            raise LessonNotEligible(coverage, required)
        now = timezone.now()
        if row is None:
            row = LessonProgress.objects.create(
                organization_id=organization_id,
                enrollment=enrollment,
                lesson=lesson,
                completed_at=now,
            )
        else:
            row.completed_at = now
            row.save(update_fields=["completed_at", "updated_at"])
        emit_on_commit(
            "lesson.completed",
            organization_id=organization_id,
            actor_ref=access.principal.user_ref,
            payload={
                "enrollment_id": str(enrollment.pk),
                "lesson_id": str(lesson.pk),
                "course_id": str(enrollment.course_id),
                "course_version_id": str(enrollment.course_version_id),
                "user_ref": enrollment.user_ref,
            },
        )
    return _lesson_payload(
        lesson, completed_at=now, watched=watched, duration=duration, required=required
    )


# --- acknowledgement (§7.7) -------------------------------------------------


def acknowledge(access: Access, enrollment_id: UUID) -> dict[str, Any]:
    """Record the learner's acknowledgment of the pinned version's content."""
    enrollment = _require_learner_enrollment(access, enrollment_id)
    if not enrollment.course_version.acknowledgment_required:
        raise AcknowledgmentNotRequired("this course version requires no acknowledgment")
    if enrollment.acknowledged_at is None:
        with transaction.atomic():
            row = (
                Enrollment.objects.for_org(enrollment.organization_id)
                .select_for_update()
                .filter(pk=enrollment.pk)
                .first()
            )
            if row is not None and row.acknowledged_at is None:
                row.acknowledged_at = timezone.now()
                row.save(update_fields=["acknowledged_at", "updated_at"])
                enrollment = row
    stamp = enrollment.acknowledged_at
    return {
        "enrollment_id": str(enrollment.pk),
        "acknowledged": stamp is not None,
        "acknowledged_at": stamp.isoformat() if stamp else None,
    }


# --- completion (§7.7) ------------------------------------------------------


def _completion_payload(
    enrollment: Enrollment, *, completed_at: datetime | None, method: str
) -> dict[str, Any]:
    return {
        "enrollment_id": str(enrollment.pk),
        "status": enrollment.status,
        "completed_at": completed_at.isoformat() if completed_at else None,
        "method": method,
        "progress_percent": selectors.progress_percent(enrollment),
    }


def _existing_completion(enrollment: Enrollment) -> dict[str, Any]:
    record = (
        CompletionRecord.objects.for_org(enrollment.organization_id)
        .filter(enrollment=enrollment)
        .first()
    )
    return _completion_payload(
        enrollment,
        completed_at=record.completed_at if record else enrollment.completed_at,
        method=record.method if record else CompletionRecord.Method.LESSONS,
    )


def complete_enrollment(access: Access, enrollment_id: UUID) -> dict[str, Any]:
    """Complete the enrollment when every required lesson is done and acknowledgment is in."""
    enrollment = _require_learner_enrollment(access, enrollment_id)
    organization_id = enrollment.organization_id
    actor_ref = access.principal.user_ref

    with transaction.atomic():
        row = (
            Enrollment.objects.for_org(organization_id)
            .select_for_update()
            .select_related("course_version")
            .filter(pk=enrollment.pk)
            .first()
        )
        if row is None:
            raise NotFound("enrollment not found")
        if row.status == Enrollment.Status.COMPLETED:
            return _existing_completion(row)

        ordered = gating.ordered_lessons(row)
        completed = gating.completed_lesson_ids(row)
        blocking = [
            lesson.pk for lesson in ordered if lesson.required and lesson.pk not in completed
        ]
        if blocking:
            raise EnrollmentIncomplete([str(lesson_id) for lesson_id in blocking])
        if row.course_version.acknowledgment_required and row.acknowledged_at is None:
            raise EnrollmentIncomplete([], acknowledgment_required=True)

        now = timezone.now()
        row.status = Enrollment.Status.COMPLETED
        row.completed_at = now
        row.save(update_fields=["status", "completed_at", "updated_at"])
        CompletionRecord.objects.create(
            organization_id=organization_id,
            enrollment=row,
            course_id=row.course_id,
            course_version_id=row.course_version_id,
            user_ref=row.user_ref,
            completed_at=now,
            method=CompletionRecord.Method.LESSONS,
            actor_ref=actor_ref,
        )
        emit_on_commit(
            "enrollment.completed",
            organization_id=organization_id,
            actor_ref=actor_ref,
            payload={
                "enrollment_id": str(row.pk),
                "course_id": str(row.course_id),
                "course_version_id": str(row.course_version_id),
                "user_ref": row.user_ref,
                "method": CompletionRecord.Method.LESSONS,
            },
        )
    return _completion_payload(row, completed_at=now, method=CompletionRecord.Method.LESSONS)


def override_complete_enrollment(
    access: Access, enrollment_id: UUID, *, reason: str
) -> dict[str, Any]:
    """``academy.admin`` override completion (``method='admin_override'``), audited."""
    if not access.granted(Capability.ADMIN):
        raise Forbidden("academy.admin is required to complete an enrollment")
    if not reason or not reason.strip():
        raise DomainValidationError("a reason is required", fields={"reason": "required"})
    organization_id = access.principal.organization_id
    actor_ref = access.principal.user_ref

    with transaction.atomic():
        row = (
            Enrollment.objects.for_org(organization_id)
            .select_for_update()
            .select_related("course_version")
            .filter(pk=enrollment_id)
            .first()
        )
        if row is None:
            raise NotFound("enrollment not found")
        if row.status == Enrollment.Status.COMPLETED:
            return _existing_completion(row)
        if row.status == Enrollment.Status.CANCELLED:
            raise StateConflict("conflict", "a cancelled enrollment cannot be completed")

        now = timezone.now()
        row.status = Enrollment.Status.COMPLETED
        row.completed_at = now
        row.save(update_fields=["status", "completed_at", "updated_at"])
        CompletionRecord.objects.create(
            organization_id=organization_id,
            enrollment=row,
            course_id=row.course_id,
            course_version_id=row.course_version_id,
            user_ref=row.user_ref,
            completed_at=now,
            method=CompletionRecord.Method.ADMIN_OVERRIDE,
            actor_ref=actor_ref,
        )
        # The reason is validated at the edge but never stored: audit metadata carries ids only
        # (§2.13), and a 5-year append-only table is no place for free text.
        audit_record(
            organization_id=organization_id,
            actor_ref=actor_ref,
            action="enrollment.completed_override",
            object_type="Enrollment",
            object_id=str(row.pk),
            metadata={
                "course_id": str(row.course_id),
                "course_version_id": str(row.course_version_id),
                "method": CompletionRecord.Method.ADMIN_OVERRIDE,
            },
        )
        emit_on_commit(
            "enrollment.completed",
            organization_id=organization_id,
            actor_ref=actor_ref,
            payload={
                "enrollment_id": str(row.pk),
                "course_id": str(row.course_id),
                "course_version_id": str(row.course_version_id),
                "user_ref": row.user_ref,
                "method": CompletionRecord.Method.ADMIN_OVERRIDE,
            },
        )
    return _completion_payload(row, completed_at=now, method=CompletionRecord.Method.ADMIN_OVERRIDE)


__all__ = [
    "DEFAULT_COMPLETE_PERCENT",
    "HEARTBEAT_INTERVAL_SECONDS",
    "MAX_HEARTBEAT_GAP_SECONDS",
    "MAX_PLAYBACK_RATE",
    "MIN_PLAYBACK_RATE",
    "RANGE_MERGE_GAP_SECONDS",
    "RANGE_PRECISION",
    "SKIP_TOLERANCE_SECONDS",
    "acknowledge",
    "complete_enrollment",
    "complete_lesson",
    "coverage_percent",
    "frontier_for",
    "lesson_duration",
    "merge_ranges",
    "override_complete_enrollment",
    "record_heartbeat",
    "watched_total",
]
