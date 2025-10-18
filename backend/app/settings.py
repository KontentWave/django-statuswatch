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
environ.Env.read_env(BASE_DIR / ".env")

# -------------------------------------------------------------------
# Core
# -------------------------------------------------------------------
SECRET_KEY = 'django-insecure-4##dqsxc46_pzcfq4nxp%_f)jhaa%0*^tnp#h-(3bok6)%28iu'  # move to ENV in real deployments
DEBUG = True

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
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
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
}
SIMPLE_JWT = {"ACCESS_TOKEN_LIFETIME": timedelta(minutes=60)}

# CORS
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CSRF_TRUSTED_ORIGINS = [
    "https://acme.django-01.local",
    "https://*.django-01.local",
    "https://statuswatch.local",
    "https://*.statuswatch.local",
]

# --- behind reverse proxy / HTTPS in dev ---
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# keep redirects off in dev; your proxy handles HTTPS on :443
SECURE_SSL_REDIRECT = False