"""T-010 acceptance: every Academy table is isolated by ``for_org``.

The suite is generic: it takes every concrete model from the app registry, requires a factory
for it, writes one row per organization, and asserts that neither organization can see the
other's row. The detector is itself tested against a deliberately unscoped query, so a broken
detector cannot pass silently.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from conftest import ORG_ID, OTHER_ORG_ID
from django.apps import apps
from factories import FACTORIES, assert_only_own_rows, make_row

from academy.models import Course, TenantModel

MODELS = sorted(FACTORIES, key=lambda model: model.__name__)
MODEL_IDS = [model.__name__ for model in MODELS]


def test_every_academy_model_has_a_factory() -> None:
    # Test-only probe models also register under this app label; the schema under test is
    # the one declared in `academy.models`.
    registered = {
        model
        for model in apps.get_app_config("academy").get_models()
        if model.__module__.startswith("academy.models")
    }
    tenant_models = {model for model in registered if issubclass(model, TenantModel)}
    global_models = {"Organization", "User"}
    missing = sorted(model.__name__ for model in tenant_models - set(FACTORIES))

    assert missing == []
    # Identity tables are global by design (§1.1); they must not quietly become tenant rows.
    assert {model.__name__ for model in registered - tenant_models} == global_models


@pytest.mark.django_db
@pytest.mark.parametrize("model", MODELS, ids=MODEL_IDS)
def test_for_org_sees_only_its_own_row(model: type[TenantModel]) -> None:
    mine = make_row(model, ORG_ID)
    theirs = make_row(model, OTHER_ORG_ID)

    own = list(model.objects.for_org(ORG_ID).values_list("pk", flat=True))
    other = list(model.objects.for_org(OTHER_ORG_ID).values_list("pk", flat=True))

    assert own == [mine.pk]
    assert other == [theirs.pk]
    assert model.objects.count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize("model", MODELS, ids=MODEL_IDS)
def test_the_detector_reports_a_leak_for_every_table(model: type[TenantModel]) -> None:
    make_row(model, ORG_ID)
    make_row(model, OTHER_ORG_ID)

    with pytest.raises(AssertionError, match="leaked"):
        assert_only_own_rows(model, ORG_ID)


@pytest.mark.django_db
def test_the_detector_passes_once_only_own_rows_exist() -> None:
    make_row(Course, ORG_ID)
    make_row(Course, OTHER_ORG_ID)

    Course.objects.filter(organization_id=OTHER_ORG_ID).delete()
    assert_only_own_rows(Course, ORG_ID)


@pytest.mark.django_db
def test_an_unscoped_query_is_why_for_org_is_mandatory() -> None:
    mine = make_row(Course, ORG_ID)
    make_row(Course, OTHER_ORG_ID)

    assert Course.objects.count() == 2
    assert list(Course.objects.for_org(ORG_ID)) == [mine]


@pytest.mark.django_db
def test_for_org_rejects_anything_that_is_not_an_organization_uuid() -> None:
    with pytest.raises(ValueError, match="organization UUID"):
        Course.objects.for_org("25498ed9-13b1-4f10-8294-859ff80a41b7")  # type: ignore[arg-type]


@pytest.mark.django_db
def test_the_two_fixtures_are_different_tenants(org_id: UUID, other_org_id: UUID) -> None:
    assert org_id != other_org_id
