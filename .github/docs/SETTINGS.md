# StatusWatch Settings Documentation

## Overview

StatusWatch uses a **split settings architecture** to separate environment-agnostic configuration from environment-specific settings. This provides better security, maintainability, and clarity.

### Settings Files Structure

backend/modules/core/
├── settings_registry.py # Central INSTALLED_APPS/middleware registry
└── urls.py # Shared admin/health/auth/payment route helpers

```
backend/app/
├── settings.py                    # Router: detects environment and loads appropriate settings
├── settings_base.py              # Shared configuration (500+ lines)
├── settings_development.py       # Development overrides (~80 lines)
└── settings_production.py        # Production overrides (~120 lines)
```

### How It Works

1. **`settings.py`** - Entry point that:

   - Detects environment via `DJANGO_ENV` or `DEBUG` env vars
   - Loads appropriate settings module
   - Logs configuration to `logs/settings.log`

2. **`settings_base.py`** - Contains all shared settings:

   - Django apps, middleware, templates
   - Database structure, password validators
   - Celery, JWT, REST Framework configuration
   - Logging handlers and formatters

   > **Tip:** `modules/core/settings_registry.py` exposes helper functions (e.g., `get_installed_apps()`, `get_middleware()`) so future modules can register additional apps or middleware without editing `settings_base.py`.

3. **`settings_development.py`** - Development overrides:

   - `DEBUG = True`
   - Permissive CORS and ALLOWED_HOSTS
   - Console email backend
   - No Stripe/Sentry validation

4. **`settings_production.py`** - Production configuration:
   - `DEBUG = False`
   - Strict security headers (HSTS, CSP, etc.)
   - HTTPS enforcement
   - Stripe and SECRET_KEY validation
   - Sentry error monitoring

---

## Environment Variables

### Environment Selection

| Variable     | Type    | Required | Default       | Description                                                           |
| ------------ | ------- | -------- | ------------- | --------------------------------------------------------------------- |
| `DJANGO_ENV` | string  | No       | (auto-detect) | Explicit environment: `development` or `production`                   |
| `DEBUG`      | boolean | No       | `False`       | If `DJANGO_ENV` not set, falls back to this for environment detection |

**Recommendation:** Set `DJANGO_ENV=development` in dev, `DJANGO_ENV=production` in prod.

---

### Core Settings (Required in Production)

| Variable       | Type   | Required | Default                | Description                                                                   |
| -------------- | ------ | -------- | ---------------------- | ----------------------------------------------------------------------------- |
| `SECRET_KEY`   | string | **YES**  | _(none)_               | Django secret key for cryptographic signing. Must be 50+ chars in production. |
| `DATABASE_URL` | string | **YES**  | `sqlite:///db.sqlite3` | PostgreSQL connection string (required for multi-tenancy)                     |

**Examples:**

```bash
# Development
SECRET_KEY="django-insecure-dev-key-CHANGE-ME-IN-PRODUCTION"
DATABASE_URL="postgresql://user:pass@localhost:5432/statuswatch_dev"

# Production
SECRET_KEY="your-50-char-random-key-generated-securely-here-abc123"
DATABASE_URL="postgresql://user:pass@db.example.com:5432/statuswatch"
```

**Generate SECRET_KEY:**

```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

---

### Database Configuration

| Variable          | Type    | Required | Default | Description                                                 |
| ----------------- | ------- | -------- | ------- | ----------------------------------------------------------- |
| `DB_CONN_MAX_AGE` | integer | No       | `600`   | Database connection max age in seconds (connection pooling) |

---

### Celery & Redis

| Variable                        | Type    | Required | Default                    | Description                                               |
| ------------------------------- | ------- | -------- | -------------------------- | --------------------------------------------------------- |
| `REDIS_URL`                     | string  | No       | `redis://127.0.0.1:6379/0` | Redis connection for Celery broker and result backend     |
| `PENDING_REQUEUE_GRACE_SECONDS` | integer | No       | `90`                       | Grace period before re-enqueueing pending endpoint checks |

**Example:**

```bash
REDIS_URL="redis://redis.example.com:6379/1"
```

---

### Stripe Payment Configuration

