"""
Development settings for StatusWatch project.

Optimized for local development with relaxed security and verbose logging.
"""

from modules.core.settings import (
    configure_sentry,
    get_dev_cors_settings,
    get_dev_csrf_trusted_origins,
    get_dev_https_settings,
    get_dev_security_headers,
    get_permissions_policy,
)

from app.settings_base import *  # noqa: F403, F401

# -------------------------------------------------------------------
# Core Development Settings
# -------------------------------------------------------------------
DEBUG = True

# Required for JWT signing
SECRET_KEY = env(  # noqa: F405
    "SECRET_KEY", default="django-insecure-dev-key-CHANGE-ME-IN-PRODUCTION"
)

# Permissive hosts for local development
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".localhost",  # Wildcard for subdomains
    "django-01.local",
    ".django-01.local",
    "statuswatch.local",
    ".statuswatch.local",
]

# -------------------------------------------------------------------
# Tenant Domain Configuration (Development)
# -------------------------------------------------------------------
# Default suffix for tenant subdomains in development
DEFAULT_TENANT_DOMAIN_SUFFIX = env(  # noqa: F405
    "DEFAULT_TENANT_DOMAIN_SUFFIX",
    default="localhost",  # For local Vite dev server (e.g., acme.localhost:5173)
)

# -------------------------------------------------------------------
# JWT Configuration (Development)
# -------------------------------------------------------------------
SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY  # noqa: F405

# -------------------------------------------------------------------
# CORS Configuration (Development - Permissive)
# -------------------------------------------------------------------
# Apply shared dev defaults so origin lists stay consistent across environments.
globals().update(get_dev_cors_settings(env))  # noqa: F405

# -------------------------------------------------------------------
# CSRF Configuration (Development)
# -------------------------------------------------------------------
CSRF_TRUSTED_ORIGINS = get_dev_csrf_trusted_origins()

# -------------------------------------------------------------------
# HTTPS/Security Configuration (Development - Relaxed)
# -------------------------------------------------------------------
globals().update(get_dev_https_settings())

# -------------------------------------------------------------------
# Security Headers (Development - Relaxed)
# -------------------------------------------------------------------
globals().update(get_dev_security_headers())
PERMISSIONS_POLICY = get_permissions_policy()

# -------------------------------------------------------------------
# Email Configuration (Development - Console Backend)
# -------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# -------------------------------------------------------------------
# Celery Configuration (Development - Synchronous Execution)
# -------------------------------------------------------------------
# Run Celery tasks synchronously without worker (for development without Celery worker)
# WARNING: Some tasks may fail in eager mode due to schema switching limitations
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# -------------------------------------------------------------------
# Frontend URL (Development - Explicit for localhost)
# -------------------------------------------------------------------
# Override to use localhost:5173 for local development
FRONTEND_URL = env("FRONTEND_URL", default="https://localhost:5173")  # noqa: F405

# -------------------------------------------------------------------
# Logging Configuration (Development - Verbose)
# -------------------------------------------------------------------
# Override monitors.audit logger to DEBUG level for development
LOGGING["loggers"]["monitors.audit"]["level"] = "DEBUG"  # type: ignore  # noqa: F405

# -------------------------------------------------------------------
# Development-Specific Settings
# -------------------------------------------------------------------
# No Stripe validation in development (allow empty keys for testing)
_sentry_cfg = configure_sentry(env, default_environment="development")  # noqa: F405
SENTRY_DSN = _sentry_cfg["dsn"]
SENTRY_TRACES_SAMPLE_RATE = _sentry_cfg["traces_sample_rate"]
if "environment" in _sentry_cfg:
    SENTRY_ENVIRONMENT = _sentry_cfg["environment"]
