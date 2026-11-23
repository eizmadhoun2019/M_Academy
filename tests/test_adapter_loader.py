"""T-003 acceptance: the adapter loader resolves, caches and refuses loudly."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from academy.adapters import ADAPTER_NAMES, load_adapter, reset_adapter_cache
from academy.exceptions import AdapterNotConfigured


class FakeStorage:
    """Stands in for the T-004 ``host_stub`` implementation."""


def not_a_class() -> None:
    """Deliberately not a class, to prove the loader checks the target."""


@pytest.fixture(autouse=True)
def _clean_cache() -> Iterator[None]:
    reset_adapter_cache()
    yield
    reset_adapter_cache()


def configure(monkeypatch: pytest.MonkeyPatch, name: str, path: str) -> None:
    monkeypatch.setitem(settings.ACADEMY_ADAPTERS, name, path)


def test_configured_path_resolves_to_the_class(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch, "storage", f"{__name__}:FakeStorage")

    assert load_adapter("storage") is FakeStorage


def test_resolution_is_cached_until_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch, "storage", f"{__name__}:FakeStorage")
    assert load_adapter("storage") is FakeStorage

    configure(monkeypatch, "storage", f"{__name__}:not_a_class")
    assert load_adapter("storage") is FakeStorage  # cached, no second import

    reset_adapter_cache()
    with pytest.raises(ImproperlyConfigured, match="does not resolve to a class"):
        load_adapter("storage")


@pytest.mark.parametrize("name", ADAPTER_NAMES)
def test_unconfigured_seam_raises_instead_of_defaulting(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setitem(settings.ACADEMY_ADAPTERS, name, "")

    with pytest.raises(AdapterNotConfigured, match=f"ACADEMY_ADAPTER_{name.upper()}"):
        load_adapter(name)


def test_unknown_seam_is_rejected() -> None:
    with pytest.raises(AdapterNotConfigured, match="Unknown adapter"):
        load_adapter("billing")


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("academy.adapters.loader", "must be 'module.path:ClassName'"),
        (":FakeStorage", "must be 'module.path:ClassName'"),
        ("no_such_module:FakeStorage", "is not importable"),
        (f"{__name__}:Missing", "does not resolve to a class"),
        (f"{__name__}:not_a_class", "does not resolve to a class"),
    ],
)
def test_malformed_configuration_is_reported_clearly(
    monkeypatch: pytest.MonkeyPatch, path: str, message: str
) -> None:
    configure(monkeypatch, "notify", path)

    with pytest.raises(ImproperlyConfigured, match=message):
        load_adapter("notify")


def test_loader_returns_a_class_not_an_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch, "organization", f"{__name__}:FakeStorage")

    resolved: Any = load_adapter("organization")

    assert isinstance(resolved, type)
