"""
Development settings for StatusWatch project.

Optimized for local development with relaxed security and verbose logging.
"""

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
# JWT Configuration (Development)
# -------------------------------------------------------------------
SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY  # noqa: F405

# -------------------------------------------------------------------
# CORS Configuration (Development - Permissive)
# -------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=False)  # noqa: F405
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://localhost:5173",  # Vite with HTTPS
    "https://localhost:8443",  # OpenResty/Nginx proxy
]

# CORS regex patterns for multi-tenant subdomains
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:5173$",
    r"^http://127\.0\.0\.1:5173$",
    r"^http://[a-z0-9-]+\.localhost:5173$",  # Any tenant subdomain (http)
    r"^https://localhost:5173$",
    r"^https://[a-z0-9-]+\.localhost:5173$",  # Any tenant subdomain (https)
    r"^https://[a-z0-9-]+\.django-01\.local$",
    r"^https://[a-z0-9-]+\.django-01\.local:\d+$",
    r"^https://[a-z0-9-]+\.statuswatch\.local$",
    r"^https://[a-z0-9-]+\.statuswatch\.local:\d+$",
]

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
# CSRF Configuration (Development)
# -------------------------------------------------------------------
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "https://localhost:5173",
    "https://acme.django-01.local",
    "https://*.django-01.local",
    "https://statuswatch.local",
    "https://*.statuswatch.local",
]

# -------------------------------------------------------------------
# HTTPS/Security Configuration (Development - Relaxed)
# -------------------------------------------------------------------
# Disable HTTPS enforcement in development
ENFORCE_HTTPS = False
SECURE_SSL_REDIRECT = False

# Disable HSTS in development
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Trust X-Forwarded-Proto from reverse proxy
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Cookie security (relaxed for development)
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# -------------------------------------------------------------------
# Security Headers (Development - Relaxed)
# -------------------------------------------------------------------
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"  # noqa: F405
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# Relaxed CSP for development (allow dev tools, hot-reload, etc.)
CSP_DEFAULT_SRC: tuple[str, ...] = ("'self'", "'unsafe-inline'", "'unsafe-eval'")
CSP_SCRIPT_SRC: tuple[str, ...] = ("'self'", "'unsafe-inline'", "'unsafe-eval'")
CSP_STYLE_SRC: tuple[str, ...] = ("'self'", "'unsafe-inline'")
CSP_CONNECT_SRC: tuple[str, ...] = ("'self'", "ws:", "wss:")  # Allow WebSocket for dev hot-reload
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_BASE_URI = ("'self'",)
CSP_FORM_ACTION = ("'self'",)

# Permissions Policy (same as base)
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
# Email Configuration (Development - Console Backend)
# -------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# -------------------------------------------------------------------
# Logging Configuration (Development - Verbose)
# -------------------------------------------------------------------
# Override monitors.audit logger to DEBUG level for development
LOGGING["loggers"]["monitors.audit"]["level"] = "DEBUG"  # type: ignore  # noqa: F405

# -------------------------------------------------------------------
# Development-Specific Settings
# -------------------------------------------------------------------
# No Stripe validation in development (allow empty keys for testing)
# No Sentry in development (disable error tracking)
SENTRY_DSN = ""
