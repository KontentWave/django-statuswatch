from django.urls import path

from .views import PingView, RegistrationView, SecurePingView, verify_email, resend_verification_email

urlpatterns = [
    path("auth/register/", RegistrationView.as_view(), name="api-register"),
    path("auth/verify-email/<uuid:token>/", verify_email, name="verify-email"),
    path("auth/resend-verification/", resend_verification_email, name="resend-verification"),
    path('secure-ping/', SecurePingView.as_view(), name='api-secure-ping'),
    path("ping/", PingView.as_view(), name="api-ping"),
]
