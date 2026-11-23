"""Signed-identity seam (``docs/hub-contract.md`` §2, §5).

The host verifies the proxy's assertion; ``academy`` only ever receives decoded claims and
still enforces issuer, audience, freshness, route binding and the nonce check itself. An
implementation therefore returns the claim object or raises :class:`ValueError` — it must
never return ``None`` for an invalid token, because ``None`` would read as "no identity" and
turn a verification bug into an authentication bypass.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IdentityAdapter(Protocol):
    """Verifies the signed identity assertion of ``docs/hub-contract.md`` §2.

    ``keys`` maps a key id (``kid``) to its shared secret, which is how the contract supports
    rotation: several keys are accepted while one is current.
    """

    def verify(self, token: str, keys: Mapping[str, str]) -> dict[str, Any]:
        """Return the decoded claims for ``token``, or raise ``ValueError``."""
        ...
