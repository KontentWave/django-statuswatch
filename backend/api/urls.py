from django.urls import path

from .views import PingView, RegistrationView, SecurePingView

urlpatterns = [
    path("auth/register/", RegistrationView.as_view(), name="api-register"),
    path('secure-ping/', SecurePingView.as_view(), name='api-secure-ping'),
    path("ping/", PingView.as_view(), name="api-ping"),
]
