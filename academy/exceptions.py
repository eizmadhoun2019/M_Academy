"""Domain exceptions.

Services raise these instead of returning error codes (RULES: "services raise domain
exceptions, never return error codes"). The API layer maps ``AcademyError.code`` onto the
stable error codes of ``docs/api.md`` §11 in one place, so a new failure mode is a new
subclass rather than a new string at each call site.
"""

from __future__ import annotations

from typing import Any


class AcademyError(Exception):
    """Base class for every Academy domain failure."""

    #: Stable wire code (``docs/api.md`` §11). Subclasses narrow it.
    code = "validation_error"

    def __init__(self, detail: str = "", *, fields: dict[str, Any] | None = None) -> None:
        super().__init__(detail or self.code)
        self.detail = detail
        self.fields = fields or {}


class DomainValidationError(AcademyError):
    """Input the domain rejects (400)."""

    code = "validation_error"


class NotFound(AcademyError):
    """The object does not exist in this tenant (404 — never a cross-tenant hint)."""

    code = "not_found"


class Forbidden(AcademyError):
    """The caller lacks the capability or the object scope (403)."""

    code = "forbidden"


class AccessSuspended(AcademyError):
    """Academy-local suspension makes every capability ineffective (403, D-028)."""

    code = "access_suspended"


class InactiveAccount(AcademyError):
    """A verified but inactive member (403, ``docs/api.md`` §1)."""

    code = "account_inactive"


class Conflict(AcademyError):
    """The current state refuses the operation (409)."""

    code = "idempotency_conflict"


class LastAdmin(AcademyError):
    """Revoking the last active ``academy.admin`` grant (409, ``docs/api.md`` §7)."""

    code = "last_admin"


class StateConflict(AcademyError):
    """A state refuses the operation (409) under a specific documented ``code``."""

    code = "conflict"

    def __init__(
        self, code: str, detail: str = "", *, fields: dict[str, Any] | None = None
    ) -> None:
        super().__init__(detail, fields=fields)
        self.code = code


class PublishInvalid(AcademyError):
    """A draft that breaks the publish rules (422, ``docs/api.md`` §8)."""

    code = "publish_invalid"


class AdapterNotConfigured(AcademyError):
    """A host seam has no configured implementation; a deployment error, never a fallback."""

    code = "unavailable"


class MediaUploadError(AcademyError):
    """An upload the policy rejects before any bytes are stored (400)."""

    code = "validation_error"

    def __init__(
        self, code: str, detail: str = "", *, fields: dict[str, Any] | None = None
    ) -> None:
        super().__init__(detail, fields=fields)
        self.code = code
