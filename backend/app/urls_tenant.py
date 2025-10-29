from api.health import health_check, metrics, readiness_check
from api.multi_tenant_auth import MultiTenantLoginView
from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    # Health & Monitoring endpoints (no auth required)
    path("health/", health_check, name="health_check"),
    path("health/ready/", readiness_check, name="readiness_check"),
    path("metrics/", metrics, name="metrics"),
    # Multi-tenant centralized authentication (accessible from tenant subdomains)
    path("api/auth/login/", MultiTenantLoginView.as_view(), name="multi_tenant_login"),
    # API endpoints
    path("api/", include("api.urls")),
    path("api/pay/", include("payments.urls")),
    path("api/billing/", include("payments.billing_urls")),
    path("api/", include("monitors.urls")),
]

urlpatterns += [
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("", lambda r: HttpResponse("tenant OK"), name="tenant-home"),
]
