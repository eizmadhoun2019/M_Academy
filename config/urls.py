"""Root URL configuration.

Operational routes plus the versioned Academy API. Web pages arrive with T-013.
"""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView
from rest_framework.permissions import AllowAny

from config.health import healthz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("api/v1/academy/", include("academy.api.urls")),
    # Development/staging only; the production profile disables this route (docs/api.md §9).
    path(
        "api/schema",
        SpectacularAPIView.as_view(permission_classes=[AllowAny], authentication_classes=[]),
        name="openapi-schema",
    ),
]
