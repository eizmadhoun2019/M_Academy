"""Reminders and escalation — N-4…N-7 of ``docs/notifications.md`` §2, §7.8 rules.

The daily sweep is a pure function of the clock and the rows: it looks at every active
enrollment, decides which of the three anchored dates today is, and inserts the reminder row
before it calls the transport. ``ReminderLog``'s unique key ``(enrollment, kind, recipient)`` is
the gate, so a crash mid-run is safe — the next run sends only what is missing — and running the
task twice on the same day produces one message, not two.

Insertion and transport happen in one transaction on purpose: if the mail API fails the row
rolls back with it, so the fact recorded is always a message that really left. Escalation is
*not* suppressed by an acknowledgment (completion is), because acknowledging a due date does not
finish the course.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date, datetime
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from academy.adapters.notify import MailMessage
from academy.assignments.selectors import progress_percent
from academy.models import Enrollment, NotificationLog, ReminderLog
from academy.notifications import catalogue, service

logger = logging.getLogger("academy.notifications")

#: ``docs/notifications.md`` §2: the three anchored dates, in days from due.
OFFSETS: dict[int, str] = {
    -3: ReminderLog.Kind.DUE_MINUS_3,
    0: ReminderLog.Kind.DUE,
    1: ReminderLog.Kind.DUE_PLUS_1,
}

#: §7.8: the manager digest starts three days after the due date and repeats until completion.
ESCALATION_DAYS = 3


def escalation_key(manager_ref: str, due: date) -> str:
    """The digest's dedupe key: one per manager per due date, so a re-run sends nothing."""
    return f"escalation:{manager_ref}:{due.isoformat()}"


def candidates(organization_id: UUID | None = None) -> Iterable[Enrollment]:
    """Active, incomplete enrollments with a due date — the only ones with a clock."""
    rows = (
        Enrollment.objects.select_related("course", "assignment")
        .filter(
            status=Enrollment.Status.ACTIVE,
            completed_at__isnull=True,
            due_at__isnull=False,
        )
        .order_by("due_at", "pk")
    )
    if organization_id is not None:
        rows = rows.filter(organization_id=organization_id)
    return rows


def recipient_ready(organization_id: UUID, user_ref: str) -> bool:
    """Whether the Hub directory gives this learner an active address (§1)."""
    return service.recipient_ready(organization_id, user_ref)


def send_reminder(enrollment: Enrollment, kind: str, *, now: datetime | None = None) -> bool:
    """Send one learner reminder, or report that the row already existed.

    Returns ``False`` when the recipient has no usable address or the reminder was already
    recorded — both are "nothing to do", not failures.
    """
    organization_id = enrollment.organization_id
    if not recipient_ready(organization_id, enrollment.user_ref):
        return False
    lang = service.language()
    spec = catalogue.spec_for(kind)
    rendered = catalogue.render(
        kind,
        language=lang,
        organization_name=service.organization_name(),
        variables={
            "course_title": enrollment.course.title,
            "due_date": service.format_date(enrollment.due_at, lang),
            "progress": str(progress_percent(enrollment)),
        },
        url=service.absolute_url(spec.path),
    )
    message = MailMessage(
        kind=kind,
        recipient_ref=enrollment.user_ref,
        title=rendered.subject,
        body=rendered.text,
        idempotency_key=f"reminder:{kind}:{enrollment.pk}",
        url=spec.path,
        channels=(NotificationLog.Channel.EMAIL,),
        payload={
            "html": rendered.html,
            "text": rendered.text,
            "link": rendered.path,
            "message_key": rendered.key,
            "language": rendered.language,
            "direction": rendered.direction,
        },
    )
    with transaction.atomic():
        _, created = ReminderLog.objects.for_org(organization_id).get_or_create(
            organization_id=organization_id,
            enrollment=enrollment,
            kind=kind,
            recipient_ref=enrollment.user_ref,
            defaults={"sent_at": now or timezone.now()},
        )
        if not created:
            return False
        service.adapter().send_mail(organization_id, message)
    return True


