"""
Production settings for StatusWatch project.

Optimized for production deployment with strict security and validation.
"""

import sys

from modules.core.settings import (
    configure_sentry,
    get_permissions_policy,
    get_prod_cors_settings,
    get_prod_csrf_trusted_origins,
    get_prod_https_settings,
    get_prod_security_headers,
)

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
globals().update(get_prod_cors_settings(env))  # noqa: F405

# -------------------------------------------------------------------
# CSRF Configuration (Production)
# -------------------------------------------------------------------
CSRF_TRUSTED_ORIGINS = get_prod_csrf_trusted_origins(env)  # noqa: F405

# -------------------------------------------------------------------
# HTTPS/Security Configuration (Production - Strict)
# -------------------------------------------------------------------
globals().update(get_prod_https_settings(env))  # noqa: F405

# -------------------------------------------------------------------
# Security Headers (Production - Strict)
# -------------------------------------------------------------------
globals().update(get_prod_security_headers())
PERMISSIONS_POLICY = get_permissions_policy()

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
_sentry_cfg = configure_sentry(env)  # noqa: F405
SENTRY_DSN = _sentry_cfg["dsn"]
SENTRY_TRACES_SAMPLE_RATE = _sentry_cfg["traces_sample_rate"]
if "environment" in _sentry_cfg:
    SENTRY_ENVIRONMENT = _sentry_cfg["environment"]
