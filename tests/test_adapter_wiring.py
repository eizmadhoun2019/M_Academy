"""T-004 acceptance: every seam is configured to a stub that honours its Protocol."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from django.conf import settings

from academy.adapters import (
    ADAPTER_NAMES,
    IdentityAdapter,
    NotifyAdapter,
    OrganizationAdapter,
    StorageAdapter,
    load_adapter,
    reset_adapter_cache,
)

PROTOCOLS: dict[str, type[Any]] = {
    "identity": IdentityAdapter,
    "organization": OrganizationAdapter,
    "notify": NotifyAdapter,
    "storage": StorageAdapter,
}


@pytest.fixture(autouse=True)
def _clean_cache() -> Iterator[None]:
    reset_adapter_cache()
    yield
    reset_adapter_cache()


@pytest.mark.parametrize("name", ADAPTER_NAMES)
def test_the_test_profile_configures_every_seam(name: str) -> None:
    assert settings.ACADEMY_ADAPTERS[name]


@pytest.mark.parametrize(("name", "protocol"), list(PROTOCOLS.items()))
def test_every_seam_loads_a_stub_that_satisfies_its_protocol(
    name: str, protocol: type[Any]
) -> None:
    adapter_class = load_adapter(name)

    assert adapter_class.__module__.startswith("host_stub.")
    assert isinstance(adapter_class(), protocol)


def test_the_protocols_are_distinct_seams() -> None:
    assert len(set(PROTOCOLS)) == len(ADAPTER_NAMES)
