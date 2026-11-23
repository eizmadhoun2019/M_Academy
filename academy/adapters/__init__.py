"""Host seams (ARCHITECTURE.md §4). Only the loader resolves a host implementation."""

from __future__ import annotations

from academy.adapters.loader import ADAPTER_NAMES, load_adapter, reset_adapter_cache

__all__ = ["ADAPTER_NAMES", "load_adapter", "reset_adapter_cache"]
