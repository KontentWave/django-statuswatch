from api.health import health_check, metrics, readiness_check
from api.multi_tenant_auth import MultiTenantLoginView
from api.token_refresh import MultiTenantTokenRefreshView
from api.views import TokenObtainPairWithLoggingView
from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path


def home(_):
    return HttpResponse("public OK")


urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    # Health & Monitoring endpoints (no auth required)
    path("health/", health_check, name="health_check"),
    path("health/ready/", readiness_check, name="readiness_check"),
    path("metrics/", metrics, name="metrics"),
    # Multi-tenant centralized authentication (NEW - works across all tenants)
    path("api/auth/login/", MultiTenantLoginView.as_view(), name="multi_tenant_login"),
    # JWT Authentication endpoints (OLD - only works if user is in public schema)
    path("api/auth/token/", TokenObtainPairWithLoggingView.as_view(), name="token_obtain_pair"),
    path(
        "api/auth/token/refresh/",
        MultiTenantTokenRefreshView.as_view(),
        name="token_refresh",
    ),
    # API endpoints (registration, verification, ping)
    path("api/", include("api.urls")),
    # Payment endpoints
    path("api/pay/", include("payments.urls")),
    path("api/billing/", include("payments.billing_urls")),
    path("", home),
]
