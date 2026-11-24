"""drf-spectacular extensions, auto-imported from the app's ``schema`` module.

The API's authenticator is the access context that the identity layer builds, so the schema
document declares the header the Hub proxy actually sends (``docs/hub-contract.md`` §2).
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class AcademyAccessAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "academy.api.authentication.AcademyAccessAuthentication"
    name = "hubIdentity"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        return {"type": "apiKey", "in": "header", "name": "X-Masheed-Identity"}
