"""Reusable URL helpers shared by public and tenant routers."""

from __future__ import annotations

from api.health import health_check, metrics, readiness_check
from api.multi_tenant_auth import MultiTenantLoginView
from api.token_refresh import MultiTenantTokenRefreshView
from api.views import validate_domain_for_tls
from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views import View
from rest_framework_simplejwt.views import TokenVerifyView


def admin_urlpatterns():
    return [path(settings.ADMIN_URL, admin.site.urls)]


def health_urlpatterns():
    return [
        path("healthz", health_check, name="healthz"),
        path("health/", health_check, name="health_check"),
        path("health/ready/", readiness_check, name="readiness_check"),
        path("metrics/", metrics, name="metrics"),
    ]


def internal_validation_urlpatterns():
    return [
        path(
            "api/internal/validate-domain/",
            validate_domain_for_tls,
            name="validate_domain_tls",
        )
    ]


def multi_tenant_login_urlpatterns():
    return [
        path(
            "api/auth/login/",
            MultiTenantLoginView.as_view(),
            name="multi_tenant_login",
        )
    ]


def payment_urlpatterns():
    return [
        path("api/pay/", include("payments.urls")),
        path("api/billing/", include("payments.billing_urls")),
    ]


def jwt_token_urlpatterns(
    token_obtain_view: type[View] | None,
    *,
    include_refresh: bool = True,
    include_verify: bool = False,
):
    """Build JWT token endpoints with shared refresh/verify wiring."""

    patterns = []
    if token_obtain_view is not None:
        patterns.append(
            path(
                "api/auth/token/",
                token_obtain_view.as_view(),
                name="token_obtain_pair",
            )
        )

    if include_refresh:
        patterns.append(
            path(
                "api/auth/token/refresh/",
                MultiTenantTokenRefreshView.as_view(),
                name="token_refresh",
            )
        )

    if include_verify:
        patterns.append(
            path(
                "api/auth/token/verify/",
                TokenVerifyView.as_view(),
                name="token_verify",
            )
        )

    return patterns


__all__ = [
    "admin_urlpatterns",
    "health_urlpatterns",
    "internal_validation_urlpatterns",
    "payment_urlpatterns",
    "multi_tenant_login_urlpatterns",
    "jwt_token_urlpatterns",
]
