"""Production signed-identity verifier for the ``kid.payload.signature`` envelope.

The cryptographic work is identical to the development verifier (same wire format); this class
exists so the production profile names a Hub implementation rather than a development stub,
and so a replacement JWT verifier can be dropped in through
``ACADEMY_HUB_IDENTITY_VERIFIER`` without touching callers.
"""

from __future__ import annotations

from host_stub.identity import DevelopmentIdentity


class HubIdentity(DevelopmentIdentity):
    """HMAC-SHA256 verifier used when the Hub proxy signs identities."""
