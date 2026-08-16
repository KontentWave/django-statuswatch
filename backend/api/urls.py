from django.urls import path

from .views import (
    CurrentUserView,
    LogoutView,
    PingView,
    RegistrationView,
    SecurePingView,
    expire_verification_token,
    latest_verification_token,
    resend_verification_email,
    resend_verification_email_debug,
    verify_email,
)

urlpatterns = [
    path("auth/register/", RegistrationView.as_view(), name="api-register"),
    path("auth/logout/", LogoutView.as_view(), name="api-logout"),
    path("auth/me/", CurrentUserView.as_view(), name="api-current-user"),
    path("auth/verify-email/", verify_email, name="verify-email"),
    path("auth/resend-verification/", resend_verification_email, name="resend-verification"),
    path(
        "debug/latest-verification-token/",
        latest_verification_token,
        name="debug-latest-verification-token",
    ),
    path(
        "debug/expire-verification-token/",
        expire_verification_token,
        name="debug-expire-verification-token",
    ),
    path(
        "debug/resend-verification/",
        resend_verification_email_debug,
        name="debug-resend-verification",
    ),
    path("secure-ping/", SecurePingView.as_view(), name="api-secure-ping"),
    path("ping/", PingView.as_view(), name="api-ping"),
]
