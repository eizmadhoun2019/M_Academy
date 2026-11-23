"""Adapter loader — the single seam between ``academy`` and the host.

``academy`` may not import ``host_stub`` or any provider SDK (gate G7, RULES). It resolves the
class named by an ``ACADEMY_ADAPTER_*`` setting (``docs/configuration.md`` §11) on first use and
caches it for the process lifetime. A seam with no configured path raises instead of falling
back to a default: a deployment that forgot an adapter must fail loudly, not degrade silently.
"""

from __future__ import annotations

import importlib
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from academy.exceptions import AdapterNotConfigured

#: The host seams of ARCHITECTURE.md §4, in the order their tasks land.
ADAPTER_NAMES = ("identity", "organization", "notify", "storage")

_CACHE: dict[str, type[Any]] = {}


def load_adapter(name: str) -> type[Any]:
    """Return the class configured for ``name`` (``"module.path:ClassName"``).

    Raises :class:`AdapterNotConfigured` when the seam is unknown or unset, and
    :class:`~django.core.exceptions.ImproperlyConfigured` when the configured path is
    malformed, unimportable or not a class.
    """
    if name in _CACHE:
        return _CACHE[name]
    if name not in ADAPTER_NAMES:
        raise AdapterNotConfigured(f"Unknown adapter {name!r}; known: {', '.join(ADAPTER_NAMES)}")

    configured = getattr(settings, "ACADEMY_ADAPTERS", {}) or {}
    path = str(configured.get(name) or "").strip()
    if not path:
        raise AdapterNotConfigured(
            f"Adapter {name!r} has no configured implementation "
            f"(set ACADEMY_ADAPTER_{name.upper()})"
        )

    module_path, _, class_name = path.partition(":")
    if not module_path or not class_name:
        raise ImproperlyConfigured(
            f"ACADEMY_ADAPTER_{name.upper()}={path!r} must be 'module.path:ClassName'"
        )

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:  # also covers a missing dependency inside the module
        raise ImproperlyConfigured(
            f"Adapter {name!r}: module {module_path!r} is not importable ({exc})"
        ) from exc

    target = getattr(module, class_name, None)
    if not isinstance(target, type):
        raise ImproperlyConfigured(
            f"Adapter {name!r}: {path!r} does not resolve to a class in {module_path!r}"
        )

    _CACHE[name] = target
    return target


def reset_adapter_cache() -> None:
    """Forget resolved adapters; tests and settings reloads call this."""
    _CACHE.clear()
