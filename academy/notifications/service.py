"""Queueing and delivery — ``docs/notifications.md`` §1–§4.

A `NotificationLog` row is the durable half of a message: the unique key ``(organization,
dedupe_key, channel)`` means a second producer cannot queue it twice, and ``status='sent'``
means a second delivery attempt does not reach the transport again. Rows carry ids, never copy:
the words are rendered when the send runs, so a message that waits a few minutes in the queue
still names the course as it is, and the recipient's name and address are looked up in the Hub
directory at the same moment and never stored (ADR-012).

The dedupe key is the durable reference to the facts a message is about
(``docs/notifications.md`` §2), so a send resolves them again instead of trusting a snapshot:
``assigned:<assignment>:<user>``, ``completed:<enrollment>``,
``learner_completed:<enrollment>:<manager>`` and ``escalation:<manager>:<due-date>``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date, datetime
from functools import partial
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone, translation
from django.utils.formats import date_format

from academy.adapters.loader import load_adapter
from academy.adapters.notify import MailMessage
from academy.assignments.selectors import progress_percent
from academy.models import Enrollment, NotificationLog, ReminderLog
from academy.notifications import catalogue

logger = logging.getLogger("academy.notifications")

#: ``docs/background-jobs.md`` §1: a message is attempted three times in total.
MAX_ATTEMPTS = 3

SKIPPED_INACTIVE = "recipient_inactive"
SKIPPED_COMPLETED = "already_completed"
SKIPPED_CANCELLED = "enrollment_cancelled"
SKIPPED_UNKNOWN = "context_missing"
FAILED_TRANSPORT = "transport_failed"
DIRECTORY_UNAVAILABLE = "directory_unavailable"
MISSING = "missing"

#: ``docs/notifications.md`` §1: a learner reminder is suppressed by an acknowledgment, and a
#: completed or cancelled enrollment needs none at all.
ACTIVE = Enrollment.Status.ACTIVE
COMPLETED = Enrollment.Status.COMPLETED
CANCELLED = Enrollment.Status.CANCELLED

#: The actor an automatic expansion writes; it is not a person to notify.
SYSTEM_ACTOR = "system"


def adapter() -> Any:
    """The configured notification seam (tests replace this attribute)."""
    return load_adapter("notify")()


def directory() -> Any:
    """The configured organization seam (tests replace this attribute)."""
    return load_adapter("organization")()


def language() -> str:
    """The organization's default language; no per-user preference is stored (§1)."""
    code = str(getattr(settings, "LANGUAGE_CODE", "ar"))
    return code if code in catalogue.LANGUAGES else "ar"


def organization_name() -> str:
    """The organization display name the copy substitutes for `{org}` and the brand line."""
    return str(getattr(settings, "ACADEMY_ORGANIZATION_NAME", "") or "مشيد")


def business_timezone() -> ZoneInfo:
    """The zone reminders are anchored in (``ACADEMY_BUSINESS_TZ``, D-002)."""
    return ZoneInfo(str(getattr(settings, "ACADEMY_BUSINESS_TZ", "UTC")))


def local_date(moment: datetime) -> date:
    """The business-time-zone date of an instant, which is what a due date means."""
    return moment.astimezone(business_timezone()).date()


def format_date(moment: datetime | None, lang: str) -> str:
    """A date the recipient can read, in their language; an absent date is an em dash."""
    if moment is None:
        return "—"
    with translation.override(lang):
        return date_format(moment.astimezone(business_timezone()), "j F Y")


def absolute_url(path: str) -> str:
    """``{ACADEMY_HUB_ORIGIN}{ACADEMY_PROXY_PATH_PREFIX}`` + path (§1)."""
    origin = str(getattr(settings, "ACADEMY_HUB_ORIGIN", "") or "").rstrip("/")
    prefix = str(getattr(settings, "ACADEMY_PROXY_PATH_PREFIX", "/academy") or "").rstrip("/")
    return f"{origin}{prefix}{path}"


def recipient(organization_id: UUID, user_ref: str) -> Any | None:
    """The directory record of one recipient, or ``None`` when it cannot be delivered to."""
    users = directory().users(organization_id, [user_ref])
    return next((user for user in users if user.user_ref == user_ref), None)


