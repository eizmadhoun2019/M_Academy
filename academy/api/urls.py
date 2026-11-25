"""`/api/v1/academy/` routes (``docs/api.md`` §1)."""

from __future__ import annotations

from django.urls import path

from academy.api.grants import GrantListCreateView, GrantRevokeView
from academy.api.views import MeCapabilitiesView

app_name = "academy_api"

urlpatterns = [
    path("me/capabilities/", MeCapabilitiesView.as_view(), name="me-capabilities"),
    path("manage/grants/", GrantListCreateView.as_view(), name="manage-grants"),
    path("manage/grants/<uuid:grant_id>/", GrantRevokeView.as_view(), name="manage-grant"),
]
