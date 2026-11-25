"""Hub transports against the loopback fake (T-015, ``docs/hub-contract.md`` §3).

The same organization-contract assertions the stub must satisfy are replayed over real HTTP,
plus delivery idempotency and directory cache invalidation — the three behaviors a fake is
specifically there to exercise.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from django.core.cache import cache
from django.test import override_settings

from academy.adapters.notify import ActivityEvent, MailMessage
from academy.adapters.organization import MAX_USER_REFS, DirectoryUser
from academy.exceptions import Conflict
from academy.hub.cache import invalidate_directory
from host_hub.directory import HubDirectory
from host_hub.fake import FakeHub
from host_hub.http import HubHttpClient, HubUnavailable
from host_hub.notify import HubNotifier

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
OTHER_ORG = UUID("2f5e3d1a-0c4b-4a8e-9f2d-6b7c8d9e0f11")


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    cache.clear()


@pytest.fixture
def hub() -> Iterator[FakeHub]:
    fake = FakeHub(organization_id=ORG)
    fake.add_department("operations", "Operations")
    fake.add_department("training", "Training", parent_ref="operations")
    fake.add_role("employee", "Employee")
    fake.add_user(
        {
            "user_ref": "u-10",
            "display_name": "Example Manager",
            "email": None,
            "language": "ar",
            "role": "department_manager",
            "department_refs": ["operations"],
            "manager_ref": None,
            "is_active": True,
        }
    )
    fake.add_user(
        {
            "user_ref": "u-42",
            "display_name": "Example Employee",
            "email": "u42@example.test",
            "language": "en",
            "role": "employee",
            "department_refs": ["training"],
            "manager_ref": "u-10",
            "is_active": True,
        }
    )
    with fake:
        yield fake


def directory(hub: FakeHub) -> HubDirectory:
    return HubDirectory(HubHttpClient(base_url=hub.base_url, token=hub.token))


def test_departments_and_descendant_members(hub: FakeHub) -> None:
    adapter = directory(hub)
    assert [(d.ref, d.name, d.parent_ref) for d in adapter.departments(ORG)] == [
        ("operations", "Operations", None),
        ("training", "Training", "operations"),
    ]
    assert list(adapter.department_members(ORG, "operations")) == ["u-10", "u-42"]
    assert list(adapter.department_members(ORG, "training")) == ["u-42"]


def test_manager_users_and_roles(hub: FakeHub) -> None:
    adapter = directory(hub)
    assert adapter.manager_of(ORG, "u-42") == "u-10"
    assert adapter.manager_of(ORG, "u-unknown") is None
    users = list(adapter.users(ORG, ["u-42", "u-10", "u-missing"]))
    assert [user.user_ref for user in users] == ["u-42", "u-10"]
    assert users[0].department_refs == ("training",)
    assert [role.ref for role in adapter.roles(ORG)] == ["employee"]
    assert list(adapter.role_members(ORG, "employee")) == ["u-42"]


def test_another_tenant_and_unknown_department_are_empty(hub: FakeHub) -> None:
    adapter = directory(hub)
    assert list(adapter.departments(OTHER_ORG)) == []
    assert list(adapter.department_members(ORG, "unknown")) == []


def test_more_than_fifty_references_is_a_caller_error(hub: FakeHub) -> None:
    with pytest.raises(ValueError):
        directory(hub).users(ORG, [f"u-{index}" for index in range(MAX_USER_REFS + 1)])


def test_lookups_are_cached_until_invalidated(hub: FakeHub) -> None:
    adapter = directory(hub)
    before = len([call for call in hub.requests if call[1].endswith("/departments")])
    adapter.departments(ORG)
    adapter.departments(ORG)
    after = len([call for call in hub.requests if call[1].endswith("/departments")])
    assert after - before == 1
    invalidate_directory(ORG)
    adapter.departments(ORG)
    assert len([call for call in hub.requests if call[1].endswith("/departments")]) == after + 1


def test_mail_is_delivered_once_per_key(hub: FakeHub) -> None:
    notifier = HubNotifier(HubHttpClient(base_url=hub.base_url, token=hub.token))
    message = MailMessage(
        kind="course_assigned",
        recipient_ref="u-42",
        title="Assigned training",
        body="A course is ready.",
        idempotency_key="assigned-training-u42",
        url="/academy/",
        channels=("email", "in_app"),
    )
    first = notifier.send_mail(ORG, message)
    repeat = notifier.send_mail(ORG, message)
    assert (first.accepted, first.duplicate) == (True, False)
    assert (repeat.accepted, repeat.duplicate) == (True, True)
    assert len(hub.mails) == 1


def test_a_reused_key_with_different_content_conflicts(hub: FakeHub) -> None:
    notifier = HubNotifier(HubHttpClient(base_url=hub.base_url, token=hub.token))
    first = MailMessage(
        kind="course_assigned",
        recipient_ref="u-42",
        title="Assigned training",
        body="A course is ready.",
        idempotency_key="same-key",
    )
    changed = MailMessage(
        kind="course_assigned",
        recipient_ref="u-42",
        title="Assigned training",
        body="Different content.",
        idempotency_key="same-key",
    )
    notifier.send_mail(ORG, first)
    with pytest.raises(Conflict):
        notifier.send_mail(ORG, changed)


def test_activity_is_mirrored_once(hub: FakeHub) -> None:
    notifier = HubNotifier(HubHttpClient(base_url=hub.base_url, token=hub.token))
    event = ActivityEvent(
        event_id=uuid4(),
        action="enrollment.cancelled",
        actor_ref="system",
        object_type="enrollment",
        object_id="e-79",
        occurred_at=datetime(2026, 11, 20, 8, 0, tzinfo=UTC),
    )
    assert notifier.record_activity(ORG, event) is True
    assert notifier.record_activity(ORG, event) is False
    assert len(hub.activities) == 1


def test_an_unreachable_hub_is_unavailable_not_empty(hub: FakeHub) -> None:
    broken = HubHttpClient(base_url="http://127.0.0.1:1", token=hub.token)
    with override_settings(ACADEMY_HUB_CIRCUIT_SECONDS=30), pytest.raises(HubUnavailable):
        HubDirectory(broken).departments(ORG)


def test_a_directory_user_value_type_is_usable() -> None:
    user = DirectoryUser(
        user_ref="u-42",
        display_name="Example",
        email=None,
        language="ar",
        role="employee",
        department_refs=(),
        manager_ref=None,
        is_active=True,
    )
    assert user.is_active
