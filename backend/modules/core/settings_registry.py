"""Central registry for shared StatusWatch settings primitives.

Provides helper hooks so future modules can register additional Django apps or
middleware without editing the core settings module directly.
"""

from __future__ import annotations

from collections.abc import Iterable


class SettingsRegistry:
    """Keeps track of shared vs tenant apps and middleware chains."""

    def __init__(self) -> None:
        self._shared_apps: list[str] = [
            "django_tenants",
            "django.contrib.contenttypes",
            "django.contrib.staticfiles",
            "rest_framework",
            "corsheaders",
            "tenants",
            "django_celery_beat",
        ]
        self._tenant_apps: list[str] = [
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.sessions",
            "django.contrib.messages",
            "rest_framework_simplejwt.token_blacklist",
            "api",
            "monitors",
        ]
        self._middleware: list[str] = [
            "app.middleware_internal.InternalEndpointMiddleware",
            "app.middleware_security_custom.CustomSecurityMiddleware",
            "app.middleware.SecurityHeadersMiddleware",
            "whitenoise.middleware.WhiteNoiseMiddleware",
            "django_tenants.middleware.main.TenantMainMiddleware",
            "app.middleware_tenant_logging.TenantRoutingLoggingMiddleware",
            "app.middleware_logging.RequestIDMiddleware",
            "app.middleware_logging.RequestLoggingMiddleware",
            "corsheaders.middleware.CorsMiddleware",
            "app.middleware_cors_logging.CorsLoggingMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
        ]

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------
    def register_shared_apps(self, *apps: str) -> None:
        self._shared_apps = _append_unique(self._shared_apps, apps)

    def register_tenant_apps(self, *apps: str) -> None:
        self._tenant_apps = _append_unique(self._tenant_apps, apps)

    def register_middleware(self, *middleware_classes: str) -> None:
        self._middleware = _append_unique(self._middleware, middleware_classes)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    @property
    def shared_apps(self) -> list[str]:
        return self._shared_apps

    @property
    def tenant_apps(self) -> list[str]:
        return self._tenant_apps

    @property
    def middleware(self) -> list[str]:
        return self._middleware

    def build_installed_apps(self) -> list[str]:
        """Return final INSTALLED_APPS preserving the shared->tenant order."""

        return list(self._shared_apps) + [
            app for app in self._tenant_apps if app not in self._shared_apps
        ]


def _append_unique(target: list[str], new_items: Iterable[str]) -> list[str]:
    for item in new_items:
        if item and item not in target:
            target.append(item)
    return target


core_settings_registry = SettingsRegistry()


def register_shared_apps(*apps: str) -> None:
    core_settings_registry.register_shared_apps(*apps)


def register_tenant_apps(*apps: str) -> None:
    core_settings_registry.register_tenant_apps(*apps)


def register_middleware(*middleware_classes: str) -> None:
    core_settings_registry.register_middleware(*middleware_classes)


def get_shared_apps() -> list[str]:
    return core_settings_registry.shared_apps


def get_tenant_apps() -> list[str]:
    return core_settings_registry.tenant_apps


def get_middleware() -> list[str]:
    return core_settings_registry.middleware


def get_installed_apps() -> list[str]:
    return core_settings_registry.build_installed_apps()


__all__ = [
    "core_settings_registry",
    "register_shared_apps",
    "register_tenant_apps",
    "register_middleware",
    "get_shared_apps",
    "get_tenant_apps",
    "get_middleware",
    "get_installed_apps",
]