def recipient_ready(organization_id: UUID, user_ref: str) -> bool:
    """Whether the Hub directory gives this recipient an active address (§1).

    A message is never sent to a placeholder: an unknown or deactivated member, or one without
    an email, is a skip rather than a send.
    """
    user = recipient(organization_id, user_ref)
    return user is not None and bool(user.is_active) and bool(user.email)


# --- queueing ---------------------------------------------------------------


def _enqueue(entries: Sequence[tuple[str, str]]) -> None:
    from academy.notifications import tasks

    for log_id, organization_id in entries:
        tasks.send_notification.delay(log_id, organization_id)


def queue(
    kind: str,
    *,
    organization_id: UUID,
    dedupe_key: str,
    recipient_ref: str,
    channels: Sequence[str] | None = None,
) -> list[NotificationLog]:
    """Insert one row per channel and schedule the send after the caller's commit.

    Returns the rows this call created; an existing row is never queued twice, which is what
    makes a repeated event or a replayed assignment harmless.
    """
    available = {choice.value for choice in NotificationLog.Kind}
    if kind not in available:
        raise ValueError(f"unknown notification kind {kind!r}; known: {sorted(available)}")
    spec = catalogue.spec_for(kind)
    created: list[NotificationLog] = []
    for channel in channels or spec.channels:
        row, was_created = NotificationLog.objects.for_org(organization_id).get_or_create(
            organization_id=organization_id,
            dedupe_key=dedupe_key,
            channel=channel,
            defaults={"kind": kind, "recipient_ref": recipient_ref},
        )
        if was_created:
            created.append(row)
    if created:
        transaction.on_commit(
            partial(
                _enqueue,
                [(str(row.pk), str(organization_id)) for row in created],
            )
        )
    return created


# --- rendering --------------------------------------------------------------


def _enrollment(organization_id: UUID, value: Any) -> Enrollment | None:
    try:
        key = UUID(str(value))
    except (TypeError, ValueError):
        return None
    return (
        Enrollment.objects.for_org(organization_id)
        .select_related("course", "course_version", "assignment")
        .filter(pk=key)
        .first()
    )


def enrollment(organization_id: UUID, value: Any) -> Enrollment | None:
    """One enrollment by id, or ``None`` for a missing or malformed reference."""
    return _enrollment(organization_id, value)


def managers_for(enrollment: Enrollment) -> tuple[str, ...]:
    """Who hears about this learner (§2): the human assigner, else the Hub manager.

    ``system`` is the actor of an automatic expansion, not a person to notify, so an
    organization- or role-wide assignment falls back to the learner's own manager.
    """
    refs: list[str] = []
    assignment = enrollment.assignment
    actor = assignment.assigned_by_ref if assignment is not None else None
    if actor and actor != SYSTEM_ACTOR:
        refs.append(actor)
    else:
        manager = directory().manager_of(enrollment.organization_id, enrollment.user_ref)
        if manager:
            refs.append(manager)
    return tuple(ref for ref in dict.fromkeys(refs) if ref and ref != enrollment.user_ref)


def _enrollment_for(organization_id: UUID, assignment_id: Any, user_ref: str) -> Enrollment | None:
    try:
        key = UUID(str(assignment_id))
    except (TypeError, ValueError):
        return None
    return (
        Enrollment.objects.for_org(organization_id)
        .select_related("course", "course_version", "assignment")
        .filter(assignment_id=key, user_ref=user_ref)
        .order_by("-created_at")
        .first()
    )


def _parts(dedupe_key: str) -> tuple[str, str]:
    """Split ``prefix:first:rest`` into the first two segments (the rest may hold colons)."""
    _, _, rest = dedupe_key.partition(":")
    head, _, tail = rest.partition(":")
    return head, tail


def escalation_context(dedupe_key: str) -> tuple[str, date] | None:
    """``escalation:<manager>:<due-date>`` → its two facts, or ``None`` when malformed."""
    manager_ref, due_value = _parts(dedupe_key)
    if not manager_ref or not due_value:
        return None
    try:
        return manager_ref, date.fromisoformat(due_value)
    except ValueError:
        return None


