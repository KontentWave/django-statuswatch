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


def home(_):
    return HttpResponse("public OK")


urlpatterns = (
    admin_urlpatterns()
    + health_urlpatterns()
    + internal_validation_urlpatterns()
    + multi_tenant_login_urlpatterns()
    + payment_urlpatterns()
    + [path("api/", include("api.urls"))]
)

urlpatterns += jwt_token_urlpatterns(TokenObtainPairWithLoggingView)
urlpatterns += [path("", home)]
