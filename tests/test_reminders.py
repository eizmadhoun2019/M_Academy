"""T-021 acceptance: reminder anchors and the manager digest (``docs/notifications.md`` §5).

The evaluator takes the clock it is given, so the matrix of ``docs/background-jobs.md`` §5 is
written as due dates around today rather than as a wait: −5, −3, −1, 0, +1, +3 and +5 days
produce exactly the three anchored learner reminders, the escalation from +3 onwards, and
nothing else. Every send is asserted through the recording transport.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID

import pytest
from django.utils import timezone
from factories import make_assignment, make_course, make_enrollment, make_reminder, make_version

from academy.adapters.organization import DirectoryUser
from academy.events import clear_handlers
from academy.models import Enrollment, NotificationLog, ReminderLog
from academy.notifications import handlers, reminders, service, tasks
from host_stub.notify import RecordingNotifier
from host_stub.organization import StubDirectory

pytestmark = pytest.mark.django_db

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")


def member(
    ref: str,
    name: str,
    *,
    email: str | None = "someone@example.test",
    active: bool = True,
    manager: str | None = "u-manager",
) -> DirectoryUser:
    return DirectoryUser(
        user_ref=ref,
        display_name=name,
        email=email,
        language="ar",
        role="employee",
        department_refs=("dep-1",),
        manager_ref=manager,
        is_active=active,
    )


@pytest.fixture
def directory(monkeypatch: pytest.MonkeyPatch) -> StubDirectory:
    stub = StubDirectory()
    stub.add_department(ORG, "dep-1", "Training")
    stub.add_user(ORG, member("u-learner", "سارة العلي", email="learner@example.test"))
    stub.add_user(ORG, member("u-two", "عمر الخطيب", email="two@example.test"))
    stub.add_user(
        ORG, member("u-manager", "مدير الفريق", email="manager@example.test", manager=None)
    )
    stub.add_user(ORG, member("u-gone", "موظف سابق", email=None, active=False))
    monkeypatch.setattr(service, "directory", lambda: stub)
    return stub


@pytest.fixture
def notifier(monkeypatch: pytest.MonkeyPatch) -> RecordingNotifier:
    stub = RecordingNotifier()
    monkeypatch.setattr(service, "adapter", lambda: stub)
    return stub


@pytest.fixture(autouse=True)
def _subscriptions() -> Iterator[None]:
    handlers.subscribe_all()
    yield
    handlers.unsubscribe_all()
    clear_handlers()


def due_after(days_from_due: int) -> datetime:
    """A due date ``days_from_due`` days before today, at noon UTC (business time is UTC)."""
    today = service.local_date(timezone.now())
    return datetime.combine(today - timedelta(days=days_from_due), time(12, 0), tzinfo=UTC)


def enrollment_with_due(
    days_from_due: int,
    *,
    user_ref: str = "u-learner",
    manager: str = "u-manager",
    **overrides: Any,
) -> Enrollment:
    course = make_course(ORG)
    version = make_version(ORG, course=course)
    assignment = make_assignment(ORG, course=course, assigned_by_ref=manager)
    return make_enrollment(
        ORG,
        course=course,
        version=version,
        assignment=assignment,
        user_ref=user_ref,
        due_at=due_after(days_from_due),
        **overrides,
    )


def kinds_by_enrollment() -> dict[UUID, set[str]]:
    found: dict[UUID, set[str]] = {}
    for row in ReminderLog.objects.filter(organization_id=ORG):
        found.setdefault(row.enrollment_id, set()).add(row.kind)
    return found


# --- the date matrix --------------------------------------------------------


def test_the_date_matrix_produces_exactly_the_anchored_reminders(
    directory: StubDirectory, notifier: RecordingNotifier
) -> None:
    enrollment = {delta: enrollment_with_due(delta) for delta in (-5, -3, -1, 0, 1, 3, 5)}

    counts = reminders.evaluate()

    found = kinds_by_enrollment()
    assert enrollment[-5].pk not in found
    assert found[enrollment[-3].pk] == {ReminderLog.Kind.DUE_MINUS_3}
    assert enrollment[-1].pk not in found
    assert found[enrollment[0].pk] == {ReminderLog.Kind.DUE}
    assert found[enrollment[1].pk] == {ReminderLog.Kind.DUE_PLUS_1}
    assert found[enrollment[3].pk] == {ReminderLog.Kind.MANAGER_ESCALATION}
    assert found[enrollment[5].pk] == {ReminderLog.Kind.MANAGER_ESCALATION}
    # Three learner reminders leave; the two escalations land in one digest batch each.
    learner_mail = [
        message
        for _, message in notifier.sent_mail
        if message.recipient_ref == "u-learner" and message.kind in reminders.OFFSETS.values()
    ]
    assert len(learner_mail) == 3
    assert counts["reminders"] == 3
    assert counts["escalations"] == 2
    assert counts["digests"] == 2


def test_a_second_run_on_the_same_day_adds_nothing(
    directory: StubDirectory, notifier: RecordingNotifier
) -> None:
    for delta in (-3, 0, 3):
        enrollment_with_due(delta)

    reminders.evaluate()
    rows_after_first = ReminderLog.objects.filter(organization_id=ORG).count()
    sent_after_first = len(notifier.sent_mail)
    counts = reminders.evaluate()

    assert ReminderLog.objects.filter(organization_id=ORG).count() == rows_after_first
    assert len(notifier.sent_mail) == sent_after_first
    assert counts["reminders"] == 0
    assert counts["escalations"] == 0


# --- suppression ------------------------------------------------------------


def test_acknowledgement_suppresses_the_learner_reminder_but_not_the_escalation(
    directory: StubDirectory, notifier: RecordingNotifier
) -> None:
    today = enrollment_with_due(0, acknowledged_at=timezone.now())
    overdue = enrollment_with_due(3, user_ref="u-two", acknowledged_at=timezone.now())

    counts = reminders.evaluate()

    found = kinds_by_enrollment()
    assert today.pk not in found
    assert found[overdue.pk] == {ReminderLog.Kind.MANAGER_ESCALATION}
    assert counts["reminders"] == 0
    assert counts["skipped"] == 1


def test_a_completed_or_cancelled_enrollment_is_never_evaluated(
    directory: StubDirectory, notifier: RecordingNotifier
) -> None:
    enrollment_with_due(
        0, user_ref="u-two", status=Enrollment.Status.COMPLETED, completed_at=timezone.now()
    )
    enrollment_with_due(
        3, user_ref="u-manager", status=Enrollment.Status.CANCELLED, cancelled_at=timezone.now()
    )

    assert reminders.evaluate()["reminders"] == 0
    assert not ReminderLog.objects.filter(organization_id=ORG).exists()


def test_an_inactive_recipient_gets_no_reminder_row(
    directory: StubDirectory, notifier: RecordingNotifier
) -> None:
    enrollment = enrollment_with_due(0, user_ref="u-gone", manager="u-manager")

    counts = reminders.evaluate()

    assert counts["reminders"] == 0
    assert counts["skipped"] == 1
    assert not ReminderLog.objects.filter(enrollment=enrollment).exists()
    assert notifier.sent_mail == ()


# --- the digest -------------------------------------------------------------


def test_the_digest_lists_every_overdue_learner_once(
    directory: StubDirectory, notifier: RecordingNotifier
) -> None:
    enrollment_with_due(3)
    enrollment_with_due(3, user_ref="u-two")

    reminders.evaluate()

    digest_mail = [
        message for _, message in notifier.sent_mail if message.kind == "manager_escalation"
    ]
    assert len(digest_mail) == 1
    message = digest_mail[0]
    assert message.recipient_ref == "u-manager"
    assert message.payload is not None
    html = str(message.payload["html"])
    assert "سارة العلي" in html
    assert "عمر الخطيب" in html
    assert "تجاوز 2 من فريقك" in html
    rows = NotificationLog.objects.filter(
        kind=NotificationLog.Kind.MANAGER_ESCALATION, organization_id=ORG
    )
    assert {row.channel for row in rows} == {"email", "in_app"}
    assert rows.filter(status=NotificationLog.Status.SENT).count() == 2


def test_the_bare_digest_task_repairs_a_recorded_escalation(
    directory: StubDirectory, notifier: RecordingNotifier
) -> None:
    enrollment = enrollment_with_due(3)
    make_reminder(
        ORG,
        enrollment=enrollment,
        kind=ReminderLog.Kind.MANAGER_ESCALATION,
        recipient_ref="u-manager",
    )

    assert len(reminders.pending_digests()) == 1
    assert tasks.send_escalation_digest.apply().result == 1

    assert reminders.pending_digests() == []
    assert NotificationLog.objects.filter(
        kind=NotificationLog.Kind.MANAGER_ESCALATION, organization_id=ORG
    ).exists()
    assert [message.kind for _, message in notifier.sent_mail] == ["manager_escalation"]
