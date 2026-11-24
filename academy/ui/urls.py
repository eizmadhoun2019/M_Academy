"""Preview routes, mounted under ``/academy/`` (docs/api.md §10)."""

from __future__ import annotations

from django.urls import path
from django.views.generic import RedirectView

from academy.ui.views import preview_showcase

app_name = "academy_ui"

urlpatterns = [
    path(
        "preview/",
        RedirectView.as_view(url="/academy/preview/ar/", permanent=False),
        name="preview",
    ),
    path("preview/<str:lang>/", preview_showcase, name="preview_showcase"),
]
