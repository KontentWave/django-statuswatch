"""
Django settings for app project (Django 5 + DRF + Celery + django-tenants).
"""

import logging
from collections import OrderedDict
from datetime import timedelta
from pathlib import Path

import environ
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration

# -------------------------------------------------------------------
# Base & env
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

env = environ.Env()
# Look for .env in backend/ first, then project root
env_file = BASE_DIR / ".env"
if not env_file.exists():
    env_file = BASE_DIR.parent / ".env"
environ.Env.read_env(env_file)

# -------------------------------------------------------------------
# Core
# -------------------------------------------------------------------
DEBUG = env.bool("DEBUG", default=False)

SECRET_KEY = env("SECRET_KEY", default=None)
if not SECRET_KEY:
    raise ValueError(
        "SECRET_KEY is not set. Please set it in your .env file or environment variables.\n"
        "Generate a secure key with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
    )
if SECRET_KEY.startswith("django-insecure"):
    if not DEBUG:
        raise ValueError(
            "Cannot use 'django-insecure' SECRET_KEY in production (DEBUG=False).\n"
            "Generate a secure key with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
        )

# Additional secret validation for production
if not DEBUG:
    # Validate SECRET_KEY length and complexity
    if len(SECRET_KEY) < 50:
        raise ValueError(
            "SECRET_KEY must be at least 50 characters long in production.\n"
            "Generate a secure key with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
        )

# include wildcard for tenant subdomains like acme.django-01.local
ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".localhost", "django-01.local", "acme.django-01.local"]

# -------------------------------------------------------------------
# django-tenants
# -------------------------------------------------------------------
TENANT_MODEL = "tenants.Client"  # app_label.ModelName
DOMAIN_MODEL = "tenants.Domain"

SHARED_APPS = (
    "django_tenants",  # must be first
    "django.contrib.contenttypes",  # required by tenants
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",  # CORS support
    "tenants",  # your tenants app (Client/Domain models)
)

TENANT_APPS = (
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework_simplejwt.token_blacklist",  # Per-tenant JWT blacklist tables
    # your tenant-facing apps:
    "api",
    "monitors",
)

# Final INSTALLED_APPS: shared first, then tenant apps (no duplicates)
INSTALLED_APPS = list(SHARED_APPS) + [a for a in TENANT_APPS if a not in SHARED_APPS]

DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

# Use separate URLConfs for public (root schema) vs tenant schemas
PUBLIC_SCHEMA_URLCONF = "app.urls_public"
ROOT_URLCONF = "app.urls_tenant"

# NOTE: MIDDLEWARE is defined later in this file (after tenant configuration)
# See line ~240 for the actual MIDDLEWARE configuration

STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


# -------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # you already have templates/welcome.html
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "app.wsgi.application"

# -------------------------------------------------------------------
# Database (Postgres via DATABASE_URL)
# -------------------------------------------------------------------
DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}

# If using Postgres, switch to the django-tenants backend
if DATABASES["default"]["ENGINE"] in (
    "django.db.backends.postgresql",
    "django.db.backends.postgresql_psycopg2",
):
    DATABASES["default"]["ENGINE"] = "django_tenants.postgresql_backend"


# Nice for managed PG; harmless for SQLite (but again, tenants won’t run on SQLite)
CONN_MAX_AGE = env.int("DB_CONN_MAX_AGE", default=600)

# -------------------------------------------------------------------
# Password validation
# -------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    # Django built-in validators
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    # Custom validators for strong password requirements
    {
        "NAME": "api.password_validators.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {
        "NAME": "api.password_validators.UppercaseValidator",
    },
    {
        "NAME": "api.password_validators.LowercaseValidator",
    },
    {
        "NAME": "api.password_validators.NumberValidator",
    },
    {
        "NAME": "api.password_validators.SpecialCharacterValidator",
    },
    {
        "NAME": "api.password_validators.MaximumLengthValidator",
        "OPTIONS": {"max_length": 128},
    },
]

# -------------------------------------------------------------------
# i18n
# -------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# -------------------------------------------------------------------
# Static
# -------------------------------------------------------------------
STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -------------------------------------------------------------------
# Proxy / cookies over HTTPS (OpenResty)
# -------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# -------------------------------------------------------------------
# Celery / Redis
# -------------------------------------------------------------------
CELERY_BROKER_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ALWAYS_EAGER = False
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_BEAT_SCHEDULE = {
    "monitors.schedule_endpoint_checks": {
        "task": "monitors.tasks.schedule_endpoint_checks",
        "schedule": timedelta(minutes=1),
    }
}

