"""`/api/v1/academy/` routes (``docs/api.md`` §1)."""

from __future__ import annotations

from django.urls import path

from academy.api.views import MeCapabilitiesView

app_name = "academy_api"

urlpatterns = [
    path("me/capabilities/", MeCapabilitiesView.as_view(), name="me-capabilities"),
]