| Variable                | Type   | Required | Default | Production Validation    |
| ----------------------- | ------ | -------- | ------- | ------------------------ |
| `STRIPE_PUBLIC_KEY`     | string | No       | `""`    | Must start with `pk_`    |
| `STRIPE_SECRET_KEY`     | string | No       | `""`    | Must start with `sk_`    |
| `STRIPE_PRO_PRICE_ID`   | string | No       | `""`    | Price ID for Pro plan    |
| `STRIPE_WEBHOOK_SECRET` | string | No       | `""`    | Must start with `whsec_` |

**Production Behavior:**

- If any Stripe key is invalid format, Django will raise `ValueError` on startup
- Validation is skipped for management commands (migrate, shell, etc.)

**Example:**

```bash
# Test mode (development)
STRIPE_PUBLIC_KEY="pk_test_51ABC..."
STRIPE_SECRET_KEY="sk_test_51ABC..."
STRIPE_WEBHOOK_SECRET="whsec_..."

# Live mode (production)
STRIPE_PUBLIC_KEY="pk_live_51ABC..."
STRIPE_SECRET_KEY="sk_live_51ABC..."
STRIPE_WEBHOOK_SECRET="whsec_..."
```

---

### Security & HTTPS

| Variable                         | Type    | Required | Default     | Description                                                             |
| -------------------------------- | ------- | -------- | ----------- | ----------------------------------------------------------------------- |
| `ENFORCE_HTTPS`                  | boolean | No       | `not DEBUG` | Enforce HTTPS redirects and secure cookies (auto-enabled in production) |
| `SECURE_HSTS_SECONDS`            | integer | No       | `3600`      | HTTP Strict Transport Security duration (only if `ENFORCE_HTTPS=True`)  |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | boolean | No       | `True`      | Apply HSTS to subdomains (important for multi-tenant)                   |
| `SECURE_HSTS_PRELOAD`            | boolean | No       | `False`     | Enable HSTS preload (set to `True` with 1+ year HSTS duration)          |

**Production Recommendations:**

```bash
ENFORCE_HTTPS=True
SECURE_HSTS_SECONDS=31536000  # 1 year (after testing with 3600)
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True  # Only after testing with long HSTS duration
```

---

### CORS Configuration

| Variable                      | Type    | Required | Default (Dev)                 | Default (Prod) | Description                             |
| ----------------------------- | ------- | -------- | ----------------------------- | -------------- | --------------------------------------- |
| `CORS_ALLOW_ALL_ORIGINS`      | boolean | No       | `False`                       | `False`        | **Never set to `True` in production!**  |
| `CORS_ALLOWED_ORIGINS`        | list    | No       | `http://localhost:5173`, etc. | _(must set)_   | Comma-separated list of allowed origins |
| `CORS_ALLOWED_ORIGIN_REGEXES` | list    | No       | See dev defaults              | _(must set)_   | Regex patterns for tenant subdomains    |

**Development defaults:**

```bash
CORS_ALLOWED_ORIGINS="http://localhost:5173,https://localhost:5173,https://localhost:8443"
CORS_ALLOWED_ORIGIN_REGEXES="^https://[a-z0-9-]+\.localhost:5173$,^https://[a-z0-9-]+\.django-01\.local$"
```

**Production example:**

```bash
CORS_ALLOWED_ORIGINS="https://statuswatch.com,https://www.statuswatch.com"
CORS_ALLOWED_ORIGIN_REGEXES="^https://[a-z0-9-]+\.statuswatch\.com$"
```

---

### CSRF Configuration

| Variable               | Type | Required | Default (Dev) | Default (Prod) | Description                                      |
| ---------------------- | ---- | -------- | ------------- | -------------- | ------------------------------------------------ |
| `CSRF_TRUSTED_ORIGINS` | list | No       | Dev domains   | _(must set)_   | Comma-separated list of trusted origins for CSRF |

**Production example:**

```bash
CSRF_TRUSTED_ORIGINS="https://statuswatch.com,https://*.statuswatch.com"
```

---

### Allowed Hosts

| Variable        | Type | Required | Default (Dev)          | Default (Prod) | Description                               |
| --------------- | ---- | -------- | ---------------------- | -------------- | ----------------------------------------- |
| `ALLOWED_HOSTS` | list | No       | `localhost`, `*.local` | _(must set)_   | Comma-separated list of allowed hostnames |