# Grace period before re-enqueuing endpoint pings that were recently queued.
PENDING_REQUEUE_GRACE_SECONDS = env.int("PENDING_REQUEUE_GRACE_SECONDS", default=90)

# -------------------------------------------------------------------
# Payments / Stripe (test mode)
# -------------------------------------------------------------------
STRIPE_PUBLIC_KEY = env("STRIPE_PUBLIC_KEY", default="")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_PRO_PRICE_ID = env("STRIPE_PRO_PRICE_ID", default="")

# Validate Stripe keys in production
if not DEBUG:
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

    import sys

    should_validate = not any(cmd in sys.argv for cmd in management_commands_skip_validation)

    if should_validate:
        if not STRIPE_PUBLIC_KEY or not STRIPE_PUBLIC_KEY.startswith("pk_"):
            raise ValueError(
                "STRIPE_PUBLIC_KEY must be set and start with 'pk_' in production.\n"
                "Get your keys from https://dashboard.stripe.com/apikeys"
            )
        if not STRIPE_SECRET_KEY or not STRIPE_SECRET_KEY.startswith("sk_"):
            raise ValueError(
                "STRIPE_SECRET_KEY must be set and start with 'sk_' in production.\n"
                "Get your keys from https://dashboard.stripe.com/apikeys"
            )


# === TENANTS / JWT / CORS (canonical tail) ===

TENANT_MODEL = "tenants.Client"
DOMAIN_MODEL = "tenants.Domain"
TENANT_DOMAIN_MODEL = "tenants.Domain"
PUBLIC_SCHEMA_NAME = "public"

SHARED_APPS = [
    "django_tenants",
    "tenants",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
]
TENANT_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",  # Per-tenant JWT blacklist tables
    "api",
    "payments",
    "monitors",
]
INSTALLED_APPS = list(OrderedDict.fromkeys(SHARED_APPS + TENANT_APPS))
DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

TENANT_URLCONF = "app.urls_tenant"  # <-- the file that has admin/
PUBLIC_SCHEMA_URLCONF = "app.urls_public"
ROOT_URLCONF = "app.urls_tenant"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "app.middleware.SecurityHeadersMiddleware",  # P1-03: Additional security headers
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django_tenants.middleware.main.TenantMainMiddleware",
    "app.middleware_logging.RequestIDMiddleware",  # Add unique request ID
    "app.middleware_logging.RequestLoggingMiddleware",  # Log all requests/responses
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".localhost",
    "django-01.local",
    ".django-01.local",
    "statuswatch.local",
    ".statuswatch.local",
]


try:
    if DATABASES["default"]["ENGINE"].endswith("postgresql"):
        DATABASES["default"]["ENGINE"] = "django_tenants.postgresql_backend"
except Exception:
    pass

REST_FRAMEWORK = {
    **globals().get("REST_FRAMEWORK", {}),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "EXCEPTION_HANDLER": "api.exception_handler.custom_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",  # General anonymous users
        "user": "1000/hour",  # Authenticated users
        "registration": "5/hour",  # Registration endpoint (strict)
        "login": "10/hour",  # Login endpoint (prevent brute-force)
        "burst": "20/min",  # Burst protection (short-term)
        "sustained": "100/day",  # Long-term protection
    },
}
# -------------------------------------------------------------------
# JWT Configuration (P1-05: Token Rotation)
# -------------------------------------------------------------------
SIMPLE_JWT = {
    # Token Lifetimes
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),  # Short-lived access tokens
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),  # Longer-lived refresh tokens
    # Token Rotation
    "ROTATE_REFRESH_TOKENS": True,  # Issue new refresh token on refresh
    "BLACKLIST_AFTER_ROTATION": True,  # Blacklist old refresh token
    # Security
    "UPDATE_LAST_LOGIN": True,  # Update user's last_login on token generation
    # Token Claims
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    # Algorithms
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    # Token Classes
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    # Sliding Tokens (disabled, we use access/refresh pair)
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
}

# CORS
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=False)
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://localhost:5173",  # Vite with HTTPS
        "https://localhost:8443",  # OpenResty/Nginx proxy
    ],
)
CORS_ALLOW_CREDENTIALS = True  # Allow cookies/auth headers
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
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "https://acme.django-01.local",
        "https://*.django-01.local",
        "https://statuswatch.local",
        "https://*.statuswatch.local",
    ],
)

