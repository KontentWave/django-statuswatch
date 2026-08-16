from api.views import TokenObtainPairWithLoggingView
from django.http import HttpResponse
from django.urls import include, path
from modules.core.urls import (
    admin_urlpatterns,
    health_urlpatterns,
    internal_validation_urlpatterns,
    jwt_token_urlpatterns,
    multi_tenant_login_urlpatterns,
    payment_urlpatterns,
)

urlpatterns = (
    admin_urlpatterns()
    + health_urlpatterns()
    + internal_validation_urlpatterns()
    + multi_tenant_login_urlpatterns()
    + payment_urlpatterns()
    + [
        path("api/", include("api.urls")),
        # Prefer the modular monitoring router but retain shim for legacy callers
        path("api/", include("modules.monitoring.urls")),
    ]
)

urlpatterns += jwt_token_urlpatterns(TokenObtainPairWithLoggingView, include_verify=True)
urlpatterns += [path("", lambda r: HttpResponse("tenant OK"), name="tenant-home")]