def digest_rows(organization_id: UUID, manager_ref: str, due: date) -> list[catalogue.DigestRow]:
    """The overdue learners of one manager for one due date, as the artifact's rows."""
    records = list(
        ReminderLog.objects.for_org(organization_id)
        .filter(kind=ReminderLog.Kind.MANAGER_ESCALATION, recipient_ref=manager_ref)
        .select_related("enrollment__course", "enrollment__assignment")
    )
    lang = language()
    today = local_date(timezone.now())
    selected: list[tuple[ReminderLog, catalogue.DigestRow]] = []
    for record in records:
        enrollment = record.enrollment
        if enrollment.status != ACTIVE or enrollment.completed_at is not None:
            continue
        if enrollment.due_at is None or local_date(enrollment.due_at) != due:
            continue
        selected.append(
            (
                record,
                catalogue.DigestRow(
                    employee="",
                    course=enrollment.course.title,
                    due=format_date(enrollment.due_at, lang),
                    days=max(0, (today - due).days),
                    progress=f"{progress_percent(enrollment)}%",
                ),
            )
        )
    if not selected:
        return []
    names = _names(organization_id, [record.enrollment.user_ref for record, _ in selected])
    return [
        replace(row, employee=names.get(record.enrollment.user_ref, record.enrollment.user_ref))
        for record, row in selected
    ]


def _names(organization_id: UUID, user_refs: Sequence[str]) -> dict[str, str]:
    """Display names for the digest; the directory is read here and nothing is stored."""
    wanted = list(dict.fromkeys(user_refs))
    if not wanted:
        return {}
    return {user.user_ref: user.display_name for user in directory().users(organization_id, wanted)}


def _message(
    row: NotificationLog,
    *,
    key: str,
    recipient_ref: str,
    variables: Mapping[str, str],
    url: str | None = None,
) -> MailMessage:
    spec = catalogue.spec_for(key)
    link = absolute_url(url or spec.path)
    rendered = catalogue.render(
        key,
        language=language(),
        organization_name=organization_name(),
        variables=variables,
        url=link,
    )
    return MailMessage(
        kind=row.kind,
        recipient_ref=recipient_ref,
        title=rendered.subject,
        body=rendered.text,
        idempotency_key=row.dedupe_key,
        url=spec.path,
        channels=(row.channel,),
        payload={
            "html": rendered.html,
            "text": rendered.text,
            "link": link,
            "message_key": rendered.key,
            "language": rendered.language,
            "direction": rendered.direction,
        },
    )


def message_for(row: NotificationLog) -> tuple[MailMessage | None, str]:
    """The message this row delivers, or the reason it must be skipped (§1)."""
    kind = row.kind
    organization_id = row.organization_id
    if kind == NotificationLog.Kind.COURSE_ASSIGNED:
        assignment_id, user_ref = _parts(row.dedupe_key)
        enrollment = _enrollment_for(organization_id, assignment_id, user_ref)
        if enrollment is None:
            return None, SKIPPED_UNKNOWN
        if enrollment.status == CANCELLED:
            return None, SKIPPED_CANCELLED
        if enrollment.status == COMPLETED:
            return None, SKIPPED_COMPLETED
        return (
            _message(
                row,
                key="course_assigned",
                recipient_ref=enrollment.user_ref,
                variables={
                    "course_title": enrollment.course.title,
                    "due_date": format_date(enrollment.due_at, language()),
                    "org": organization_name(),
                },
            ),
            "",
        )
    if kind == NotificationLog.Kind.COURSE_COMPLETED:
        enrollment_id, _ = _parts(row.dedupe_key)
        enrollment = _enrollment(organization_id, enrollment_id)
        if enrollment is None:
            return None, SKIPPED_UNKNOWN
        return (
            _message(
                row,
                key="course_completed",
                recipient_ref=enrollment.user_ref,
                variables={"course_title": enrollment.course.title},
            ),
            "",
        )
    if kind == NotificationLog.Kind.LEARNER_COMPLETED:
        enrollment_id, manager_ref = _parts(row.dedupe_key)
        enrollment = _enrollment(organization_id, enrollment_id)
        if enrollment is None or not manager_ref:
            return None, SKIPPED_UNKNOWN
        learner = _names(organization_id, [enrollment.user_ref])
        return (
            _message(
                row,
                key="learner_completed",
                recipient_ref=manager_ref,
                variables={
                    "learner_name": learner.get(enrollment.user_ref, enrollment.user_ref),
                    "course_title": enrollment.course.title,
                    "completed_date": format_date(enrollment.completed_at, language()),
                },
            ),
            "",
        )
    context = escalation_context(row.dedupe_key)
    if context is None:
        return None, SKIPPED_UNKNOWN
    manager_ref, due = context
    rows = digest_rows(organization_id, manager_ref, due)
    if not rows:
        return None, SKIPPED_UNKNOWN
    rendered = catalogue.render_digest(
        language=language(),
        organization_name=organization_name(),
        rows=rows,
        url=absolute_url(catalogue.spec_for("manager_escalation").path),
    )
    return (
        MailMessage(
            kind=row.kind,
            recipient_ref=manager_ref,
            title=rendered.subject,
            body=rendered.text,
            idempotency_key=row.dedupe_key,
            url=catalogue.spec_for("manager_escalation").path,
            channels=(row.channel,),
            payload={
                "html": rendered.html,
                "text": rendered.text,
                "message_key": rendered.key,
                "language": rendered.language,
                "direction": rendered.direction,
            },
        ),
        "",
    )


