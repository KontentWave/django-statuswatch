"""Core primitives shared by modular StatusWatch apps."""

from .settings_registry import (
    core_settings_registry,
    get_installed_apps,
    get_middleware,
    get_shared_apps,
    get_tenant_apps,
    register_middleware,
    register_shared_apps,
    register_tenant_apps,
)

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
