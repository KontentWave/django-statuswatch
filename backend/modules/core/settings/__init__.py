"""Shared settings helpers for StatusWatch.

Centralizes common settings primitives (paths, env loader, base configs) so
`app.settings_base` and any future modular stacks can import from a single
module rather than duplicating logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path
from typing import Any

import environ

from modules.core.settings.logger import SettingsLoggingContext, setup_settings_logging
from modules.core.settings.security import (
    get_dev_cors_settings,
    get_dev_csrf_trusted_origins,
    get_dev_https_settings,
    get_dev_security_headers,
    get_permissions_policy,
    get_prod_cors_settings,
    get_prod_csrf_trusted_origins,
    get_prod_https_settings,
    get_prod_security_headers,
)
from modules.core.settings.sentry import configure_sentry
from modules.core.settings_registry import (
    get_installed_apps,
    get_middleware,
    get_shared_apps,
    get_tenant_apps,
)

# ---------------------------------------------------------------------------
# Base directories / env loader
# ---------------------------------------------------------------------------
# Path(__file__) -> backend/modules/core/settings/__init__.py; backend lives three levels up
BASE_DIR = Path(__file__).resolve().parents[3]
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

_env = environ.Env()
_env_file = BASE_DIR / ".env"
if not _env_file.exists():
    _env_file = BASE_DIR.parent / ".env"
if _env_file.exists():
    environ.Env.read_env(_env_file)


def get_env() -> environ.Env:
    """Return the singleton environ loader used across settings."""

    return _env


# ---------------------------------------------------------------------------
# Tenancy configuration
# ---------------------------------------------------------------------------
TENANT_MODEL = "tenants.Client"
DOMAIN_MODEL = "tenants.Domain"
TENANT_DOMAIN_MODEL = "tenants.Domain"
PUBLIC_SCHEMA_NAME = "public"
SHOW_PUBLIC_IF_NO_TENANT_FOUND = True
DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)


# ---------------------------------------------------------------------------
# Settings fragments
# ---------------------------------------------------------------------------


def build_default_database_config() -> dict[str, Any]:
    env = get_env()
    database = env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
    if database["ENGINE"] in (
        "django.db.backends.postgresql",
        "django.db.backends.postgresql_psycopg2",
    ):
        database["ENGINE"] = "django_tenants.postgresql_backend"
    return {"default": database}


def build_rest_framework_config() -> dict[str, Any]:
    return {
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework_simplejwt.authentication.JWTAuthentication",
            "rest_framework.authentication.SessionAuthentication",
        ),
        "EXCEPTION_HANDLER": "api.exception_handler.custom_exception_handler",
        "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
        "PAGE_SIZE": 50,
        "DEFAULT_THROTTLE_RATES": {
            "anon": "100/hour",
            "user": "1000/hour",
            "registration": "5/hour",
            "login": "10/hour",
            "burst": "20/min",
            "sustained": "100/day",
            "billing": "100/hour",
        },
    }


def build_simple_jwt_defaults() -> dict[str, Any]:
    return {
        "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
        "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
        "ROTATE_REFRESH_TOKENS": True,
        "BLACKLIST_AFTER_ROTATION": True,
        "UPDATE_LAST_LOGIN": True,
        "AUTH_HEADER_TYPES": ("Bearer",),
        "USER_ID_FIELD": "id",
        "USER_ID_CLAIM": "user_id",
        "ALGORITHM": "HS256",
        "VERIFYING_KEY": None,
        "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
        "TOKEN_TYPE_CLAIM": "token_type",
        "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
        "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
        "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
    }


def build_logging_config(log_dir: Path | None = None) -> dict[str, Any]:
    dir_path = log_dir or LOG_DIR
    return {
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
            "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
            "require_debug_true": {"()": "django.utils.log.RequireDebugTrue"},
            "max_warning": {"()": "app.logging_filters.MaxLevelFilter", "level": "WARNING"},
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
            **{
                name: {
                    "level": handler_cfg["level"],
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": dir_path / handler_cfg["filename"],
                    "maxBytes": handler_cfg.get("max_bytes", 1024 * 1024 * 5),
                    "backupCount": 5,
                    "formatter": "verbose",
                    **({"filters": ["max_warning"]} if handler_cfg.get("filters") else {}),
                }
                for name, handler_cfg in {
                    "file_app": {"level": "INFO", "filename": "statuswatch.log", "filters": True},
                    "file_error": {"level": "ERROR", "filename": "error.log"},
                    "file_security": {"level": "WARNING", "filename": "security.log"},
                    "file_request": {"level": "INFO", "filename": "request.log"},
                    "file_audit": {"level": "INFO", "filename": "audit.log"},
                    "file_performance": {"level": "INFO", "filename": "performance.log"},
                    "file_payments": {"level": "INFO", "filename": "payments.log"},
                    "file_billing": {"level": "INFO", "filename": "billing.log"},
                    "file_webhooks": {"level": "INFO", "filename": "webhooks.log"},
                    "file_webhooks_debug": {"level": "DEBUG", "filename": "webhooks_debug.log"},
                    "file_webhook_signatures": {
                        "level": "INFO",
                        "filename": "webhook_signatures.log",
                    },
                    "file_subscriptions": {"level": "INFO", "filename": "subscriptions.log"},
                    "file_cancellations": {"level": "INFO", "filename": "cancellations.log"},
                    "file_subscription_state": {
                        "level": "INFO",
                        "filename": "subscription_state.log",
                    },
                    "file_authentication": {"level": "INFO", "filename": "authentication.log"},
                    "file_health": {
                        "level": "INFO",
                        "filename": "health.log",
                        "max_bytes": 1024 * 1024 * 10,
                    },
                    "file_frontend_resolution": {
                        "level": "INFO",
                        "filename": "frontend_resolution.log",
                        "max_bytes": 1024 * 1024 * 10,
                    },
                }.items()
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
                "level": "INFO",
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


def build_email_defaults(env: environ.Env | None = None) -> Mapping[str, Any]:
    env = env or get_env()
    default_from = env("DEFAULT_FROM_EMAIL", default="noreply@statuswatch.local")
    return {
        "EMAIL_HOST": env("EMAIL_HOST", default="localhost"),
        "EMAIL_PORT": env.int("EMAIL_PORT", default=587),
        "EMAIL_USE_TLS": env.bool("EMAIL_USE_TLS", default=True),
        "EMAIL_HOST_USER": env("EMAIL_HOST_USER", default=""),
        "EMAIL_HOST_PASSWORD": env("EMAIL_HOST_PASSWORD", default=""),
        "DEFAULT_FROM_EMAIL": default_from,
        "SERVER_EMAIL": env("SERVER_EMAIL", default=default_from),
        "FRONTEND_URL": env("FRONTEND_URL", default=""),
    }


def build_celery_config(
    env: environ.Env | None = None,
    *,
    timezone: str = "UTC",
) -> Mapping[str, Any]:
    env = env or get_env()
    redis_url = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
    result_backend_default = redis_url[:-1] + "1" if redis_url.endswith("/0") else redis_url

    celery_broker_url = env("CELERY_BROKER_URL", default=redis_url)
    celery_result_backend = env("CELERY_RESULT_BACKEND", default=result_backend_default)

    return {
        "REDIS_URL": redis_url,
        "CELERY_BROKER_URL": celery_broker_url,
        "CELERY_RESULT_BACKEND": celery_result_backend,
        "CELERY_TIMEZONE": timezone,
        "CELERY_TASK_TRACK_STARTED": True,
        "CELERY_TASK_ALWAYS_EAGER": env.bool("CELERY_TASK_ALWAYS_EAGER", default=False),
        "CELERY_ACCEPT_CONTENT": ["json"],
        "CELERY_TASK_SERIALIZER": "json",
        "CELERY_RESULT_SERIALIZER": "json",
        "CELERY_BEAT_SCHEDULE": {
            "monitors.schedule_endpoint_checks": {
                "task": "monitors.tasks.schedule_endpoint_checks",
                "schedule": timedelta(minutes=1),
            }
        },
    }


def build_stripe_config(env: environ.Env | None = None) -> Mapping[str, str]:
    env = env or get_env()
    return {
        "STRIPE_PUBLIC_KEY": env("STRIPE_PUBLIC_KEY", default=""),
        "STRIPE_SECRET_KEY": env("STRIPE_SECRET_KEY", default=""),
        "STRIPE_PRO_PRICE_ID": env("STRIPE_PRO_PRICE_ID", default=""),
        "STRIPE_WEBHOOK_SECRET": env("STRIPE_WEBHOOK_SECRET", default=""),
    }


__all__ = [
    "BASE_DIR",
    "LOG_DIR",
    "get_env",
    "get_shared_apps",
    "get_tenant_apps",
    "get_middleware",
    "get_installed_apps",
    "TENANT_MODEL",
    "DOMAIN_MODEL",
    "TENANT_DOMAIN_MODEL",
    "PUBLIC_SCHEMA_NAME",
    "SHOW_PUBLIC_IF_NO_TENANT_FOUND",
    "DATABASE_ROUTERS",
    "build_default_database_config",
    "build_rest_framework_config",
    "build_simple_jwt_defaults",
    "build_logging_config",
    "build_email_defaults",
    "build_celery_config",
    "build_stripe_config",
    "get_dev_cors_settings",
    "get_prod_cors_settings",
    "get_dev_csrf_trusted_origins",
    "get_prod_csrf_trusted_origins",
    "get_dev_https_settings",
    "get_prod_https_settings",
    "get_dev_security_headers",
    "get_prod_security_headers",
    "get_permissions_policy",
    "configure_sentry",
    "setup_settings_logging",
    "SettingsLoggingContext",
]
