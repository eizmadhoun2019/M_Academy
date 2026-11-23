"""Organization seam contract (REQ-02) — every implementation must pass this suite.

The fixture is seeded through the stub's ``add_*`` methods; an implementation added later
(T-015's Hub HTTP transport) must be able to reproduce this directory through its fake and pass
the same assertions.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import pytest

from academy.adapters.organization import (
    MAX_USER_REFS,
    Department,
    DirectoryUser,
    OrganizationAdapter,
    Role,
)
from host_stub.organization import StubDirectory

ORG = UUID("25498ed9-13b1-4f10-8294-859ff80a41b7")
OTHER_ORG = UUID("2f5e3d1a-0c4b-4a8e-9f2d-6b7c8d9e0f11")


def seeded() -> StubDirectory:
    directory = StubDirectory()
    directory.add_department(ORG, "operations", "Operations")
    directory.add_department(ORG, "training", "Training", parent_ref="operations")
    directory.add_department(ORG, "sales", "Sales")
    directory.add_role(ORG, "employee", "Employee")
    directory.add_role(ORG, "department_manager", "Department manager")
    directory.add_user(
        ORG,
        DirectoryUser(
            user_ref="u-10",
            display_name="Example Manager",
            email="u10@example.test",
            language="ar",
            role="department_manager",
            department_refs=("operations",),
            manager_ref=None,
            is_active=True,
        ),
    )
    directory.add_user(
        ORG,
        DirectoryUser(
            user_ref="u-42",
            display_name="Example Employee",
            email="u42@example.test",
            language="ar",
            role="employee",
            department_refs=("training",),
            manager_ref="u-10",
            is_active=True,
        ),
    )
    directory.add_user(
        ORG,
        DirectoryUser(
            user_ref="u-77",
            display_name="Example Seller",
            email=None,
            language="en",
            role="employee",
            department_refs=("sales",),
            manager_ref="u-10",
            is_active=True,
        ),
    )
    directory.add_user(
        ORG,
        DirectoryUser(
            user_ref="u-99",
            display_name="Inactive Employee",
            email="u99@example.test",
            language="ar",
            role="employee",
            department_refs=("training",),
            manager_ref="u-10",
            is_active=False,
        ),
    )
    return directory


IMPLEMENTATIONS: dict[str, Callable[[], OrganizationAdapter]] = {
    "host_stub.StubDirectory": seeded,
}


@pytest.fixture(params=list(IMPLEMENTATIONS.values()), ids=list(IMPLEMENTATIONS))
def adapter(request: pytest.FixtureRequest) -> OrganizationAdapter:
    return request.param()


def test_lists_departments_with_their_parents(adapter: OrganizationAdapter) -> None:
    assert list(adapter.departments(ORG)) == [
        Department(ref="operations", name="Operations", parent_ref=None),
        Department(ref="sales", name="Sales", parent_ref=None),
        Department(ref="training", name="Training", parent_ref="operations"),
    ]


def test_an_unknown_organization_sees_nothing(adapter: OrganizationAdapter) -> None:
    assert adapter.departments(OTHER_ORG) == ()
    assert adapter.department_members(OTHER_ORG, "training") == ()
    assert adapter.users(OTHER_ORG, ["u-42"]) == ()
    assert adapter.roles(OTHER_ORG) == ()
    assert adapter.role_members(OTHER_ORG, "employee") == ()
    assert adapter.manager_of(OTHER_ORG, "u-42") is None


def test_department_members_include_descendants_and_active_members_only(
    adapter: OrganizationAdapter,
) -> None:
    assert adapter.department_members(ORG, "operations") == ("u-10", "u-42")
    assert adapter.department_members(ORG, "training") == ("u-42",)
    assert adapter.department_members(ORG, "sales") == ("u-77",)


def test_department_members_of_an_unknown_department_is_empty(
    adapter: OrganizationAdapter,
) -> None:
    assert adapter.department_members(ORG, "no-such-department") == ()


def test_manager_lookup_returns_none_instead_of_failing(adapter: OrganizationAdapter) -> None:
    assert adapter.manager_of(ORG, "u-42") == "u-10"
    assert adapter.manager_of(ORG, "u-10") is None
    assert adapter.manager_of(ORG, "u-nobody") is None


def test_users_keep_request_order_include_inactive_and_skip_unknown(
    adapter: OrganizationAdapter,
) -> None:
    users = adapter.users(ORG, ["u-99", "u-unknown", "u-42"])

    assert [user.user_ref for user in users] == ["u-99", "u-42"]
    assert users[0].is_active is False
    assert users[1].department_refs == ("training",)


def test_users_deduplicate_repeated_references(adapter: OrganizationAdapter) -> None:
    users = adapter.users(ORG, ["u-42", "u-42", "u-10"])

    assert [user.user_ref for user in users] == ["u-42", "u-10"]


def test_users_refuse_more_than_the_documented_batch(adapter: OrganizationAdapter) -> None:
    refs = [f"u-{index}" for index in range(MAX_USER_REFS + 1)]

    with pytest.raises(ValueError):
        adapter.users(ORG, refs)


def test_roles_and_their_members(adapter: OrganizationAdapter) -> None:
    assert list(adapter.roles(ORG)) == [
        Role(ref="department_manager", name="Department manager"),
        Role(ref="employee", name="Employee"),
    ]
    assert adapter.role_members(ORG, "employee") == ("u-42", "u-77")
    assert adapter.role_members(ORG, "department_manager") == ("u-10",)
    assert adapter.role_members(ORG, "no-such-role") == ()


@pytest.mark.parametrize(
    "call",
    [
        lambda adapter: adapter.departments(ORG),
        lambda adapter: adapter.department_members(ORG, "operations"),
        lambda adapter: adapter.users(ORG, ["u-42"]),
        lambda adapter: adapter.roles(ORG),
        lambda adapter: adapter.role_members(ORG, "employee"),
    ],
)
def test_results_are_immutable_snapshots(
    adapter: OrganizationAdapter, call: Callable[[OrganizationAdapter], object]
) -> None:
    assert isinstance(call(adapter), tuple)
