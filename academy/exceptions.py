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


class InvalidCredentials(AcademyError):
    """A sign-in that must not reveal whether the email exists (401)."""

    code = "invalid_credentials"


class TokenInvalid(AcademyError):
    """An unknown, used or expired verification/reset token (400)."""

    code = "token_invalid"


class TooManyAttempts(AcademyError):
    """The documented failure window has locked this email+IP pair (429)."""

    code = "throttled"


class EmailUnverified(AcademyError):
    """A signed-in account must verify its address before tenant access (403)."""

    code = "email_unverified"


class Forbidden(AcademyError):
    """The caller lacks the capability or the object scope (403)."""

    code = "forbidden"


class AccessSuspended(AcademyError):
    """Academy-local suspension makes every capability ineffective (403, D-028)."""

    code = "access_suspended"


class InactiveAccount(AcademyError):
    """A verified but inactive member (403, ``docs/api.md`` §1)."""

    code = "account_inactive"


class MembershipInactive(AcademyError):
    """A signed-in account with no active company membership (403, ``docs/api.md`` §1)."""

    code = "membership_inactive"


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


class LessonLocked(AcademyError):
    """A lesson whose earlier required lesson is incomplete (403, ``lesson_locked``)."""

    code = "lesson_locked"

    def __init__(self, next_lesson_id: Any, detail: str = "") -> None:
        super().__init__(detail or self.code, fields={"next_lesson_id": str(next_lesson_id)})


class TargetEmpty(AcademyError):
    """An assignment whose target reaches nobody (422, ``target_empty``)."""

    code = "target_empty"


class InvalidRange(AcademyError):
    """A report window whose ``from`` is after its ``to`` (400, ``invalid_range``)."""

    code = "invalid_range"


class ProgressSkipRejected(AcademyError):
    """A heartbeat that claims more playback than the clock allows (400, §7.3 step 5)."""

    code = "progress_skip_rejected"

    def __init__(self, allowed_seconds: float, detail: str = "") -> None:
        super().__init__(
            detail or "the playback position is ahead of what the server has credited",
            fields={"allowed_seconds": round(allowed_seconds, 1)},
        )


class LessonNotEligible(AcademyError):
    """A lesson below its watch threshold (409, ``lesson_not_eligible``)."""

    code = "lesson_not_eligible"

    def __init__(self, coverage_percent: float, required_percent: int) -> None:
        super().__init__(
            "the lesson has not been watched far enough",
            fields={
                "coverage_percent": coverage_percent,
                "required_percent": required_percent,
            },
        )


class EnrollmentIncomplete(AcademyError):
    """An enrollment with lessons or an acknowledgment outstanding (409, §7.7)."""

    code = "enrollment_incomplete"

    def __init__(
        self, blocking_lesson_ids: list[str], *, acknowledgment_required: bool = False
    ) -> None:
        fields: dict[str, Any] = {
            "blocking_lesson_ids": blocking_lesson_ids,
            "blocking_count": len(blocking_lesson_ids),
        }
        if acknowledgment_required:
            fields["acknowledgment_required"] = True
        super().__init__("the enrollment is not complete yet", fields=fields)


class AcknowledgmentNotRequired(AcademyError):
    """An acknowledgment on a version that does not ask for one (409)."""

    code = "acknowledgment_not_required"


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
