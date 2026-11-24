"""The three error pages: one canvas and card, no navigation and no data."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext as _


def _page(request: HttpRequest, *, status: int, title: str, message: str) -> HttpResponse:
    return render(
        request,
        "academy/error.html",
        {"status_code": status, "title": title, "message": message},
        status=status,
    )


def forbidden(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return _page(
        request,
        status=403,
        title=_("You do not have access to this page"),
        message=_("If you believe this is a mistake, contact your Academy administrator."),
    )


def not_found(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return _page(
        request,
        status=404,
        title=_("This page does not exist"),
        message=_("The link may be old, or the page may have moved. Return to your dashboard."),
    )


def server_error(request: HttpRequest) -> HttpResponse:
    return _page(
        request,
        status=500,
        title=_("Something went wrong"),
        message=_(
            "The action did not complete. Try again; if it repeats, contact your administrator."
        ),
    )
