"""
Custom throttling classes for API rate limiting.

Protects against spam, DoS attacks, and automated abuse.
"""

from django.conf import settings
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class RateLimitingToggleMixin:
    """Bypass throttles entirely when rate limiting is disabled in settings."""

    @staticmethod
    def _is_enabled() -> bool:
        return getattr(settings, "API_RATE_LIMITING_ENABLED", True)

    def allow_request(self, request, view):  # type: ignore[override]
        if not self._is_enabled():
            return True
        return super().allow_request(request, view)


class RegistrationRateThrottle(RateLimitingToggleMixin, AnonRateThrottle):
    """
    Strict rate limit for user registration endpoint.

    Prevents spam account creation and automated attacks.
    Default: 5 requests per hour per IP address.

    Configure in settings.py:
        REST_FRAMEWORK = {
            'DEFAULT_THROTTLE_RATES': {
                'registration': '5/hour',
            }
        }
    """

    scope = "registration"


class LoginRateThrottle(RateLimitingToggleMixin, AnonRateThrottle):
    """
    Rate limit for login attempts.

    Protects against brute-force password attacks.
    Default: 10 requests per hour per IP address.

    Configure in settings.py:
        REST_FRAMEWORK = {
            'DEFAULT_THROTTLE_RATES': {
                'login': '10/hour',
            }
        }
    """

    scope = "login"


class BurstRateThrottle(RateLimitingToggleMixin, AnonRateThrottle):
    """
    Short-term burst protection for anonymous users.

    Prevents rapid-fire requests from scripts/bots.
    Default: 20 requests per minute.

    Configure in settings.py:
        REST_FRAMEWORK = {
            'DEFAULT_THROTTLE_RATES': {
                'burst': '20/min',
            }
        }
    """

    scope = "burst"


class SustainedRateThrottle(RateLimitingToggleMixin, AnonRateThrottle):
    """
    Long-term rate limit for anonymous users.

    Prevents sustained abuse over longer periods.
    Default: 100 requests per day.

    Configure in settings.py:
        REST_FRAMEWORK = {
            'DEFAULT_THROTTLE_RATES': {
                'sustained': '100/day',
            }
        }
    """

    scope = "sustained"


class AuthenticatedUserRateThrottle(RateLimitingToggleMixin, UserRateThrottle):
    """
    Rate limit for authenticated users.

    More generous than anonymous limits since users are identified.
    Default: 1000 requests per hour.

    Configure in settings.py:
        REST_FRAMEWORK = {
            'DEFAULT_THROTTLE_RATES': {
                'user': '1000/hour',
            }
        }
    """

    scope = "user"


class BillingRateThrottle(RateLimitingToggleMixin, UserRateThrottle):
    """
    Strict rate limit for billing/checkout endpoints.

    Protects against billing abuse, repeated failed transactions,
    and accidental duplicate subscription attempts.
    Default: 10 requests per hour per authenticated user.

    Configure in settings.py:
        REST_FRAMEWORK = {
            'DEFAULT_THROTTLE_RATES': {
                'billing': '10/hour',
            }
        }
    """

    scope = "billing"
