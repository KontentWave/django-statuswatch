"""
Production settings for StatusWatch project.

Optimized for production deployment with strict security and validation.
"""

import logging
import sys

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration

from app.settings_base import *  # noqa: F403, F401

# -------------------------------------------------------------------
# Core Production Settings
# -------------------------------------------------------------------
DEBUG = env.bool("DEBUG", default=False)  # noqa: F405

# -------------------------------------------------------------------
# Secret Key Validation (Production)
# -------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY", default=None)  # noqa: F405

if not SECRET_KEY:
    raise ValueError(
        "SECRET_KEY is not set. Please set it in your .env file or environment variables.\n"
        "Generate a secure key with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
    )

if SECRET_KEY.startswith("django-insecure"):
    raise ValueError(
        "Cannot use 'django-insecure' SECRET_KEY in production (DEBUG=False).\n"
        "Generate a secure key with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
    )

# Validate SECRET_KEY length and complexity
if len(SECRET_KEY) < 50:
    raise ValueError(
        "SECRET_KEY must be at least 50 characters long in production.\n"
        "Generate a secure key with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
    )

# -------------------------------------------------------------------
# Allowed Hosts (Production - Strict)
# -------------------------------------------------------------------
# Must be explicitly set in production
ALLOWED_HOSTS = env.list(  # noqa: F405
    "ALLOWED_HOSTS",
    default=[
        "django-01.local",
        ".django-01.local",
        "statuswatch.local",
        ".statuswatch.local",
    ],
)

# -------------------------------------------------------------------
# Tenant Domain Configuration (Production)
# -------------------------------------------------------------------
# Default suffix for tenant subdomains (e.g., acme.statuswatch.kontentwave.digital)
DEFAULT_TENANT_DOMAIN_SUFFIX = env(  # noqa: F405
    "DEFAULT_TENANT_DOMAIN_SUFFIX",
    default="statuswatch.kontentwave.digital",
)

# -------------------------------------------------------------------
# JWT Configuration (Production)
# -------------------------------------------------------------------
SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY  # noqa: F405

# -------------------------------------------------------------------
# CORS Configuration (Production - Strict)
# -------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = False  # Never allow all origins in production
CORS_ALLOWED_ORIGINS = env.list(  # noqa: F405
    "CORS_ALLOWED_ORIGINS",
    default=[
        "https://statuswatch.local",
        "https://www.statuswatch.local",
    ],
)

CORS_ALLOWED_ORIGIN_REGEXES = env.list(  # noqa: F405
    "CORS_ALLOWED_ORIGIN_REGEXES",
    default=[
        r"^https://[a-z0-9-]+\.django-01\.local$",
        r"^https://[a-z0-9-]+\.statuswatch\.local$",
    ],
)

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# -------------------------------------------------------------------
# CSRF Configuration (Production)
# -------------------------------------------------------------------
CSRF_TRUSTED_ORIGINS = env.list(  # noqa: F405
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "https://statuswatch.local",
        "https://*.statuswatch.local",
        "https://django-01.local",
        "https://*.django-01.local",
    ],
)

# -------------------------------------------------------------------
# HTTPS/Security Configuration (Production - Strict)
# -------------------------------------------------------------------
# Enforce HTTPS in production
ENFORCE_HTTPS = env.bool("ENFORCE_HTTPS", default=True)  # noqa: F405
SECURE_SSL_REDIRECT = ENFORCE_HTTPS

# HTTP Strict Transport Security (HSTS)
if ENFORCE_HTTPS:
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=3600)  # noqa: F405
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(  # noqa: F405
        "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True
    )
    SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)  # noqa: F405
else:
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# Trust X-Forwarded-Proto from reverse proxy
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Cookie security (strict in production)
SESSION_COOKIE_SECURE = ENFORCE_HTTPS
CSRF_COOKIE_SECURE = ENFORCE_HTTPS
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# -------------------------------------------------------------------
# Security Headers (Production - Strict)
# -------------------------------------------------------------------
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"  # noqa: F405
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# Strict CSP for production
CSP_DEFAULT_SRC: tuple[str, ...] = ("'self'",)
CSP_SCRIPT_SRC: tuple[str, ...] = (
    "'self'",
    "'unsafe-inline'",
)  # TODO: Remove unsafe-inline when frontend uses nonces
CSP_STYLE_SRC: tuple[str, ...] = ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com")
CSP_FONT_SRC: tuple[str, ...] = ("'self'", "https://fonts.gstatic.com")
CSP_IMG_SRC: tuple[str, ...] = ("'self'", "data:", "https:")
CSP_CONNECT_SRC: tuple[str, ...] = ("'self'", "https://api.stripe.com")  # Allow Stripe API calls
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_BASE_URI = ("'self'",)
CSP_FORM_ACTION = ("'self'",)

