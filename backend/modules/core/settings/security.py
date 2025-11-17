"""Security-related settings helpers shared across environments."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_COMMON_CORS_ALLOW_HEADERS = [
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

_DEV_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://localhost:5173",
    "https://localhost:8443",
]

_DEV_ALLOWED_REGEXES = [
    r"^http://localhost:5173$",
    r"^http://127\.0\.0\.1:5173$",
    r"^https://localhost:5173$",
    r"^https://[a-z0-9-]+\.statuswatch\.local$",
    r"^https://[a-z0-9-]+\.statuswatch\.local:\d+$",
]

_DEV_CSRF_TRUSTED = [
    "http://localhost:5173",
    "https://localhost:5173",
    "https://statuswatch.local",
    "https://*.statuswatch.local",
]

_PROD_DEFAULT_ALLOWED_ORIGINS = [
    "https://statuswatch.local",
    "https://www.statuswatch.local",
]

_PROD_DEFAULT_ALLOWED_REGEXES = [
    r"^https://[a-z0-9-]+\.statuswatch\.local$",
]

_PROD_DEFAULT_CSRF = [
    "https://statuswatch.local",
    "https://*.statuswatch.local",
]

_PERMISSIONS_POLICY: Mapping[str, list[str]] = {
    "geolocation": [],
    "camera": [],
    "microphone": [],
    "payment": [],
    "usb": [],
    "magnetometer": [],
    "accelerometer": [],
    "gyroscope": [],
}


def get_dev_cors_settings(env) -> Mapping[str, Any]:
    return {
        "CORS_ALLOW_ALL_ORIGINS": env.bool("CORS_ALLOW_ALL_ORIGINS", default=False),
        "CORS_ALLOWED_ORIGINS": _DEV_ALLOWED_ORIGINS,
        "CORS_ALLOWED_ORIGIN_REGEXES": _DEV_ALLOWED_REGEXES,
        "CORS_ALLOW_CREDENTIALS": True,
        "CORS_ALLOW_HEADERS": _COMMON_CORS_ALLOW_HEADERS,
    }


def get_prod_cors_settings(env) -> Mapping[str, Any]:
    return {
        "CORS_ALLOW_ALL_ORIGINS": False,
        "CORS_ALLOWED_ORIGINS": env.list(
            "CORS_ALLOWED_ORIGINS",
            default=_PROD_DEFAULT_ALLOWED_ORIGINS,
        ),
        "CORS_ALLOWED_ORIGIN_REGEXES": env.list(
            "CORS_ALLOWED_ORIGIN_REGEXES",
            default=_PROD_DEFAULT_ALLOWED_REGEXES,
        ),
        "CORS_ALLOW_CREDENTIALS": True,
        "CORS_ALLOW_HEADERS": _COMMON_CORS_ALLOW_HEADERS,
    }


def get_dev_csrf_trusted_origins() -> list[str]:
    return list(_DEV_CSRF_TRUSTED)


def get_prod_csrf_trusted_origins(env) -> list[str]:
    return env.list("CSRF_TRUSTED_ORIGINS", default=_PROD_DEFAULT_CSRF)


def get_dev_https_settings() -> Mapping[str, Any]:
    return {
        "ENFORCE_HTTPS": False,
        "SECURE_SSL_REDIRECT": False,
        "SECURE_HSTS_SECONDS": 0,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": False,
        "SECURE_HSTS_PRELOAD": False,
        "USE_X_FORWARDED_HOST": True,
        "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
        "SESSION_COOKIE_SECURE": False,
        "CSRF_COOKIE_SECURE": False,
        "SESSION_COOKIE_HTTPONLY": True,
        "CSRF_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "CSRF_COOKIE_SAMESITE": "Lax",
    }


def get_prod_https_settings(env) -> Mapping[str, Any]:
    enforce_https = env.bool("ENFORCE_HTTPS", default=True)
    hsts_seconds = env.int("SECURE_HSTS_SECONDS", default=3600) if enforce_https else 0
    hsts_include = (
        env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True) if enforce_https else False
    )
    hsts_preload = env.bool("SECURE_HSTS_PRELOAD", default=False) if enforce_https else False

    return {
        "ENFORCE_HTTPS": enforce_https,
        "SECURE_SSL_REDIRECT": enforce_https,
        "SECURE_HSTS_SECONDS": hsts_seconds,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": hsts_include,
        "SECURE_HSTS_PRELOAD": hsts_preload,
        "USE_X_FORWARDED_HOST": True,
        "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
        "SESSION_COOKIE_SECURE": enforce_https,
        "CSRF_COOKIE_SECURE": enforce_https,
        "SESSION_COOKIE_HTTPONLY": True,
        "CSRF_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "CSRF_COOKIE_SAMESITE": "Lax",
    }


def get_dev_security_headers() -> Mapping[str, Any]:
    return {
        "SECURE_CROSS_ORIGIN_OPENER_POLICY": "same-origin",
        "X_FRAME_OPTIONS": "DENY",
        "SECURE_CONTENT_TYPE_NOSNIFF": True,
        "SECURE_REFERRER_POLICY": "same-origin",
        "CSP_DEFAULT_SRC": ("'self'", "'unsafe-inline'", "'unsafe-eval'"),
        "CSP_SCRIPT_SRC": ("'self'", "'unsafe-inline'", "'unsafe-eval'"),
        "CSP_STYLE_SRC": ("'self'", "'unsafe-inline'"),
        "CSP_CONNECT_SRC": ("'self'", "ws:", "wss:"),
        "CSP_FONT_SRC": ("'self'",),
        "CSP_IMG_SRC": ("'self'", "data:"),
        "CSP_FRAME_ANCESTORS": ("'none'",),
        "CSP_BASE_URI": ("'self'",),
        "CSP_FORM_ACTION": ("'self'",),
    }


def get_prod_security_headers() -> Mapping[str, Any]:
    return {
        "SECURE_CROSS_ORIGIN_OPENER_POLICY": "same-origin",
        "X_FRAME_OPTIONS": "DENY",
        "SECURE_CONTENT_TYPE_NOSNIFF": True,
        "SECURE_REFERRER_POLICY": "same-origin",
        "CSP_DEFAULT_SRC": ("'self'",),
        "CSP_SCRIPT_SRC": ("'self'", "'unsafe-inline'"),
        "CSP_STYLE_SRC": ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com"),
        "CSP_FONT_SRC": ("'self'", "https://fonts.gstatic.com"),
        "CSP_IMG_SRC": ("'self'", "data:", "https:"),
        "CSP_CONNECT_SRC": ("'self'", "https://api.stripe.com"),
        "CSP_FRAME_ANCESTORS": ("'none'",),
        "CSP_BASE_URI": ("'self'",),
        "CSP_FORM_ACTION": ("'self'",),
    }


def get_permissions_policy() -> Mapping[str, list[str]]:
    return _PERMISSIONS_POLICY
