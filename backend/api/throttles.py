"""
Custom throttling classes for API rate limiting.

Protects against spam, DoS attacks, and automated abuse.
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class RegistrationRateThrottle(AnonRateThrottle):
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


class LoginRateThrottle(AnonRateThrottle):
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


class BurstRateThrottle(AnonRateThrottle):
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


class SustainedRateThrottle(AnonRateThrottle):
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


class AuthenticatedUserRateThrottle(UserRateThrottle):
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


class BillingRateThrottle(UserRateThrottle):
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
