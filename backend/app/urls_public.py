from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

def home(_): return HttpResponse("public OK")

urlpatterns = [
    path("admin/", admin.site.urls),
    # JWT Authentication endpoints
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # API endpoints (registration, verification, ping)
    path("api/", include("api.urls")),
    # Payment endpoints
    path("api/pay/", include("payments.urls")),
    path("", home),
]
