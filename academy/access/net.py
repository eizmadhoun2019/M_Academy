"""Client-address helpers shared by sign-in and the session registry."""

from __future__ import annotations

import ipaddress
from typing import Any


def client_ip(request: Any) -> str:
    if request is None:
        return "unknown"
    meta = getattr(request, "META", {})
    return str(meta.get("REMOTE_ADDR") or "unknown")


def truncated_ip(value: str) -> str:
    """The address form that may be stored or logged: a /24 (v4) or /48 (v6) network."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return ""
    prefix = 24 if address.version == 4 else 48
    network = ipaddress.ip_network(f"{address}/{prefix}", strict=False)
    return str(network.network_address)