# Permissions Policy (strict - disable risky features)
PERMISSIONS_POLICY: dict[str, list[str]] = {  # noqa: F405
    "geolocation": [],
    "camera": [],
    "microphone": [],
    "payment": [],
    "usb": [],
    "magnetometer": [],
    "accelerometer": [],
    "gyroscope": [],
}

# -------------------------------------------------------------------
# Stripe Validation (Production)
# -------------------------------------------------------------------
# Skip validation for management commands that don't need Stripe
management_commands_skip_validation = [
    "makemigrations",
    "migrate",
    "shell",
    "dbshell",
    "showmigrations",
    "sqlmigrate",
    "createsuperuser",
    "collectstatic",
]

should_validate = not any(cmd in sys.argv for cmd in management_commands_skip_validation)

if should_validate:
    if not STRIPE_PUBLIC_KEY or not STRIPE_PUBLIC_KEY.startswith("pk_"):  # noqa: F405
        raise ValueError(
            "STRIPE_PUBLIC_KEY must be set and start with 'pk_' in production.\n"
            "Get your keys from https://dashboard.stripe.com/apikeys"
        )
    if not STRIPE_SECRET_KEY or not STRIPE_SECRET_KEY.startswith("sk_"):  # noqa: F405
        raise ValueError(
            "STRIPE_SECRET_KEY must be set and start with 'sk_' in production.\n"
            "Get your keys from https://dashboard.stripe.com/apikeys"
        )
    if not STRIPE_WEBHOOK_SECRET or not STRIPE_WEBHOOK_SECRET.startswith("whsec_"):  # noqa: F405
        raise ValueError(
            "STRIPE_WEBHOOK_SECRET must be set and start with 'whsec_' in production.\n"
            "Get your keys from https://dashboard.stripe.com/webhooks"
        )

# -------------------------------------------------------------------
# Email Configuration (Production - SMTP)
# -------------------------------------------------------------------
EMAIL_BACKEND = env(  # noqa: F405
    "EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend"
)

# -------------------------------------------------------------------
# Sentry Configuration (Production - Error & Performance Monitoring)
# -------------------------------------------------------------------
SENTRY_DSN = env("SENTRY_DSN", default="")  # noqa: F405
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", default="production")  # noqa: F405
SENTRY_TRACES_SAMPLE_RATE = env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1)  # noqa: F405

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        # Enable performance monitoring
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        # Capture 10% of transactions for performance monitoring in production
        profiles_sample_rate=0.1,
        # Integrations
        integrations=[
            DjangoIntegration(
                transaction_style="url",
                middleware_spans=True,
                signals_spans=True,
            ),
            CeleryIntegration(
                monitor_beat_tasks=True,
                exclude_beat_tasks=[],
            ),
            RedisIntegration(),
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,
            ),
        ],
        # Customize what gets sent to Sentry
        send_default_pii=False,
        attach_stacktrace=True,
        enable_tracing=True,
        # Filter out health check requests
        traces_sampler=lambda sampling_context: (
            0.0
            if sampling_context.get("wsgi_environ", {}).get("PATH_INFO", "").startswith("/health")
            else SENTRY_TRACES_SAMPLE_RATE
        ),
        # Release tracking
        release=env("SENTRY_RELEASE", default=None),  # noqa: F405
        # Before send hook to scrub sensitive data
        before_send=lambda event, hint: _scrub_sentry_event(event, hint),
    )


def _scrub_sentry_event(event, hint):
    """
    Scrub sensitive data from Sentry events before sending.
    """
    # Remove sensitive headers
    if "request" in event:
        headers = event["request"].get("headers", {})
        sensitive_headers = ["Authorization", "Cookie", "X-CSRF-Token"]
        for header in sensitive_headers:
            if header in headers:
                headers[header] = "[Filtered]"

    # Remove sensitive environment variables
    if "contexts" in event and "runtime" in event["contexts"]:
        env_vars = event["contexts"]["runtime"].get("env", {})
        sensitive_keys = [
            "SECRET_KEY",
            "DATABASE_URL",
            "REDIS_URL",
            "STRIPE_SECRET_KEY",
            "EMAIL_HOST_PASSWORD",
        ]
        for key in sensitive_keys:
            if key in env_vars:
                env_vars[key] = "[Filtered]"

    return event