# -------------------------------------------------------------------
# HTTPS/Security Configuration (P1-02)
# -------------------------------------------------------------------
# Trust X-Forwarded-Proto header from reverse proxies (nginx, AWS ALB, etc.)
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HTTPS Redirect - enabled in production only
# In development, the reverse proxy handles HTTPS termination
ENFORCE_HTTPS = env.bool("ENFORCE_HTTPS", default=not DEBUG)
SECURE_SSL_REDIRECT = ENFORCE_HTTPS

# HTTP Strict Transport Security (HSTS)
# Tells browsers to only access the site via HTTPS
if ENFORCE_HTTPS:
    SECURE_HSTS_SECONDS = env.int(
        "SECURE_HSTS_SECONDS", default=3600
    )  # 1 hour for testing, increase gradually
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
        "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True
    )  # Apply to all subdomains (important for multi-tenant)
    SECURE_HSTS_PRELOAD = env.bool(
        "SECURE_HSTS_PRELOAD", default=False
    )  # Set True only when using long HSTS duration
else:
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# Cookie Security - only send cookies over HTTPS in production
SESSION_COOKIE_SECURE = ENFORCE_HTTPS
CSRF_COOKIE_SECURE = ENFORCE_HTTPS

# Additional cookie security settings
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
CSRF_COOKIE_HTTPONLY = True  # Prevent JavaScript access to CSRF cookie
SESSION_COOKIE_SAMESITE = (
    "Lax"  # CSRF protection: Lax allows navigation, Strict blocks all cross-site
)
CSRF_COOKIE_SAMESITE = "Lax"

# -------------------------------------------------------------------
# Security Headers (P1-03)
# -------------------------------------------------------------------
# X-Frame-Options: Prevent clickjacking attacks
# DENY = cannot be displayed in frame/iframe at all
# SAMEORIGIN = can only be displayed in frame on same origin
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"  # Most secure: prevents all framing

# X-Content-Type-Options: Prevent MIME type sniffing
# Browsers must respect the declared Content-Type
SECURE_CONTENT_TYPE_NOSNIFF = True

# Referrer-Policy: Control referrer information sent to other sites
# 'same-origin' = only send referrer for same-origin requests
# 'strict-origin-when-cross-origin' = send origin only for cross-origin HTTPS
SECURE_REFERRER_POLICY = "same-origin"

# Permissions-Policy (formerly Feature-Policy)
# Control which browser features can be used
# Disable potentially risky features like geolocation, camera, microphone
PERMISSIONS_POLICY = {
    "geolocation": [],  # No sites can access geolocation
    "camera": [],  # No sites can access camera
    "microphone": [],  # No sites can access microphone
    "payment": [],  # No sites can use Payment Request API (we use Stripe redirect)
    "usb": [],  # No USB device access
    "magnetometer": [],  # No magnetometer access
    "accelerometer": [],  # No accelerometer access
    "gyroscope": [],  # No gyroscope access
}

# Content Security Policy (CSP) - Prevent XSS attacks
# NOTE: django-csp package would be ideal for production, but for now we'll use basic CSP
# For production, install: pip install django-csp
# Then configure CSP_* settings in detail
if ENFORCE_HTTPS:
    # Strict CSP for production
    CSP_DEFAULT_SRC = ("'self'",)
    CSP_SCRIPT_SRC = (
        "'self'",
        "'unsafe-inline'",
    )  # TODO: Remove unsafe-inline when frontend uses nonces
    CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com")
    CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com")
    CSP_IMG_SRC = ("'self'", "data:", "https:")
    CSP_CONNECT_SRC = ("'self'", "https://api.stripe.com")  # Allow Stripe API calls
    CSP_FRAME_ANCESTORS = ("'none'",)  # Same as X-Frame-Options: DENY
    CSP_BASE_URI = ("'self'",)
    CSP_FORM_ACTION = ("'self'",)
else:
    # Relaxed CSP for development
    CSP_DEFAULT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'")
    CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'")
    CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
    CSP_CONNECT_SRC = ("'self'", "ws:", "wss:")  # Allow WebSocket for dev hot-reload
    CSP_FRAME_ANCESTORS = ("'none'",)  # Still prevent clickjacking in dev
    CSP_BASE_URI = ("'self'",)
    CSP_FORM_ACTION = ("'self'",)

