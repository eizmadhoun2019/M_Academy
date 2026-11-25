"""Message copy and rendering — ``docs/notifications.md`` §2–§3.

The copy table in the document is the source: both languages live here together with the same
variable set, so a diff between them is visible and neither can drift. Rendering is strict —
a template that names a variable the caller did not supply raises instead of shipping a
literal ``{course_title}`` to a learner, and a subject over :data:`MAX_SUBJECT` characters is
refused before the transport sees it.

Only the wrapper lives in ``templates/academy/notifications/``: the approved visual artifact
(navy ``#101820`` header, gold ``#E8AA23`` brand line, white card on ``#F8FAFC``, 12 px radius,
Tahoma/Arial) with the direction the recipient's language needs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from string import Formatter

from django.template.loader import render_to_string
from django.utils import timezone

#: ``docs/notifications.md`` §3: a longer subject is truncated by mail clients.
MAX_SUBJECT = 78

LANGUAGES = ("ar", "en")
DIRECTIONS = {"ar": "rtl", "en": "ltr"}

MESSAGE_TEMPLATE = "academy/notifications/message.html"
MESSAGE_TEXT_TEMPLATE = "academy/notifications/message.txt"
DIGEST_TEMPLATE = "academy/notifications/digest.html"
DIGEST_TEXT_TEMPLATE = "academy/notifications/digest.txt"


@dataclass(frozen=True, slots=True)
class Copy:
    """One language of one message: the three string fields the table fixes."""

    subject: str
    body: str
    button: str


@dataclass(frozen=True, slots=True)
class MessageSpec:
    """One catalogue row: which kinds and channels it serves, and where its button goes."""

    key: str
    kind: str
    channels: tuple[str, ...]
    path: str
    ar: Copy
    en: Copy

    def copy_for(self, language: str) -> Copy:
        return self.ar if language == "ar" else self.en


@dataclass(frozen=True, slots=True)
class Rendered:
    """A message ready for the transport, in one language, with its plain-text alternative."""

    key: str
    kind: str
    language: str
    direction: str
    subject: str
    text: str
    html: str
    path: str


@dataclass(frozen=True, slots=True)
class DigestRow:
    """One overdue learner in N-7; every field is already formatted for the language."""

    employee: str
    course: str
    due: str
    days: int
    progress: str


SPECS: tuple[MessageSpec, ...] = (
    MessageSpec(
        key="N-1",
        kind="course_assigned",
        channels=("email", "in_app"),
        path="/my/",
        ar=Copy(
            subject="تم إسناد دورة إليك: {course_title}",
            body="أُسندت إليك دورة {course_title} في أكاديمية {org}. موعد الاستحقاق: {due_date}.",
            button="ابدأ الدورة",
        ),
        en=Copy(
            subject="A course has been assigned to you: {course_title}",
            body="{course_title} was assigned to you in {org} Academy. Due: {due_date}.",
            button="Start course",
        ),
    ),
    MessageSpec(
        key="N-2",
        kind="course_completed",
        channels=("email", "in_app"),
        path="/my/?status=completed",
        ar=Copy(
            subject="أكملت دورة {course_title}",
            body="أتممت دورة {course_title} بنجاح. يمكنك مراجعة محتواها في أي وقت.",
            button="الدورات التي أكملتها",
        ),
        en=Copy(
            subject="You completed {course_title}",
            body="You finished {course_title} successfully. You can revisit the content any time.",
            button="Completed courses",
        ),
    ),
    MessageSpec(
        key="N-3",
        kind="learner_completed",
        channels=("in_app",),
        path="/manage/team/",
        ar=Copy(
            subject="أكمل {learner_name} دورة {course_title}",
            body="أتمّ {learner_name} الدورة في {completed_date}.",
            button="تدريب فريقي",
        ),
        en=Copy(
            subject="{learner_name} completed {course_title}",
            body="{learner_name} finished the course on {completed_date}.",
            button="Team training",
        ),
    ),
    MessageSpec(
        key="N-4",
        kind="due_minus_3",
        channels=("email",),
        path="/my/",
        ar=Copy(
            subject="تبقّى 3 أيام لإكمال {course_title}",
            body="يستحق إكمال دورة {course_title} في {due_date}. تقدّمك الحالي {progress}%.",
            button="أكمل الآن",
        ),
        en=Copy(
            subject="3 days left to finish {course_title}",
            body="{course_title} is due on {due_date}. Your progress is {progress}%.",
            button="Continue",
        ),
    ),
    MessageSpec(
        key="N-5",
        kind="due",
        channels=("email",),
        path="/my/",
        ar=Copy(
            subject="دورة {course_title} مستحقة اليوم",
            body="موعد إكمال دورة {course_title} هو اليوم. تقدّمك الحالي {progress}%.",
            button="أكمل الآن",
        ),
        en=Copy(
            subject="{course_title} is due today",
            body="{course_title} is due today. Your progress is {progress}%.",
            button="Continue",
        ),
    ),
    MessageSpec(
        key="N-6",
        kind="due_plus_1",
        channels=("email",),
        path="/my/",
        ar=Copy(
            subject="تأخّرت دورة {course_title} يوماً واحداً",
            body=(
                "كان موعد إكمال دورة {course_title} في {due_date}. أكملها لتجنّب التصعيد إلى مديرك."
            ),
            button="أكمل الآن",
        ),
        en=Copy(
            subject="{course_title} is one day overdue",
            body=(
                "{course_title} was due on {due_date}. "
                "Finish it to avoid escalation to your manager."
            ),
            button="Continue",
        ),
    ),
    MessageSpec(
        key="N-7",
        kind="manager_escalation",
        channels=("email", "in_app"),
        path="/manage/team/",
        ar=Copy(
            subject="ملخّص تدريب الفريق المتأخر",
            body="تجاوز {count} من فريقك موعد إكمال التدريب بثلاثة أيام أو أكثر.",
            button="افتح صفحة تدريب فريقي",
        ),
        en=Copy(
            subject="Your team's overdue training",
            body="{count} members of your team are three or more days overdue on their training.",
            button="Open team training",
        ),
    ),
)

#: Kind → spec. The kinds are the ones ``docs/domain-model.md`` §2.11–§2.12 fixes; the reminder
#: kinds live in the same map because they render the same way.
SPECS_BY_KIND: dict[str, MessageSpec] = {spec.kind: spec for spec in SPECS}


def spec_for(kind: str) -> MessageSpec:
    """The catalogue row for ``kind``; an unknown kind is a programming error, not a 4xx."""
    try:
        return SPECS_BY_KIND[kind]
    except KeyError:
        raise KeyError(f"no message copy for kind {kind!r}") from None


def _fields(template: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(template) if name}


def required_variables(kind: str) -> set[str]:
    """Every variable the copy for ``kind`` names, in both languages."""
    spec = spec_for(kind)
    names: set[str] = set()
    for copy in (spec.ar, spec.en):
        names |= _fields(copy.subject)
        names |= _fields(copy.body)
        names |= _fields(copy.button)
    return names


def _fill(template: str, variables: Mapping[str, str], what: str) -> str:
    missing = sorted(_fields(template) - set(variables))
    if missing:
        raise KeyError(f"{what} is missing {', '.join(missing)}")
    filled = template.format_map(dict(variables))
    if "{" in filled or "}" in filled:
        raise ValueError(f"{what} still contains a placeholder after substitution")
    return filled


def brand(language: str, organization_name: str) -> str:
    """The brand line the artifact prints at the top of every message."""
    return f"أكاديمية {organization_name}" if language == "ar" else f"{organization_name} Academy"


def _normalize(language: str) -> str:
    return language if language in LANGUAGES else "ar"


def render(
    kind: str,
    *,
    language: str,
    organization_name: str,
    variables: Mapping[str, str],
    url: str | None = None,
    now: datetime | None = None,
) -> Rendered:
    """Render one catalogue message, refusing a subject the transport would cut off."""
    spec = spec_for(kind)
    language = _normalize(language)
    copy = spec.copy_for(language)
    subject = _fill(copy.subject, variables, "subject")
    if len(subject) > MAX_SUBJECT:
        raise ValueError(f"subject for {spec.key} is {len(subject)} characters (max {MAX_SUBJECT})")
    body = _fill(copy.body, variables, "body")
    button = _fill(copy.button, variables, "button")
    brand_name = brand(language, organization_name)
    context = {
        "language": language,
        "direction": DIRECTIONS[language],
        "brand": brand_name,
        "subject": subject,
        "body": body,
        "button": button,
        "url": url or spec.path,
        "footer": f"{brand_name} · {(now or timezone.now()).year}",
    }
    return Rendered(
        key=spec.key,
        kind=kind,
        language=language,
        direction=DIRECTIONS[language],
        subject=subject,
        text=render_to_string(MESSAGE_TEXT_TEMPLATE, context),
        html=render_to_string(MESSAGE_TEMPLATE, context),
        path=url or spec.path,
    )


def render_digest(
    *,
    language: str,
    organization_name: str,
    rows: Sequence[DigestRow],
    url: str,
    now: datetime | None = None,
) -> Rendered:
    """N-7: the approved artifact with the rows, the count and the footer injected."""
    language = _normalize(language)
    spec = spec_for("manager_escalation")
    copy = spec.copy_for(language)
    brand_name = brand(language, organization_name)
    context = {
        "language": language,
        "direction": DIRECTIONS[language],
        "brand": brand_name,
        "heading": copy.subject,
        "intro": copy.body.format_map({"count": str(len(rows))}),
        "button": copy.button,
        "headers": (
            ("الموظف", "الدورة", "الاستحقاق", "أيام التأخر", "التقدم")
            if language == "ar"
            else ("Employee", "Course", "Due", "Days overdue", "Progress")
        ),
        "rows": [
            {
                "employee": row.employee,
                "course": row.course,
                "due": row.due,
                "days": row.days,
                "progress": row.progress,
            }
            for row in rows
        ],
        "url": url,
        "footer": f"{brand_name} · {(now or timezone.now()).year}",
    }
    return Rendered(
        key=spec.key,
        kind=spec.kind,
        language=language,
        direction=DIRECTIONS[language],
        subject=copy.subject,
        text=render_to_string(DIGEST_TEXT_TEMPLATE, context),
        html=render_to_string(DIGEST_TEMPLATE, context),
        path=url,
    )


__all__ = [
    "DIRECTIONS",
    "LANGUAGES",
    "MAX_SUBJECT",
    "Copy",
    "DigestRow",
    "MessageSpec",
    "Rendered",
    "SPECS",
    "SPECS_BY_KIND",
    "brand",
    "render",
    "render_digest",
    "required_variables",
    "spec_for",
]