def record_escalation(
    enrollment: Enrollment, manager_ref: str, *, now: datetime | None = None
) -> bool:
    """Record that this manager was escalated for this enrollment; ``False`` when it existed."""
    _, created = ReminderLog.objects.for_org(enrollment.organization_id).get_or_create(
        organization_id=enrollment.organization_id,
        enrollment=enrollment,
        kind=ReminderLog.Kind.MANAGER_ESCALATION,
        recipient_ref=manager_ref,
        defaults={"sent_at": now or timezone.now()},
    )
    return created


def evaluate(*, now: datetime | None = None, organization_id: UUID | None = None) -> dict[str, int]:
    """Run the daily sweep and return what it did, for the task log.

    One pass decides both halves: the three learner anchors (exact date, unacknowledged) and
    the escalation (``days >= 3``, self-healing so a missed day does not skip a learner).
    Digests are collected per ``(organization, manager, due date)`` and handed to the digest
    task, which owns the message itself.
    """
    now = now or timezone.now()
    today = service.local_date(now)
    counts = {"reminders": 0, "skipped": 0, "escalations": 0, "digests": 0}
    batches: dict[tuple[UUID, str, date], None] = {}
    for enrollment in candidates(organization_id):
        due = service.local_date(enrollment.due_at)  # type: ignore[arg-type]
        delta = (today - due).days
        kind = OFFSETS.get(delta)
        if kind is not None:
            if enrollment.acknowledged_at is not None:
                counts["skipped"] += 1
            elif send_reminder(enrollment, kind, now=now):
                counts["reminders"] += 1
            else:
                counts["skipped"] += 1
        if delta >= ESCALATION_DAYS:
            for manager_ref in service.managers_for(enrollment):
                if record_escalation(enrollment, manager_ref, now=now):
                    counts["escalations"] += 1
                batches[(enrollment.organization_id, manager_ref, due)] = None
    for batch_org, manager_ref, due in batches:
        from academy.notifications import tasks

        tasks.send_escalation_digest.delay(str(batch_org), manager_ref, due.isoformat())
        counts["digests"] += 1
    return counts


def pending_digests(*, now: datetime | None = None) -> list[tuple[UUID, str, date]]:
    """Every ``(organization, manager, due date)`` batch that is owed a digest and has none.

    This is what the bare beat run of ``academy.escalations.digest`` sends, so an escalation
    recorded by a run that stopped before queueing its digest is repaired on the same morning.
    """
    today = service.local_date(now or timezone.now())
    batches: dict[tuple[UUID, str, date], None] = {}
    records = ReminderLog.objects.filter(kind=ReminderLog.Kind.MANAGER_ESCALATION).select_related(
        "enrollment"
    )
    for record in records:
        enrollment = record.enrollment
        if enrollment.status != Enrollment.Status.ACTIVE or enrollment.due_at is None:
            continue
        due = service.local_date(enrollment.due_at)
        if (today - due).days < ESCALATION_DAYS:
            continue
        batches[(enrollment.organization_id, record.recipient_ref, due)] = None
    sent = {
        row.dedupe_key
        for row in NotificationLog.objects.filter(
            kind=NotificationLog.Kind.MANAGER_ESCALATION
        ).only("dedupe_key")
    }
    return [batch for batch in batches if escalation_key(batch[1], batch[2]) not in sent]


def send_digest(organization_id: UUID, manager_ref: str, due: date) -> str:
    """Queue and deliver N-7 for one manager and one due date; ``empty`` when nothing is due.

    The digest is built when it is sent, from the escalation rows that are still unpaid, so it
    never repeats a learner who finished between the sweep and the send.
    """
    rows = service.digest_rows(organization_id, manager_ref, due)
    if not rows:
        return "empty"
    key = escalation_key(manager_ref, due)
    created = service.queue(
        NotificationLog.Kind.MANAGER_ESCALATION,
        organization_id=organization_id,
        dedupe_key=key,
        recipient_ref=manager_ref,
    )
    for row in created:
        service.deliver(row)
    return "" if created else "duplicate"


__all__ = [
    "ESCALATION_DAYS",
    "OFFSETS",
    "candidates",
    "escalation_key",
    "evaluate",
    "pending_digests",
    "record_escalation",
    "recipient_ready",
    "send_digest",
    "send_reminder",
]
