"""T-003 acceptance: ``TenantModel`` and ``for_org`` (``docs/domain-model.md`` §1.1)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connection, models

from academy.models import TenantManager, TenantModel


class TenantProbe(TenantModel):
    """Concrete model used only in this module; it has no migration and no app of its own."""

    label = models.CharField(max_length=20)
    objects: TenantManager[TenantProbe] = TenantManager()  # type: ignore[assignment]

    class Meta:
        app_label = "academy"


@pytest.fixture(scope="module", autouse=True)
def probe_table(django_db_setup: None, django_db_blocker: Any) -> Iterator[None]:
    """The probe has no migration, so its table exists only for this module's tests.

    The DDL commits (it runs outside the per-test transaction), so the fixture also drops a
    leftover table from an interrupted run before creating its own.
    """
    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        if TenantProbe._meta.db_table in connection.introspection.table_names():
            editor.delete_model(TenantProbe)
        editor.create_model(TenantProbe)
    yield
    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        if TenantProbe._meta.db_table in connection.introspection.table_names():
            editor.delete_model(TenantProbe)


def test_base_model_is_abstract_with_the_documented_columns() -> None:
    assert TenantModel._meta.abstract is True
    assert {field.name for field in TenantModel._meta.get_fields()} == {
        "id",
        "organization_id",
        "created_at",
        "updated_at",
    }
    assert TenantModel._meta.get_field("id").primary_key is True
    assert TenantModel._meta.get_field("organization_id").null is False


def test_uuid_primary_key_is_generated_in_python() -> None:
    row = TenantProbe(label="draft", organization_id=uuid.uuid4())

    assert isinstance(row.id, uuid.UUID)


def test_manager_is_the_documented_default() -> None:
    assert isinstance(TenantProbe.objects, TenantManager)
    default_manager = TenantProbe._meta.default_manager
    assert default_manager is not None
    assert default_manager.name == "objects"


@pytest.mark.django_db
def test_for_org_returns_only_that_organization() -> None:
    mine, other = uuid.uuid4(), uuid.uuid4()
    TenantProbe.objects.create(label="mine-a", organization_id=mine)
    TenantProbe.objects.create(label="mine-b", organization_id=mine)
    TenantProbe.objects.create(label="other", organization_id=other)

    assert TenantProbe.objects.for_org(mine).count() == 2
    assert set(TenantProbe.objects.for_org(mine).values_list("label", flat=True)) == {
        "mine-a",
        "mine-b",
    }
    assert TenantProbe.objects.for_org(other).values_list("label", flat=True).get() == "other"
    # The unrestricted manager is still unscoped: that is why review rejects it in services.
    assert TenantProbe.objects.count() == 3


@pytest.mark.django_db
def test_for_org_refuses_a_scope_that_is_not_an_organization_uuid() -> None:
    for scope in (None, "", 1, "0b7c2f3e-0000-0000-0000-000000000000"):
        with pytest.raises(ValueError, match="organization UUID"):
            TenantProbe.objects.for_org(scope)  # type: ignore[arg-type]
