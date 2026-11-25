"""Local sign-in routes, mounted under ``/academy/`` (``docs/api.md`` §10)."""

from __future__ import annotations

from django.urls import path

from academy.access.views import access_denied_view, login_view, logout_view

app_name = "academy_access"

urlpatterns = [
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("access-denied/", access_denied_view, name="access_denied"),
]
