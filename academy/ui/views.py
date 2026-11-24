"""The preview showcase: the one place that renders the shell without a session.

It exists only in a development profile — ``docs/ui/wireframes.md`` §Preview routes — and it
reads no model, so it cannot leak one organization's rows to another.
"""

from __future__ import annotations

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import translation
from django.utils.translation import gettext_lazy

#: Sample states every screen has to render (docs/ui/screen-specification.md §5).
STATES = ("loading", "empty", "error", "forbidden", "slow")
LANGUAGES = ("ar", "en")

#: (heading, ((anchor, label), ...)) — labels are lazy so the preview language decides them.
NAV_SECTIONS = (
    (
        gettext_lazy("Showcase"),
        (
            ("shell", gettext_lazy("Shell")),
            ("tokens", gettext_lazy("Tokens")),
            ("typography", gettext_lazy("Typography")),
            ("buttons", gettext_lazy("Buttons")),
            ("statuses", gettext_lazy("Statuses")),
        ),
    ),
    (
        gettext_lazy("Patterns"),
        (
            ("cards", gettext_lazy("Cards")),
            ("tables", gettext_lazy("Tables")),
            ("forms", gettext_lazy("Forms")),
            ("dialogs", gettext_lazy("Dialogs")),
            ("states", gettext_lazy("States")),
        ),
    ),
)


def preview_showcase(request: HttpRequest, lang: str = "ar") -> HttpResponse:
    """Render the component showcase in one language and one sample state."""
    if not settings.DEBUG:
        raise Http404("The preview exists only in a development profile.")
    if lang not in LANGUAGES:
        raise Http404(f"Unknown preview language {lang!r}.")
    state = request.GET.get("state")
    if state is not None and state not in STATES:
        raise Http404(f"Unknown preview state {state!r}.")

    with translation.override(lang):
        return render(
            request,
            "academy/preview/showcase.html",
            {
                "state": state or "ready",
                "state_options": STATES,
                "languages": LANGUAGES,
                "nav_sections": NAV_SECTIONS,
                "other_language": "en" if lang == "ar" else "ar",
            },
        )
