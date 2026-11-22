"""Root URL configuration.

Only operational routes exist at T-001. API v1 and web routes arrive with T-011 and T-013.
"""

from django.urls import path
from drf_spectacular.views import SpectacularAPIView

from config.health import healthz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("api/schema", SpectacularAPIView.as_view(), name="openapi-schema"),
]
