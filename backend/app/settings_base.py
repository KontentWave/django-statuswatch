"""
Base Django settings for StatusWatch project (Django 5 + DRF + Celery + django-tenants).

This module contains environment-agnostic settings shared across all environments.
Environment-specific overrides are in settings_development.py and settings_production.py.
"""

from modules.core.settings import (
    BASE_DIR,
    build_celery_config,
    build_default_database_config,
    build_email_defaults,
    build_logging_config,
    build_rest_framework_config,
    build_simple_jwt_defaults,
    build_stripe_config,
    get_env,
    get_installed_apps,
    get_middleware,
    get_shared_apps,
    get_tenant_apps,
)
from modules.core.settings import (
    DATABASE_ROUTERS as CORE_DATABASE_ROUTERS,
)
from modules.core.settings import (
    DOMAIN_MODEL as CORE_DOMAIN_MODEL,
)
from modules.core.settings import (
    LOG_DIR as CORE_LOG_DIR,
)
from modules.core.settings import (
    PUBLIC_SCHEMA_NAME as CORE_PUBLIC_SCHEMA_NAME,
)
from modules.core.settings import (
    SHOW_PUBLIC_IF_NO_TENANT_FOUND as CORE_SHOW_PUBLIC_IF_NO_TENANT_FOUND,
)
from modules.core.settings import (
    TENANT_DOMAIN_MODEL as CORE_TENANT_DOMAIN_MODEL,
)
from modules.core.settings import (
    TENANT_MODEL as CORE_TENANT_MODEL,
)

env = get_env()

# -------------------------------------------------------------------
# File system locations
# -------------------------------------------------------------------
LOG_DIR = CORE_LOG_DIR

# -------------------------------------------------------------------
# django-tenants Configuration
# -------------------------------------------------------------------
TENANT_MODEL = CORE_TENANT_MODEL
DOMAIN_MODEL = CORE_DOMAIN_MODEL
TENANT_DOMAIN_MODEL = CORE_TENANT_DOMAIN_MODEL
PUBLIC_SCHEMA_NAME = CORE_PUBLIC_SCHEMA_NAME

# Allow internal requests (e.g., from Caddy with Host: web:8000) to use public schema
SHOW_PUBLIC_IF_NO_TENANT_FOUND = CORE_SHOW_PUBLIC_IF_NO_TENANT_FOUND

SHARED_APPS: tuple[str, ...] = tuple(get_shared_apps())
TENANT_APPS: tuple[str, ...] = tuple(get_tenant_apps())

# Final INSTALLED_APPS resolved through the core registry (shared first, deduped)
INSTALLED_APPS = get_installed_apps()

DATABASE_ROUTERS = CORE_DATABASE_ROUTERS

# Use separate URLConfs for public (root schema) vs tenant schemas
PUBLIC_SCHEMA_URLCONF = "app.urls_public"
ROOT_URLCONF = "app.urls_tenant"

# -------------------------------------------------------------------
# Middleware
# -------------------------------------------------------------------
# Resolved dynamically so modules can register additional middleware entries.
MIDDLEWARE = list(get_middleware())

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

DATABASES = build_default_database_config()

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

celery_config = build_celery_config(env, timezone=TIME_ZONE)
REDIS_URL = celery_config["REDIS_URL"]
CELERY_BROKER_URL = celery_config["CELERY_BROKER_URL"]
CELERY_RESULT_BACKEND = celery_config["CELERY_RESULT_BACKEND"]
CELERY_TIMEZONE = celery_config["CELERY_TIMEZONE"]
CELERY_TASK_TRACK_STARTED = celery_config["CELERY_TASK_TRACK_STARTED"]
CELERY_TASK_ALWAYS_EAGER = celery_config["CELERY_TASK_ALWAYS_EAGER"]
CELERY_ACCEPT_CONTENT = celery_config["CELERY_ACCEPT_CONTENT"]
CELERY_TASK_SERIALIZER = celery_config["CELERY_TASK_SERIALIZER"]
CELERY_RESULT_SERIALIZER = celery_config["CELERY_RESULT_SERIALIZER"]
CELERY_BEAT_SCHEDULE = celery_config["CELERY_BEAT_SCHEDULE"]

# Grace period before re-enqueuing endpoint pings
PENDING_REQUEUE_GRACE_SECONDS = env.int("PENDING_REQUEUE_GRACE_SECONDS", default=90)

# -------------------------------------------------------------------
# Stripe Payment Configuration
# -------------------------------------------------------------------
stripe_config = build_stripe_config(env)
STRIPE_PUBLIC_KEY = stripe_config["STRIPE_PUBLIC_KEY"]
STRIPE_SECRET_KEY = stripe_config["STRIPE_SECRET_KEY"]
STRIPE_PRO_PRICE_ID = stripe_config["STRIPE_PRO_PRICE_ID"]
STRIPE_WEBHOOK_SECRET = stripe_config["STRIPE_WEBHOOK_SECRET"]

# -------------------------------------------------------------------
# Admin Panel
# -------------------------------------------------------------------
ADMIN_URL = env("ADMIN_URL", default="admin/")

# -------------------------------------------------------------------
# REST Framework Configuration
# -------------------------------------------------------------------
REST_FRAMEWORK = build_rest_framework_config()

# -------------------------------------------------------------------
# JWT Configuration
# -------------------------------------------------------------------
# Note: SECRET_KEY must be defined in environment-specific settings before importing this
SIMPLE_JWT = build_simple_jwt_defaults()

# -------------------------------------------------------------------
# Email Configuration (base settings)
# -------------------------------------------------------------------
_email_defaults = build_email_defaults(env)
EMAIL_HOST = _email_defaults["EMAIL_HOST"]
EMAIL_PORT = _email_defaults["EMAIL_PORT"]
EMAIL_USE_TLS = _email_defaults["EMAIL_USE_TLS"]
EMAIL_HOST_USER = _email_defaults["EMAIL_HOST_USER"]
EMAIL_HOST_PASSWORD = _email_defaults["EMAIL_HOST_PASSWORD"]
DEFAULT_FROM_EMAIL = _email_defaults["DEFAULT_FROM_EMAIL"]
SERVER_EMAIL = _email_defaults["SERVER_EMAIL"]
FRONTEND_URL = _email_defaults["FRONTEND_URL"]

# -------------------------------------------------------------------
# Logging Configuration (shared base)
# -------------------------------------------------------------------
LOGGING = build_logging_config()
