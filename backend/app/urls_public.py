from api.health import health_check, metrics, readiness_check
from api.views import TokenObtainPairWithLoggingView
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView


def home(_):
    return HttpResponse("public OK")


urlpatterns = [
    path("admin/", admin.site.urls),
    # Health & Monitoring endpoints (no auth required)
    path("health/", health_check, name="health_check"),
    path("health/ready/", readiness_check, name="readiness_check"),
    path("metrics/", metrics, name="metrics"),
    # JWT Authentication endpoints
    path("api/auth/token/", TokenObtainPairWithLoggingView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # API endpoints (registration, verification, ping)
    path("api/", include("api.urls")),
    # Payment endpoints
    path("api/pay/", include("payments.urls")),
    path("", home),
]