**Production example:**

```bash
ALLOWED_HOSTS="statuswatch.com,.statuswatch.com,www.statuswatch.com"
```

---

### Email Configuration

| Variable              | Type    | Required | Default                         | Description                     |
| --------------------- | ------- | -------- | ------------------------------- | ------------------------------- |
| `EMAIL_BACKEND`       | string  | No       | `console` (dev) / `smtp` (prod) | Email backend class             |
| `EMAIL_HOST`          | string  | No       | `localhost`                     | SMTP server hostname            |
| `EMAIL_PORT`          | integer | No       | `587`                           | SMTP server port                |
| `EMAIL_USE_TLS`       | boolean | No       | `True`                          | Use TLS for SMTP connection     |
| `EMAIL_HOST_USER`     | string  | No       | `""`                            | SMTP authentication username    |
| `EMAIL_HOST_PASSWORD` | string  | No       | `""`                            | SMTP authentication password    |
| `DEFAULT_FROM_EMAIL`  | string  | No       | `noreply@statuswatch.local`     | Default sender email address    |
| `SERVER_EMAIL`        | string  | No       | _(same as DEFAULT_FROM_EMAIL)_  | Server error notification email |

**Production example (SendGrid):**

```bash
EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST="smtp.sendgrid.net"
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER="apikey"
EMAIL_HOST_PASSWORD="SG.your-api-key-here"
DEFAULT_FROM_EMAIL="noreply@statuswatch.com"
```

---

### Frontend URL

| Variable       | Type   | Required | Default                  | Description                                                 |
| -------------- | ------ | -------- | ------------------------ | ----------------------------------------------------------- |
| `FRONTEND_URL` | string | No       | `https://localhost:5173` | Frontend URL for email links (verification, password reset) |

**Production example:**

```bash
FRONTEND_URL="https://app.statuswatch.com"
```

---

### Admin Panel Security

| Variable    | Type   | Required | Default  | Description                                                |
| ----------- | ------ | -------- | -------- | ---------------------------------------------------------- |
| `ADMIN_URL` | string | No       | `admin/` | Admin panel URL path (use non-standard path in production) |

**Production recommendation:**

```bash
ADMIN_URL="secure-admin-f7a9b2c4/"  # Random, hard-to-guess path
```

---

### Sentry Error Monitoring

| Variable                    | Type   | Required | Default                      | Description                                       |
| --------------------------- | ------ | -------- | ---------------------------- | ------------------------------------------------- |
| `SENTRY_DSN`                | string | No       | `""`                         | Sentry DSN for error tracking (disabled if empty) |
| `SENTRY_ENVIRONMENT`        | string | No       | `development` / `production` | Environment name in Sentry dashboard              |
| `SENTRY_TRACES_SAMPLE_RATE` | float  | No       | `0.1`                        | Percentage of transactions to capture (0.0-1.0)   |
| `SENTRY_RELEASE`            | string | No       | _(none)_                     | Release version (set in CI/CD)                    |

**Production example:**

```bash
SENTRY_DSN="https://abc123@o123.ingest.sentry.io/456"
SENTRY_ENVIRONMENT="production"
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% of transactions
SENTRY_RELEASE="statuswatch@1.2.3"
```

---

## Migration Guide

### From Monolithic `settings.py` to Split Settings

1. **Checkpoint your current settings in version control** (e.g., commit or stash any local edits).

2. **Set environment variable:**

   ```bash
   # In .env file
   DJANGO_ENV=development  # or production
   ```

3. **Verify settings load correctly:**

   ```bash
   python manage.py check
   ```

4. **Check logs/settings.log for configuration details:**

   ```bash
   cat logs/settings.log
   ```

5. **Run tests to ensure compatibility:**
   ```bash
   python manage.py test
   ```

### Common Issues

**Issue:** `ImportError: cannot import name 'X' from 'app.settings'`

- **Solution:** The split settings use wildcard imports (`from app.settings_base import *`). All settings should be available.

**Issue:** Settings not loading in production

- **Solution:** Ensure `DJANGO_ENV=production` is set in environment variables, not just `.env` file.

**Issue:** Stripe validation errors in development

- **Solution:** Development settings skip Stripe validation. Use test keys or leave empty.

