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
from rest_framework_simplejwt.views import TokenObtainPairView

urlpatterns = (
    admin_urlpatterns()
    + health_urlpatterns()
    + internal_validation_urlpatterns()
    + multi_tenant_login_urlpatterns()
    + payment_urlpatterns()
    + [
        path("api/", include("api.urls")),
        path("api/", include("monitors.urls")),
    ]
)

urlpatterns += jwt_token_urlpatterns(TokenObtainPairView, include_verify=True)
urlpatterns += [path("", lambda r: HttpResponse("tenant OK"), name="tenant-home")]
