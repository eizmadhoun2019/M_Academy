"""Notification seam contract (REQ-02) — every implementation must pass this suite."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from academy.adapters.notify import (
    ActivityEvent,
    MailMessage,
    NotifyAdapter,
)
from academy.exceptions import Conflict
from host_stub.notify import RecordingNotifier

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
OTHER_ORG = UUID("2f5e3d1a-0c4b-4a8e-9f2d-6b7c8d9e0f11")

IMPLEMENTATIONS: dict[str, Callable[[], NotifyAdapter]] = {
    "host_stub.RecordingNotifier": RecordingNotifier,
}


@pytest.fixture(params=list(IMPLEMENTATIONS.values()), ids=list(IMPLEMENTATIONS))
def adapter(request: pytest.FixtureRequest) -> NotifyAdapter:
    return request.param()


def message(**overrides: object) -> MailMessage:
    values: dict[str, object] = {
        "kind": "course_assigned",
        "recipient_ref": "u-42",
        "title": "A course has been assigned to you",
        "body": "Example course is ready.",
        "idempotency_key": "assigned:a-12:u-42",
        "url": "/academy/my/",
        "channels": ("email", "in_app"),
    }
    values.update(overrides)
    return MailMessage(**values)  # type: ignore[arg-type]


def event(**overrides: object) -> ActivityEvent:
    values: dict[str, object] = {
        "event_id": uuid4(),
        "action": "grant.created",
        "actor_ref": "u-10",
        "object_type": "grant",
        "object_id": "g-7",
        "occurred_at": datetime(2026, 11, 23, 8, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return ActivityEvent(**values)  # type: ignore[arg-type]


def test_first_send_is_accepted_once(adapter: NotifyAdapter) -> None:
    receipt = adapter.send_mail(ORG, message())

    assert receipt.accepted is True
    assert receipt.duplicate is False


def test_resending_the_same_key_and_content_is_a_duplicate(adapter: NotifyAdapter) -> None:
    adapter.send_mail(ORG, message())

    receipt = adapter.send_mail(ORG, message())

    assert receipt.accepted is True
    assert receipt.duplicate is True


def test_reusing_a_key_for_different_content_is_a_conflict(adapter: NotifyAdapter) -> None:
    adapter.send_mail(ORG, message())

    with pytest.raises(Conflict):
        adapter.send_mail(ORG, message(body="Something else entirely."))


def test_idempotency_is_scoped_to_the_organization(adapter: NotifyAdapter) -> None:
    adapter.send_mail(ORG, message())

    receipt = adapter.send_mail(OTHER_ORG, message())

    assert receipt.duplicate is False


def test_optional_url_and_payload(adapter: NotifyAdapter) -> None:
    receipt = adapter.send_mail(ORG, message(url=None, payload=None))

    assert receipt.accepted is True


def test_a_message_never_carries_a_name_or_address() -> None:
    fields = set(MailMessage.__dataclass_fields__)

    assert not fields & {"email", "address", "display_name", "recipient_name"}


@pytest.mark.parametrize("field", ["kind", "recipient_ref", "title", "idempotency_key"])
def test_empty_required_fields_are_refused(field: str) -> None:
    with pytest.raises(ValueError):
        message(**{field: "  "})


def test_an_unknown_channel_is_refused() -> None:
    with pytest.raises(ValueError):
        message(channels=("email", "sms"))


def test_at_least_one_channel_is_required() -> None:
    with pytest.raises(ValueError):
        message(channels=())


def test_a_relative_or_absolute_url_is_refused() -> None:
    with pytest.raises(ValueError):
        message(url="https://hub.example.com/academy/")


def test_an_event_is_recorded_once(adapter: NotifyAdapter) -> None:
    assert adapter.record_activity(ORG, event()) is True


def test_repeating_an_event_is_a_no_op(adapter: NotifyAdapter) -> None:
    record = event()
    adapter.record_activity(ORG, record)

    assert adapter.record_activity(ORG, record) is False


def test_reusing_an_event_id_for_different_content_is_a_conflict(adapter: NotifyAdapter) -> None:
    record = event()
    adapter.record_activity(ORG, record)

    with pytest.raises(Conflict):
        adapter.record_activity(ORG, event(event_id=record.event_id, action="grant.revoked"))


def test_an_naive_timestamp_is_refused() -> None:
    with pytest.raises(ValueError):
        event(occurred_at=datetime(2026, 11, 23, 8, 0))