# --- delivery ---------------------------------------------------------------


def _update(row: NotificationLog, **values: Any) -> None:
    NotificationLog.objects.for_org(row.organization_id).filter(pk=row.pk).update(**values)


def _mark_sent(row: NotificationLog) -> None:
    _update(row, status=NotificationLog.Status.SENT, sent_at=timezone.now(), error_code=None)


def deliver_by_id(log_id: UUID, organization_id: UUID) -> str:
    """Deliver one queued row; ``missing`` when another process already pruned it."""
    row = NotificationLog.objects.for_org(organization_id).filter(pk=log_id).first()
    if row is None:
        return MISSING
    return deliver(row)


def deliver(row: NotificationLog) -> str:
    """Deliver one row and record the outcome (§3).

    A directory outage leaves the row ``pending`` with its attempt counted, so the sweeper
    retries instead of the message leaving without a real address; a transport failure marks it
    ``failed`` with a stable code. Both re-raise so Celery's own retry sees the failure.
    """
    if row.status == NotificationLog.Status.SENT:
        return NotificationLog.Status.SENT
    if row.channel == NotificationLog.Channel.IN_APP:
        # In-app rows are rendered from the table itself, so there is nothing to transport and
        # no address to resolve; unread state is the client's view of `sent`.
        _mark_sent(row)
        return NotificationLog.Status.SENT
    try:
        message, skipped = message_for(row)
        if message is not None and not recipient_ready(row.organization_id, message.recipient_ref):
            message, skipped = None, SKIPPED_INACTIVE
    except Exception:
        _update(row, attempt_count=F("attempt_count") + 1, error_code=DIRECTORY_UNAVAILABLE)
        raise
    if message is None:
        _update(row, status=NotificationLog.Status.SKIPPED, error_code=skipped)
        return NotificationLog.Status.SKIPPED
    try:
        adapter().send_mail(row.organization_id, message)
    except Exception:
        _update(
            row,
            status=NotificationLog.Status.FAILED,
            attempt_count=F("attempt_count") + 1,
            error_code=FAILED_TRANSPORT,
        )
        raise
    _mark_sent(row)
    return NotificationLog.Status.SENT


def pending(organization_id: UUID | None = None) -> Sequence[NotificationLog]:
    """Rows the sweeper may retry: pending or failed, under the attempt cap (§1)."""
    rows = NotificationLog.objects.filter(
        status__in=[NotificationLog.Status.PENDING, NotificationLog.Status.FAILED],
        attempt_count__lt=MAX_ATTEMPTS,
    ).order_by("created_at")
    if organization_id is not None:
        rows = rows.filter(organization_id=organization_id)
    return list(rows)


__all__ = [
    "DIRECTORY_UNAVAILABLE",
    "FAILED_TRANSPORT",
    "MAX_ATTEMPTS",
    "MISSING",
    "SKIPPED_CANCELLED",
    "SKIPPED_COMPLETED",
    "SKIPPED_INACTIVE",
    "SKIPPED_UNKNOWN",
    "SYSTEM_ACTOR",
    "absolute_url",
    "adapter",
    "business_timezone",
    "deliver",
    "deliver_by_id",
    "digest_rows",
    "directory",
    "enrollment",
    "escalation_context",
    "format_date",
    "language",
    "local_date",
    "managers_for",
    "message_for",
    "organization_name",
    "pending",
    "queue",
    "recipient",
    "recipient_ready",
]