# -------------------------------------------------------------------
# Logging Configuration
# -------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name} {module}.{funcName}:{lineno} - {message}",
            "style": "{",
        },
        "simple": {
            "format": "[{levelname}] {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
        "max_warning": {
            "()": "app.logging_filters.MaxLevelFilter",
            "level": "WARNING",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "console_debug": {
            "level": "DEBUG",
            "filters": ["require_debug_true"],
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file_app": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "statuswatch.log",
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
            "filters": ["max_warning"],
        },
        "file_error": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "error.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "file_security": {
            "level": "WARNING",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "security.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "file_request": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "request.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "file_audit": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "audit.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "file_performance": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "performance.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "file_payments": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "payments.log",
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file_app", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["file_security", "console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["file_app", "file_error", "console"],
            "level": "ERROR",
            "propagate": False,
        },
        "api": {
            "handlers": ["console", "file_app"],
            "level": "INFO",
            "propagate": False,
        },
        "tenants": {
            "handlers": ["console", "file_app"],
            "level": "INFO",
            "propagate": False,
        },
        "payments": {
            "handlers": ["console", "file_app"],
            "level": "INFO",
            "propagate": False,
        },
        "payments.checkout": {
            "handlers": ["console", "file_payments"],
            "level": "INFO",
            "propagate": False,
        },
        "api.auth": {
            "handlers": ["console", "file_app", "file_security"],
            "level": "INFO",
            "propagate": False,
        },
        "api.request": {
            "handlers": ["file_request"],
            "level": "INFO",
            "propagate": False,
        },
        "api.audit": {
            "handlers": ["file_audit", "console"],
            "level": "INFO",
            "propagate": False,
        },
        "api.performance": {
            "handlers": ["file_performance", "console"],
            "level": "WARNING",
            "propagate": False,
        },
        "monitors": {
            "handlers": ["console", "file_app"],
            "level": "INFO",
            "propagate": False,
        },
        "monitors.audit": {
            "handlers": ["file_audit", "console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "monitors.performance": {
            "handlers": ["file_performance", "console"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console", "file_app"],
        "level": "INFO",
    },
}

# -------------------------------------------------------------------
# Email Configuration
# -------------------------------------------------------------------
# For MVP/development: console backend logs emails to terminal
# For production: switch to SMTP backend (SendGrid, Mailgun, AWS SES, etc.)
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")

# SMTP settings (used when EMAIL_BACKEND is set to SMTP)
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

# Email addresses
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@statuswatch.local")
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)

# Frontend URL for email links (verification, password reset, etc.)
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173")

# -------------------------------------------------------------------
# Sentry Configuration (Error & Performance Monitoring)
# -------------------------------------------------------------------
SENTRY_DSN = env("SENTRY_DSN", default="")
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", default="development" if DEBUG else "production")
SENTRY_TRACES_SAMPLE_RATE = env.float(
    "SENTRY_TRACES_SAMPLE_RATE", default=0.1
)  # 10% of transactions

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        # Enable performance monitoring
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        # Capture 10% of transactions for performance monitoring in production
        # Set to 1.0 in development to capture all
        profiles_sample_rate=1.0 if DEBUG else 0.1,
        # Integrations
        integrations=[
            DjangoIntegration(
                transaction_style="url",  # Group transactions by URL pattern
                middleware_spans=True,  # Track middleware performance
                signals_spans=True,  # Track Django signals
            ),
            CeleryIntegration(
                monitor_beat_tasks=True,  # Monitor Celery Beat scheduled tasks
                exclude_beat_tasks=[],  # Don't exclude any beat tasks
            ),
            RedisIntegration(),
            LoggingIntegration(
                level=logging.INFO,  # Capture info and above as breadcrumbs
                event_level=logging.ERROR,  # Send errors and above as events
            ),
        ],
        # Customize what gets sent to Sentry
        send_default_pii=False,  # Don't send personally identifiable information
        attach_stacktrace=True,  # Include stack traces in messages
        # Performance
        enable_tracing=True,
        # Filter out health check requests from performance monitoring
        traces_sampler=lambda sampling_context: (
            0.0
            if sampling_context.get("wsgi_environ", {}).get("PATH_INFO", "").startswith("/health")
            else SENTRY_TRACES_SAMPLE_RATE
        ),
        # Release tracking (set via environment variable in CI/CD)
        release=env("SENTRY_RELEASE", default=None),
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
