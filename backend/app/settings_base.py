"""
Base Django settings for StatusWatch project (Django 5 + DRF + Celery + django-tenants).

This module contains environment-agnostic settings shared across all environments.
Environment-specific overrides are in settings_development.py and settings_production.py.
"""

import os
from datetime import timedelta
from pathlib import Path

import environ

# -------------------------------------------------------------------
# Base directories and paths
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# -------------------------------------------------------------------
# Environment variable setup
# -------------------------------------------------------------------
env = environ.Env()

# Look for .env in backend/ first, then project root
env_file = BASE_DIR / ".env"
if not env_file.exists():
    env_file = BASE_DIR.parent / ".env"
environ.Env.read_env(env_file)

# -------------------------------------------------------------------
# django-tenants Configuration
# -------------------------------------------------------------------
TENANT_MODEL = "tenants.Client"  # app_label.ModelName
DOMAIN_MODEL = "tenants.Domain"
TENANT_DOMAIN_MODEL = "tenants.Domain"
PUBLIC_SCHEMA_NAME = "public"

SHARED_APPS: tuple[str, ...] = (
    "django_tenants",  # MUST be first!
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",  # CORS support
    "tenants",  # your tenants app (Client/Domain models)
    # NOTE: token_blacklist NOT in SHARED_APPS - we handle it per tenant
)

TENANT_APPS: tuple[str, ...] = (
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework_simplejwt.token_blacklist",  # JWT blacklist per tenant
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

# -------------------------------------------------------------------
# Middleware
# -------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "app.middleware.SecurityHeadersMiddleware",  # Additional security headers
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django_tenants.middleware.main.TenantMainMiddleware",
    "app.middleware_tenant_logging.TenantRoutingLoggingMiddleware",  # Log tenant routing
    "app.middleware_logging.RequestIDMiddleware",  # Add unique request ID
    "app.middleware_logging.RequestLoggingMiddleware",  # Log all requests/responses
    "corsheaders.middleware.CorsMiddleware",
    "app.middleware_cors_logging.CorsLoggingMiddleware",  # Log CORS decisions
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# -------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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
# Database (structure only - connection details loaded from env in child settings)
# -------------------------------------------------------------------
DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}

# If using Postgres, switch to the django-tenants backend
if DATABASES["default"]["ENGINE"] in (
    "django.db.backends.postgresql",
    "django.db.backends.postgresql_psycopg2",
):
    DATABASES["default"]["ENGINE"] = "django_tenants.postgresql_backend"

# Connection pooling
CONN_MAX_AGE = env.int("DB_CONN_MAX_AGE", default=600)

# -------------------------------------------------------------------
# Password Validation
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
# Internationalization
# -------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# -------------------------------------------------------------------
# Static Files
# -------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# -------------------------------------------------------------------
# Default Primary Key Field Type
# -------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -------------------------------------------------------------------
# Celery/Redis Configuration
# -------------------------------------------------------------------
# Prefer explicit CELERY_* vars; otherwise fall back to REDIS_URL; finally to sane defaults.
REDIS_URL_DEFAULT = "redis://127.0.0.1:6379/0"

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL", REDIS_URL_DEFAULT)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND") or os.getenv(
    "REDIS_RESULT_URL", "redis://127.0.0.1:6379/1"
)

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

# Grace period before re-enqueuing endpoint pings
PENDING_REQUEUE_GRACE_SECONDS = env.int("PENDING_REQUEUE_GRACE_SECONDS", default=90)

# -------------------------------------------------------------------
# Stripe Payment Configuration
# -------------------------------------------------------------------
STRIPE_PUBLIC_KEY = env("STRIPE_PUBLIC_KEY", default="")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_PRO_PRICE_ID = env("STRIPE_PRO_PRICE_ID", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")

# -------------------------------------------------------------------
# Admin Panel
# -------------------------------------------------------------------
ADMIN_URL = env("ADMIN_URL", default="admin/")

# -------------------------------------------------------------------
# REST Framework Configuration
# -------------------------------------------------------------------
REST_FRAMEWORK = {
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
        "billing": "100/hour",  # Billing/checkout endpoints (prevent abuse)
    },
}

# -------------------------------------------------------------------
# JWT Configuration
# -------------------------------------------------------------------
# Note: SECRET_KEY must be defined in environment-specific settings before importing this
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
    # Algorithms - SIGNING_KEY will be set in environment-specific settings
    "ALGORITHM": "HS256",
    "VERIFYING_KEY": None,
    # Token Classes
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    # Sliding Tokens (disabled, we use access/refresh pair)
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
}

# -------------------------------------------------------------------
# Email Configuration (base settings)
# -------------------------------------------------------------------
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@statuswatch.local")
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)

# Frontend URL for email links (verification, password reset, etc.)
FRONTEND_URL = env("FRONTEND_URL", default="https://localhost:5173")

# -------------------------------------------------------------------
# Logging Configuration (shared base)
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
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
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
        "file_billing": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "billing.log",
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "file_webhooks": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "webhooks.log",
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "file_webhooks_debug": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "webhooks_debug.log",
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "file_webhook_signatures": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "webhook_signatures.log",
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "file_subscriptions": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "subscriptions.log",
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "file_cancellations": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "cancellations.log",
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "file_subscription_state": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "subscription_state.log",
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "file_authentication": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "authentication.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "file_health": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "health.log",
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "file_frontend_resolution": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "frontend_resolution.log",
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
        "tenant.routing": {
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
        "payments.billing": {
            "handlers": ["console", "file_billing"],
            "level": "INFO",
            "propagate": False,
        },
        "payments.webhooks": {
            "handlers": ["console", "file_webhooks"],
            "level": "INFO",
            "propagate": False,
        },
        "payments.webhooks.debug": {
            "handlers": ["file_webhooks_debug"],
            "level": "DEBUG",
            "propagate": False,
        },
        "payments.webhooks.signature": {
            "handlers": ["file_webhook_signatures"],
            "level": "INFO",
            "propagate": False,
        },
        "payments.subscriptions": {
            "handlers": ["console", "file_subscriptions"],
            "level": "INFO",
            "propagate": False,
        },
        "payments.subscription_state": {
            "handlers": ["file_subscription_state"],
            "level": "INFO",
            "propagate": False,
        },
        "payments.cancellations": {
            "handlers": ["console", "file_cancellations"],
            "level": "INFO",
            "propagate": False,
        },
        "payments.frontend_resolver": {
            "handlers": ["file_frontend_resolution"],
            "level": "INFO",
            "propagate": False,
        },
        "api.auth": {
            "handlers": ["console", "file_authentication", "file_security"],
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
        "api.health": {
            "handlers": ["file_health"],
            "level": "INFO",
            "propagate": False,
        },
        "monitors": {
            "handlers": ["console", "file_app"],
            "level": "INFO",
            "propagate": False,
        },
        "monitors.audit": {
            "handlers": ["file_audit", "console"],
            "level": "INFO",  # Will be overridden in dev to DEBUG
            "propagate": False,
        },
        "monitors.performance": {
            "handlers": ["file_performance", "console"],
            "level": "INFO",
            "propagate": False,
        },
        "subscriptions.feature_gating": {
            "handlers": ["console", "file_subscriptions"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console", "file_app"],
        "level": "INFO",
    },
}
