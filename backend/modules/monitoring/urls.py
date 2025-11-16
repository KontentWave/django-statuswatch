"""Monitoring API routes exposed by the modular monitoring package."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import EndpointViewSet

router = DefaultRouter()
router.register("endpoints", EndpointViewSet, basename="endpoint")

urlpatterns = router.urls

__all__ = ["urlpatterns", "router"]
