"""X1 sign-in, sign-out and the X2 access-denied page, in standalone mode only."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from academy.access.forms import DevelopmentLoginForm
from academy.access.principals import SESSION_KEY, access_mode
from academy.access.throttles import throttle_exceeded


def login_enabled() -> bool:
    """The stub exists only where a local sign-in is the documented path (D-026)."""
    return access_mode() == "standalone" and bool(getattr(settings, "DEVELOPMENT_LOGIN", False))


def login_view(request: HttpRequest) -> HttpResponse:
    if not login_enabled():
        raise Http404("Local sign-in is not enabled in this deployment.")
    if throttle_exceeded(request, "login", "10/min"):
        return render(
            request,
            "academy/login.html",
            {"form": DevelopmentLoginForm(), "throttled": True},
            status=429,
        )

    if request.method == "POST":
        form = DevelopmentLoginForm(request.POST)
        if form.is_valid():
            request.session.cycle_key()
            department = form.cleaned_data["department_ref"]
            request.session[SESSION_KEY] = {
                "user_ref": form.cleaned_data["user_ref"],
                "roles": [form.cleaned_data["role"]],
                "department_refs": [department] if department else [],
                "is_active": not form.cleaned_data["simulate_inactive"],
            }
            return redirect(_landing_url(request))
    else:
        form = DevelopmentLoginForm()
    return render(request, "academy/login.html", {"form": form})


def logout_view(request: HttpRequest) -> HttpResponse:
    if not login_enabled():
        raise Http404("Local sign-in is not enabled in this deployment.")
    if request.method != "POST":
        return HttpResponse(status=405)
    request.session.flush()
    return redirect("academy_access:login")


def access_denied_view(request: HttpRequest) -> HttpResponse:
    """A direct visit shows the same page the middleware renders (screen X2)."""
    access: Any = getattr(request, "academy_access", None)
    reason = getattr(access, "denied_reason", None) or "inactive"
    return render(request, "academy/access_denied.html", {"reason": reason}, status=403)


def _landing_url(request: HttpRequest) -> str:
    """L1 replaces this landing when the dashboard screen lands.

    The screen showcase exists only while ``DEBUG`` is on; without it the sign-in page is the
    only reachable page until L1 ships.
    """
    if settings.DEBUG:
        return reverse("academy_ui:preview_showcase", kwargs={"lang": "ar"})
    return reverse("academy_access:login")
