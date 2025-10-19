"""
Django settings for app project (Django 5 + DRF + Celery + django-tenants).
"""

from pathlib import Path
import os
import environ

# -------------------------------------------------------------------
# Base & env
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

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

# include wildcard for tenant subdomains like acme.django-01.local
ALLOWED_HOSTS = ["localhost","127.0.0.1","django-01.local","acme.django-01.local"]

# -------------------------------------------------------------------
# django-tenants
# -------------------------------------------------------------------
TENANT_MODEL = "tenants.Client"   # app_label.ModelName
DOMAIN_MODEL = "tenants.Domain"

SHARED_APPS = (
    "django_tenants",                 # must be first
    "django.contrib.contenttypes",    # required by tenants
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",  # P1-05: JWT token blacklist
    "tenants",                        # your tenants app (Client/Domain models)
)

TENANT_APPS = (
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    # your tenant-facing apps:
    "api",
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
    "django_tenants.middleware.main.TenantMainMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

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
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}

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

# -------------------------------------------------------------------
# Payments / Stripe (test mode)
# -------------------------------------------------------------------
STRIPE_PUBLIC_KEY = env("STRIPE_PUBLIC_KEY", default="")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")




# === TENANTS / JWT / CORS (canonical tail) ===
from collections import OrderedDict
from datetime import timedelta

TENANT_MODEL = "tenants.Client"; DOMAIN_MODEL = "tenants.Domain"; TENANT_DOMAIN_MODEL = "tenants.Domain"; PUBLIC_SCHEMA_NAME = "public"

SHARED_APPS = [
    "django_tenants",
    "tenants",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",  # P1-05: JWT token blacklist
    "api",
]
TENANT_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "rest_framework",
    "api",
    "payments",
]
INSTALLED_APPS = list(OrderedDict.fromkeys(SHARED_APPS + TENANT_APPS))
DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

TENANT_URLCONF = "app.urls_tenant"           # <-- the file that has admin/
PUBLIC_SCHEMA_URLCONF = "app.urls_public"
ROOT_URLCONF = "app.urls_tenant"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "app.middleware.SecurityHeadersMiddleware",  # P1-03: Additional security headers
    "django_tenants.middleware.main.TenantMainMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ALLOWED_HOSTS = [
    "localhost","127.0.0.1",
    "django-01.local",".django-01.local",
    "statuswatch.local",".statuswatch.local"
]


try:
    if DATABASES["default"]["ENGINE"].endswith("postgresql"):
        DATABASES["default"]["ENGINE"] = "django_tenants.postgresql_backend"
except Exception:
    pass

REST_FRAMEWORK = {**globals().get("REST_FRAMEWORK", {}),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "EXCEPTION_HANDLER": "api.exception_handler.custom_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",           # General anonymous users
        "user": "1000/hour",          # Authenticated users
        "registration": "5/hour",     # Registration endpoint (strict)
        "login": "10/hour",           # Login endpoint (prevent brute-force)
        "burst": "20/min",            # Burst protection (short-term)
        "sustained": "100/day",       # Long-term protection
    },
}
# -------------------------------------------------------------------
# JWT Configuration (P1-05: Token Rotation)
# -------------------------------------------------------------------
SIMPLE_JWT = {
    # Token Lifetimes
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),  # Short-lived access tokens
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),     # Longer-lived refresh tokens
    
    # Token Rotation
    "ROTATE_REFRESH_TOKENS": True,   # Issue new refresh token on refresh
    "BLACKLIST_AFTER_ROTATION": True, # Blacklist old refresh token
    
    # Security
    "UPDATE_LAST_LOGIN": True,       # Update user's last_login on token generation
    
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
    default=["http://localhost:5173", "http://127.0.0.1:5173"]
)
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "https://acme.django-01.local",
        "https://*.django-01.local",
        "https://statuswatch.local",
        "https://*.statuswatch.local",
    ]
)

# -------------------------------------------------------------------
# HTTPS/Security Configuration (P1-02)
# -------------------------------------------------------------------
# Trust X-Forwarded-Proto header from reverse proxies (nginx, AWS ALB, etc.)
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HTTPS Redirect - enabled in production only
# In development, the reverse proxy handles HTTPS termination
ENFORCE_HTTPS = env.bool("ENFORCE_HTTPS", default=not DEBUG)
SECURE_SSL_REDIRECT = ENFORCE_HTTPS

# HTTP Strict Transport Security (HSTS)
# Tells browsers to only access the site via HTTPS
if ENFORCE_HTTPS:
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=3600)  # 1 hour for testing, increase gradually
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)  # Apply to all subdomains (important for multi-tenant)
    SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)  # Set True only when using long HSTS duration
else:
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# Cookie Security - only send cookies over HTTPS in production
SESSION_COOKIE_SECURE = ENFORCE_HTTPS
CSRF_COOKIE_SECURE = ENFORCE_HTTPS

# Additional cookie security settings
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
CSRF_COOKIE_HTTPONLY = True     # Prevent JavaScript access to CSRF cookie
SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection: Lax allows navigation, Strict blocks all cross-site
CSRF_COOKIE_SAMESITE = 'Lax'

# -------------------------------------------------------------------
# Security Headers (P1-03)
# -------------------------------------------------------------------
# X-Frame-Options: Prevent clickjacking attacks
# DENY = cannot be displayed in frame/iframe at all
# SAMEORIGIN = can only be displayed in frame on same origin
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'  # Most secure: prevents all framing

# X-Content-Type-Options: Prevent MIME type sniffing
# Browsers must respect the declared Content-Type
SECURE_CONTENT_TYPE_NOSNIFF = True

# Referrer-Policy: Control referrer information sent to other sites
# 'same-origin' = only send referrer for same-origin requests
# 'strict-origin-when-cross-origin' = send origin only for cross-origin HTTPS
SECURE_REFERRER_POLICY = 'same-origin'

# Permissions-Policy (formerly Feature-Policy)
# Control which browser features can be used
# Disable potentially risky features like geolocation, camera, microphone
PERMISSIONS_POLICY = {
    'geolocation': [],        # No sites can access geolocation
    'camera': [],             # No sites can access camera
    'microphone': [],         # No sites can access microphone
    'payment': [],            # No sites can use Payment Request API (we use Stripe redirect)
    'usb': [],                # No USB device access
    'magnetometer': [],       # No magnetometer access
    'accelerometer': [],      # No accelerometer access
    'gyroscope': [],          # No gyroscope access
}

# Content Security Policy (CSP) - Prevent XSS attacks
# NOTE: django-csp package would be ideal for production, but for now we'll use basic CSP
# For production, install: pip install django-csp
# Then configure CSP_* settings in detail
if ENFORCE_HTTPS:
    # Strict CSP for production
    CSP_DEFAULT_SRC = ("'self'",)
    CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")  # TODO: Remove unsafe-inline when frontend uses nonces
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
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} {module}.{funcName}:{lineno} - {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'console_debug': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file_error': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'error.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'file_security': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['file_security', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['file_error', 'console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'api': {
            'handlers': ['console', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
        'tenants': {
            'handlers': ['console', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
        'payments': {
            'handlers': ['console', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# -------------------------------------------------------------------
# Email Configuration
# -------------------------------------------------------------------
# For MVP/development: console backend logs emails to terminal
# For production: switch to SMTP backend (SendGrid, Mailgun, AWS SES, etc.)
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend"
)

# SMTP settings (used when EMAIL_BACKEND is set to SMTP)
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

# Email addresses
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default="noreply@statuswatch.local"
)
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)

# Frontend URL for email links (verification, password reset, etc.)
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173")