---

## Development Setup

### Minimal `.env` for Development

```bash
# Environment
DJANGO_ENV=development
DEBUG=True

# Database (use PostgreSQL for multi-tenancy)
DATABASE_URL=postgresql://postgres:devpass@localhost:5432/statuswatch_dev

# Redis
REDIS_URL=redis://127.0.0.1:6379/0

# Stripe (test mode - optional in dev)
STRIPE_PUBLIC_KEY=pk_test_51...
STRIPE_SECRET_KEY=sk_test_51...
STRIPE_WEBHOOK_SECRET=whsec_...

# Frontend
FRONTEND_URL=http://localhost:5173
```

---

## Production Setup

### Required `.env` for Production

```bash
# Environment
DJANGO_ENV=production
DEBUG=False

# Core (REQUIRED)
SECRET_KEY=your-50-char-random-key-here
DATABASE_URL=postgresql://user:pass@db.prod.com:5432/statuswatch

# Redis
REDIS_URL=redis://redis.prod.com:6379/0

# Stripe (REQUIRED for payments)
STRIPE_PUBLIC_KEY=pk_live_51...
STRIPE_SECRET_KEY=sk_live_51...
STRIPE_PRO_PRICE_ID=price_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Security
ENFORCE_HTTPS=True
SECURE_HSTS_SECONDS=31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True

# CORS & CSRF
ALLOWED_HOSTS=statuswatch.com,.statuswatch.com
CORS_ALLOWED_ORIGINS=https://statuswatch.com,https://www.statuswatch.com
CORS_ALLOWED_ORIGIN_REGEXES=^https://[a-z0-9-]+\.statuswatch\.com$
CSRF_TRUSTED_ORIGINS=https://statuswatch.com,https://*.statuswatch.com

# Email (SMTP)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SG.your-api-key
DEFAULT_FROM_EMAIL=noreply@statuswatch.com

# Frontend
FRONTEND_URL=https://app.statuswatch.com

# Admin
ADMIN_URL=secure-admin-xyz123/

# Sentry
SENTRY_DSN=https://abc@o123.ingest.sentry.io/456
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
```

---

## Security Checklist

### Development

- [ ] Use test Stripe keys
- [ ] Use weak SECRET_KEY (it's okay for dev)
- [ ] Enable DEBUG mode
- [ ] Use console email backend

### Production

- [ ] Generate secure 50+ char SECRET_KEY
- [ ] Use live Stripe keys
- [ ] **Disable DEBUG mode** (`DEBUG=False`)
- [ ] Enable HTTPS enforcement
- [ ] Set long HSTS duration (after testing)
- [ ] Use non-standard ADMIN_URL
- [ ] Configure strict ALLOWED_HOSTS
- [ ] Configure strict CORS_ALLOWED_ORIGINS
- [ ] Use SMTP email backend
- [ ] Enable Sentry error monitoring
- [ ] Validate all required env vars are set
- [ ] Test settings with `python manage.py check --deploy`

---

## Logging

Settings loading is logged to `logs/settings.log`:

```
[INFO] app.settings_loader - 🔧 DEBUG=True detected (DJANGO_ENV not set) - Loading development settings
[INFO] app.settings_loader - 📂 Loading settings from: app.settings_development
[INFO] app.settings_loader - 📍 BASE_DIR: /path/to/backend
[INFO] app.settings_loader - 📝 LOG_DIR: /path/to/backend/logs
[INFO] app.settings_loader - ✅ Development settings loaded successfully
[INFO] app.settings_loader -    - DEBUG: True
[INFO] app.settings_loader -    - ALLOWED_HOSTS: Permissive (localhost, *.local)
[INFO] app.settings_loader -    - CORS: Permissive (localhost:5173)
[INFO] app.settings_loader -    - HTTPS: Disabled
[INFO] app.settings_loader -    - Email: Console backend
[INFO] app.settings_loader -    - Stripe: Validation disabled
[INFO] app.settings_loader -    - Sentry: Disabled
[INFO] app.settings_loader - ======================================================================
```

---

## Additional Resources

- [Django Settings Best Practices](https://docs.djangoproject.com/en/stable/topics/settings/)
- [12-Factor App Methodology](https://12factor.net/config)
- [Django Security Checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
