# ADR 08: Production Deployment and Environment Adaptation

> **Navigation:** [← Back to README](../../../../README.md) | [Deployment Guide](../../../deployment/EC2_DEPLOYMENT_GUIDE.md) | [Diagnostic Scripts](../../../deployment/diag-scripts/README.md) | [Project Overview](../../StatusWatch_project_sheet.md)

---

**Date:** November 12, 2025  
**Status:** Implemented  
**Decision Makers:** Development Team  
**Tags:** #deployment #production #infrastructure #ec2 #docker #caddy

## Context and Problem Statement

StatusWatch needed to transition from local development to production deployment on AWS EC2. The application is a multi-tenant SaaS platform with dynamic subdomain routing, requiring proper HTTPS/TLS certificate management, environment-specific configuration, and operational monitoring tools.

**Key Challenges:**

1. Tenant subdomains were being created with `.localhost` suffix in production (incorrect domain)
2. No clear separation between local development and production configurations
3. Missing emergency diagnostic tools for production incident response
4. Caddy reverse proxy needed on-demand TLS for wildcard subdomains (`*.statuswatch.kontentwave.digital`)
5. Health monitoring needed SSL certificate validation without breaking on IP-based checks

## Decision Drivers

- **Security First:** Production must enforce HTTPS, secure cookies, HSTS headers
- **Multi-Tenant Architecture:** Each tenant needs a unique subdomain with automatic TLS
- **Operational Excellence:** Emergency scripts for 2AM incident response
- **Developer Experience:** Local development should mirror production but allow easier debugging
- **Infrastructure as Code:** Docker Compose for reproducible deployments
- **Zero Downtime:** Deployment process should minimize service interruption

## Considered Options

### Option 1: Single Environment Configuration (Rejected)

Use one settings file with environment variables for all differences.

**Pros:**

- Simpler file structure
- Single source of truth

**Cons:**

- ❌ Hard to enforce security defaults (DEBUG=False must be explicit)
- ❌ Difficult to audit production configuration
- ❌ Merge conflicts on frequently-changed settings
- ❌ No compile-time validation of production requirements

### Option 2: Multi-File Settings Architecture (Selected ✅)

Split settings into 4 files:

- `settings.py` - Environment router
- `settings_base.py` - Shared configuration
- `settings_development.py` - Dev overrides
- `settings_production.py` - Production hardening

**Pros:**

- ✅ Secure by default (production enforces DEBUG=False)
- ✅ Clear separation of concerns
- ✅ Easy to audit security posture
- ✅ Compile-time validation (raises errors if secrets missing)
- ✅ Reduced merge conflicts

**Cons:**

- More files to maintain
- Settings inheritance requires understanding of import chain

### Option 3: Docker Compose File Strategy

**Rejected:** Single `compose.yaml` with commented sections for Caddy  
**Selected:** Base + override pattern

- `compose.yaml` - Local dev (no Caddy, Django dev server)
- `docker-compose.production.yml` - Production overrides (adds Caddy, uses Gunicorn)

**Rationale:**

- Eliminates commented code (cleaner, less error-prone)
- Explicit differences between environments
- Docker Compose native file merging: `docker compose -f compose.yaml -f docker-compose.production.yml`

## Decision Outcome

**Chosen Solution:** Multi-file settings + Docker Compose override pattern + Emergency scripts

### Architecture Components

#### 1. Settings Architecture

**File Structure:**

```
backend/app/
├── settings.py                 # Router (selects dev/prod based on DJANGO_ENV)
├── settings_base.py            # Shared config (REST Framework, Celery, logging)
├── settings_development.py     # Dev overrides (DEBUG=True, relaxed CORS)
└── settings_production.py      # Production hardening (DEBUG=False, HTTPS, secrets validation)
```

**Environment Detection:**

```python
# settings.py
DJANGO_ENV = os.getenv("DJANGO_ENV", "development")

if DJANGO_ENV == "production":
    from app.settings_production import *
else:
    from app.settings_development import *
```

**Key Configuration Differences:**

| Setting                        | Development                   | Production                                          |
| ------------------------------ | ----------------------------- | --------------------------------------------------- |
| `DEBUG`                        | `True`                        | `False` (enforced with validation)                  |
| `SECRET_KEY`                   | Insecure default              | Required, validated (50+ chars, no 'insecure')      |
| `DEFAULT_TENANT_DOMAIN_SUFFIX` | `localhost`                   | `statuswatch.kontentwave.digital`                   |
| `ALLOWED_HOSTS`                | `['*']`                       | Explicit list only                                  |
| `CORS_ALLOW_ALL_ORIGINS`       | `False`                       | `False` (strict whitelist)                          |
| `ENFORCE_HTTPS`                | `False`                       | `True`                                              |
| `SECURE_SSL_REDIRECT`          | `False`                       | `True`                                              |
| `SECURE_HSTS_SECONDS`          | `0`                           | `3600` (progressive rollout to 31536000)            |
| `SESSION_COOKIE_SECURE`        | `False`                       | `True`                                              |
| `CSRF_COOKIE_SECURE`           | `False`                       | `True`                                              |
| `STRIPE_*` validation          | Optional                      | Required with format checks (`pk_`, `sk_`, `whsec`) |
| `EMAIL_BACKEND`                | `console` (stdout)            | `smtp` (SendGrid)                                   |
| `CELERY_TASK_ALWAYS_EAGER`     | `True` (sync execution)       | `False` (async via Redis)                           |
| `SENTRY_DSN`                   | Empty (no error tracking)     | Required for monitoring                             |
| Django command                 | `runserver` (auto-reload)     | Gunicorn (production WSGI server)                   |
| CSP headers                    | Relaxed (allow `unsafe-eval`) | Strict (no `unsafe-*` directives)                   |
| Logging                        | Console + file (DEBUG level)  | File only (INFO level, rotated)                     |
| Frontend URL                   | `http://localhost:5173`       | `https://statuswatch.kontentwave.digital`           |
| TLS/SSL                        | Optional (dev certificates)   | Mandatory (Let's Encrypt via Caddy)                 |
| Reverse Proxy                  | Nginx/OpenResty (external)    | Caddy (in Docker Compose)                           |
| Database                       | SQLite or Docker PostgreSQL   | Docker PostgreSQL with persistent volume            |
| Redis                          | Docker Redis                  | Docker Redis with persistent volume                 |
| File Uploads                   | Local disk                    | S3 (future)                                         |
| Static Files                   | Django dev server             | WhiteNoise (compressed, cached)                     |
| Log Rotation                   | Manual                        | Automatic (5-10MB per file, 3-5 backups)            |
| Health Checks                  | Optional                      | Required (`/health/`, `/health/ready/`, `/metrics`) |
| Rate Limiting                  | Disabled                      | Enabled (authentication endpoints)                  |
| CORS Origins                   | Wildcard for localhost        | Explicit whitelist only                             |
| CSRF Origins                   | Wildcard for localhost        | Explicit whitelist only                             |
| Database Connection Pooling    | Disabled (`CONN_MAX_AGE=0`)   | Enabled (`CONN_MAX_AGE=600`)                        |
| Stripe Mode                    | Test keys (`pk_test_`, `sk_`) | Live keys (`pk_live_`, `sk_live_`)                  |
| Docker Image Tag               | `latest` or local build       | `edge` (from GHCR)                                  |
| Container Command              | `runserver 0.0.0.0:8000`      | Gunicorn from Dockerfile CMD                        |

#### 2. Docker Compose Architecture

**File Merging Pattern:**

```bash
# Local Development
docker compose up -d
# Uses: compose.yaml only
# Services: db, redis, web (Django dev server), worker, beat

# Production (EC2)
docker compose -f compose.yaml -f docker-compose.production.yml up -d
# Merges: compose.yaml (base) + docker-compose.production.yml (overrides)
# Services: db, redis, web (Gunicorn), worker, beat, caddy
```

**Base Configuration (`compose.yaml`):**

- PostgreSQL 16 with persistent volume
- Redis 7 (broker on db 0, results on db 1)
- Web service with Django dev server (`python manage.py runserver 0.0.0.0:8000`)
- Celery worker (5 processes)
- Celery beat (DatabaseScheduler)
- Health checks for all services
- Shared networks and volumes

**Production Overrides (`docker-compose.production.yml`):**

- Adds Caddy service (reverse proxy + TLS)
- Overrides web command to use Gunicorn (from Dockerfile CMD)
- Mounts Caddyfile for on-demand TLS configuration
- Exposes ports 80, 443 for HTTPS
- Production logging configuration

**Production Service Stack:**

```yaml
services:
  db:
    image: postgres:16-alpine
    volumes:
      - dbdata:/var/lib/postgresql/data
    healthcheck: pg_isready

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data
    healthcheck: redis-cli ping

  web:
    image: ghcr.io/kontentwave/statuswatch-web:edge
    command: gunicorn app.wsgi:application --bind 0.0.0.0:8000 --workers 4
    depends_on: [db, redis]
    healthcheck: curl http://localhost:8000/health/

  worker:
    image: ghcr.io/kontentwave/statuswatch-web:edge
    command: celery -A app worker -l info -c 5
    depends_on: [db, redis]

  beat:
    image: ghcr.io/kontentwave/statuswatch-web:edge
    command: celery -A app beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    depends_on: [db, redis]

  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
      - "2019:2019" # Admin API
    volumes:
      - ./caddy/Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    depends_on: [web]
```

#### 3. Caddy On-Demand TLS Configuration

**File:** `.github/deployment/Caddyfile.ondemand`

```caddyfile
{
    # Enable admin API for healthchecks
    admin 0.0.0.0:2019

    # On-demand TLS configuration
    on_demand_tls {
        ask http://web:8000/api/internal/validate-domain/
    }
}

*.statuswatch.kontentwave.digital, statuswatch.kontentwave.digital {
    # Enable on-demand TLS for dynamic tenant subdomains
    tls {
        on_demand
    }

    encode gzip

    # Backend API routes
    handle /api/* {
        reverse_proxy web:8000
    }

    handle /admin/* {
        reverse_proxy web:8000
    }

    handle /health/* {
        reverse_proxy web:8000
    }

    # Django static files
    handle /static/* {
        reverse_proxy web:8000
    }

    # Frontend SPA fallback (served from host filesystem, NOT Docker)
    handle {
        root * /opt/statuswatch/frontend-dist
        try_files {path} /index.html
        file_server
    }
}
```

**How It Works:**

1. Client requests `https://acme.statuswatch.kontentwave.digital`
2. Caddy checks if TLS certificate exists for this subdomain
3. If not, Caddy calls `/api/internal/validate-domain/?domain=acme.statuswatch.kontentwave.digital`
4. Backend validates domain exists in database (authorized tenant)
5. If valid, Caddy requests certificate from Let's Encrypt
6. Certificate cached for future requests
7. HTTPS connection established

**Frontend Deployment:**

- Frontend is **NOT** built inside Docker containers
- Vite production build happens on EC2 host: `npm run build` in `/opt/statuswatch/django-statuswatch/frontend`
- Build output copied to `/opt/statuswatch/frontend-dist/` (host filesystem)
- Caddy serves static files directly from host path (no Docker volume needed)
- Benefits:
  - Faster deployments (no container rebuild)
  - Smaller Docker images (backend only)
  - Easier cache busting (delete old assets immediately)
  - Independent frontend/backend updates

**Security Benefits:**

- Prevents certificate issuance for unauthorized subdomains
- Rate limit protection (Let's Encrypt has strict limits)
- Automatic renewal (Caddy handles lifecycle)
- No manual certificate management

#### 4. Emergency Diagnostic Scripts

Created 5 production-ready scripts in `scripts/` directory for incident response.

**Script #1: `health-check.sh`**

Complete health monitoring with 10 checks:

```bash
./scripts/health-check.sh           # Full check
./scripts/health-check.sh --quick   # Essential checks only
./scripts/health-check.sh --fix     # Attempt auto-remediation
```

**Checks:**

- SSH connectivity to EC2
- Docker container status (6 services)
- Backend health endpoint (`/health/`)
- Frontend accessibility
- PostgreSQL connection
- Redis connection
- Disk space (threshold: 80%)
- Memory usage (threshold: 80%)
- SSL certificate expiry (warning: 30 days)
- Recent error logs (last 50 lines)

**Critical Fix:** SSL validation with IP addresses

```bash
# Problem: curl https://<ec2-ip>/health/ fails (cert is for domain, not IP)
# Solution: Use --resolve flag to map domain to IP
curl --resolve "statuswatch.kontentwave.digital:443:<ec2-public-ip>" \
     "https://statuswatch.kontentwave.digital/health/"
```

**Script #2: `db-check.sh`**

Database diagnostics:

- Database size and growth rate
- Active connections by tenant schema
- List of all tenant schemas with domain mappings
- Table counts per schema
- Slow query detection
- Connection pool utilization
- Lock conflicts
- Dead tuple percentage (vacuum needed?)

**Script #3: `emergency-restart.sh`**

Safe restart automation:

```bash
./scripts/emergency-restart.sh          # Interactive confirmation
./scripts/emergency-restart.sh --force  # Skip confirmation (CI/CD use)
```

**Steps:**

1. Pull latest images from GHCR
2. Stop all containers gracefully
3. Start containers in dependency order
4. Wait for health checks to pass
5. Display status summary

**Script #4: `tail-logs.sh`**

Live log streaming:

```bash
./scripts/tail-logs.sh                  # All services
./scripts/tail-logs.sh web              # Single service
./scripts/tail-logs.sh web worker       # Multiple services
./scripts/tail-logs.sh --errors         # Only errors (grep filter)
```

**Critical Fix:** `--errors` flag implementation

```bash
# Problem: Passed --errors directly to docker compose (unknown flag)
# Solution: Filter after fetching logs with grep
docker compose logs -f $services 2>&1 | \
    grep -i --line-buffered 'error\|exception\|traceback\|critical'
```

**Script #5: `deploy.sh`**

Safe deployment automation:

```bash
./scripts/deploy.sh
```

**Steps:**

1. Pull latest code from git
2. Pull latest Docker images
3. Run database migrations (shared + tenant schemas)
4. Restart containers with new images
5. Health check verification
6. Rollback on failure

**SSH Configuration:**

All scripts use consistent connection parameters:

```bash
PRODUCTION_HOST="<your-ec2-ip>"
SSH_USER="ubuntu"
SSH_KEY="${HOME}/.ssh/statuswatch-ec2-key.pem"

ssh -i "$SSH_KEY" "${SSH_USER}@${PRODUCTION_HOST}" "command"
```

### Critical Bug Fixes

#### Bug #1: Tenant Domain Suffix

**Problem:**

New tenants were being created with `.localhost` domain suffix in production:

- Expected: `acme.statuswatch.kontentwave.digital`
- Actual: `acme.localhost`
- Impact: Subdomains inaccessible in production, no TLS certificates issued

**Root Cause:**

`DEFAULT_TENANT_DOMAIN_SUFFIX` setting was not defined, causing fallback to hardcoded `.localhost` value in tenant creation logic.

**Fix #1: Add Environment-Specific Settings**

```python
# backend/app/settings_production.py
DEFAULT_TENANT_DOMAIN_SUFFIX = env(
    "DEFAULT_TENANT_DOMAIN_SUFFIX",
    default="statuswatch.kontentwave.digital",
)

# backend/app/settings_development.py
DEFAULT_TENANT_DOMAIN_SUFFIX = env(
    "DEFAULT_TENANT_DOMAIN_SUFFIX",
    default="localhost",  # For Vite dev server (acme.localhost:5173)
)
```

**Fix #2: Data Migration for Existing Tenants**

Created idempotent migration to fix existing tenant domains:

**File:** `backend/tenants/migrations/0008_fix_tenant_domains_production.py`

```python
def fix_tenant_domains(apps, schema_editor):
    """Update tenant domains from .localhost to .statuswatch.kontentwave.digital"""
    Domain = apps.get_model("tenants", "Domain")

    # Find all .localhost domains (excluding public/main)
    localhost_domains = Domain.objects.filter(
        domain__endswith=".localhost"
    ).exclude(
        tenant__schema_name__in=["public", "main"]
    )

    for domain in localhost_domains:
        old_domain = domain.domain
        new_domain = old_domain.replace(
            ".localhost",
            ".statuswatch.kontentwave.digital"
        )

        # Skip if new domain already exists (idempotent)
        if Domain.objects.filter(domain=new_domain).exists():
            print(f"⏭️  Skipping {old_domain} - {new_domain} already exists")
            continue

        # Update domain
        domain.domain = new_domain
        domain.save()
        print(f"✅ Updated domain: {old_domain} → {new_domain}")
```

**Migration Output (Nov 12, 2025):**

```
Running migrations:
  Applying tenants.0008_fix_tenant_domains_production...
✅ Updated domain: pokus2.localhost → pokus2.statuswatch.kontentwave.digital
⏭️  Skipping acme.localhost - acme.statuswatch.kontentwave.digital already exists
✅ Successfully updated 1 tenant domain(s)
⏭️  Skipped 1 domain(s) (already exist)
```

**Result:**

- All existing tenants now use correct production domain
- New tenants automatically get correct suffix
- Migration is idempotent (safe to re-run)

#### Bug #2: Migration History Cleanup

**Problem:**

Redundant migrations for localhost/loopback domains:

- `0002_add_localhost_domain.py` - Adds `localhost`, `127.0.0.1`
- `0003_add_dev_domains.py` - Adds same + `statuswatch.local`, `acme.statuswatch.local`
- `0007_add_loopback_domains.py` - Adds `127.0.0.1`, `statuswatch.local` again

Each migration overlaps, causing confusion.

**Decision:**

Keep all migrations as-is. Rationale:

1. Migrations already applied in production (cannot delete)
2. History provides audit trail of domain evolution
3. `update_or_create` makes them idempotent (safe to run multiple times)
4. Squashing would require complex coordination (not worth risk)

**Alternative Considered:** Squash migrations 0002-0007 into single migration

- **Rejected:** Too risky for live production system
- **Better solution:** Document migration purpose in comments

#### Bug #3: Performance Index Conflicts

**Problem:**

Two migrations that cancel each other:

- `monitors/0003_add_performance_indexes.py` - Adds 3 indexes
- `monitors/0004_remove_endpoint_indexes.py` - Removes same 3 indexes

Net result: No indexes (poor query performance at scale).

**Decision:**

Keep both migrations for now. Reason:

1. Already applied in production
2. Provides history of performance tuning attempts
3. New indexes can be added in fresh migration (Phase 3)

**Future Action (Phase 3):**

Create `0005_add_optimized_indexes.py` with proper indexes based on query patterns:

```python
migrations.AddIndex(
    model_name="endpoint",
    index=models.Index(
        fields=["tenant", "last_checked_at"],
        name="monitors_endpoint_tenant_check_idx",
    ),
)
```

### Infrastructure Setup

#### EC2 Instance Details

**Region:** EU North 1 (Stockholm)  
**Instance:** `ubuntu@<your-ec2-ip>`  
**OS:** Ubuntu 22.04 LTS  
**Docker:** 24.x  
**Docker Compose:** 2.x

**Directory Structure:**

```
/opt/statuswatch/
├── docker-compose.yml           # Symlink to docker-compose.production.yml (or copy)
├── docker-compose.override.yml  # Forces IMAGE_TAG=edge
├── .env                         # Production secrets (NOT in git)
├── caddy/
│   └── Caddyfile               # Copy from .github/deployment/Caddyfile.ondemand
├── django-statuswatch/          # Git clone of repository
│   ├── backend/
│   ├── frontend/               # Source code (for building)
│   └── ...
├── frontend-dist/               # Production frontend build (served by Caddy)
│   ├── index.html
│   ├── assets/                 # JS/CSS bundles with content hashes
│   └── vite.svg
└── logs/                        # Application logs (mounted volume)
```

**Deployment Alias:**

```bash
# Add to /home/ubuntu/.bashrc
alias dcp='docker compose -f docker-compose.yml -f docker-compose.override.yml'

# Usage
cd /opt/statuswatch
dcp up -d          # Start all services
dcp pull           # Pull latest images
dcp logs -f web    # View logs
dcp ps             # Service status
```

#### DNS Configuration

**Wildcard A Record:**

```
statuswatch.kontentwave.digital        A    <your-ec2-ip>
*.statuswatch.kontentwave.digital      A    <your-ec2-ip>
```

**Result:**

- `statuswatch.kontentwave.digital` → EC2 (root domain)
- `acme.statuswatch.kontentwave.digital` → EC2 (tenant subdomain)
- `main.statuswatch.kontentwave.digital` → EC2 (tenant subdomain)
- Any `{tenant}.statuswatch.kontentwave.digital` → EC2

**TLS Certificates:**

Caddy automatically issues Let's Encrypt certificates on-demand for each subdomain after validating with `/api/internal/validate-domain/`.

#### GitHub Actions CI/CD

**Workflow File:** `.github/workflows/publish.yml`

**Trigger:** Push to `main` branch

**Steps:**

1. Checkout code
2. Build Docker image from `backend/Dockerfile`
3. Push to GHCR: `ghcr.io/kontentwave/statuswatch-web:edge`
4. Tag: `edge` (always latest from main)

**Manual Deployment to EC2:**

```bash
ssh ubuntu@<your-ec2-ip>

# Backend deployment (Docker)
cd /opt/statuswatch
dcp pull                    # Pull latest edge image
dcp up -d                   # Restart with new image
dcp logs -f web            # Monitor deployment

# Frontend deployment (if changed)
cd /opt/statuswatch/django-statuswatch/frontend
npm run build               # Build Vite production bundle
rm -rf /opt/statuswatch/frontend-dist/*
cp -r dist/* /opt/statuswatch/frontend-dist/
# Caddy serves updated files immediately (no restart needed)
```

**Why Separate Frontend Deployment:**

- Frontend doesn't need Docker (static files only)
- Vite builds are fast (~30 seconds)
- No container restart needed for frontend updates
- Smaller Docker images (backend only)
- Easier rollback (just restore previous dist/ folder)

**Future:** GitHub Actions can trigger deployment via SSH (Phase 3).

### Production Environment Variables

**File:** `/opt/statuswatch/.env` (not in git)

```bash
# Core Django
DJANGO_ENV=production
DEBUG=False
SECRET_KEY=<50+ character secure random string>

# Database & Redis
DATABASE_URL=postgresql://postgres:devpass@db:5432/dj01
DB_CONN_MAX_AGE=600
REDIS_URL=redis://redis:6379/0

# Multi-Tenant Configuration
DEFAULT_TENANT_DOMAIN_SUFFIX=statuswatch.kontentwave.digital
ALLOWED_HOSTS=*.statuswatch.kontentwave.digital,statuswatch.kontentwave.digital
CSRF_TRUSTED_ORIGINS=https://*.statuswatch.kontentwave.digital,https://statuswatch.kontentwave.digital
CORS_ALLOWED_ORIGINS=https://statuswatch.kontentwave.digital,https://www.statuswatch.kontentwave.digital

# HTTPS/Security
ENFORCE_HTTPS=True
SECURE_HSTS_SECONDS=3600
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=False
USE_X_FORWARDED_HOST=True
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https

# Stripe (Production Keys)
STRIPE_PUBLIC_KEY=<pk_live_xxxxxxxxxxxxxxxxxxxxx>
STRIPE_SECRET_KEY=<sk_live_xxxxxxxxxxxxxxxxxxxxx>
STRIPE_WEBHOOK_SECRET=<whsec_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx>
STRIPE_PRO_PRICE_ID=<price_xxxxxxxxxxxxxxxxxxxxxxxx>

# Email (SendGrid)
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEFAULT_FROM_EMAIL=noreply@statuswatch.kontentwave.digital
SERVER_EMAIL=alerts@statuswatch.kontentwave.digital

# Frontend
FRONTEND_URL=https://statuswatch.kontentwave.digital

# Monitoring
SENTRY_DSN=https://xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx@sentry.io/xxxxxxx
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_RELEASE=<git-commit-sha>

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
PENDING_REQUEUE_GRACE_SECONDS=90

# Logging
LOG_TO_FILE=1
LOG_DIR=/app/logs

# Image Tag
IMAGE_TAG=edge
```

**Secret Generation:**

```bash
# Django SECRET_KEY (50+ characters)
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# Example output:
# django-q8*x#k@9v$m&3f%h^j!2n+r=w_p7c6b5a4s1d0z-e8t7y6u5i4o3p2
```

### Database Schema Health

**Verification Command:**

```bash
./scripts/db-check.sh
```

**Output (Nov 12, 2025):**

```
📊 Database Information
Database: dj01
Size: 12 MB
Active Connections: 8 / 100

📋 Tenant Schemas
public (main infrastructure)
  └─ statuswatch.kontentwave.digital
acme (demo tenant)
  └─ acme.statuswatch.kontentwave.digital
main (main tenant)
  └─ main.statuswatch.kontentwave.digital

✅ All schemas healthy (12 tables each)
✅ Migrations synchronized
✅ No slow queries detected
```

**Schema Details:**

- **Public Schema:** django-tenants, django_celery_beat, token_blacklist
- **Tenant Schemas:** auth, sessions, admin, endpoints, monitors

**Migration Status:**

```bash
ssh ubuntu@<your-ec2-ip>
cd /opt/statuswatch
dcp run --rm web python manage.py showmigrations
```

```
tenants
 [X] 0001_initial
 [X] 0002_add_localhost_domain
 [X] 0003_add_dev_domains
 [X] 0004_client_subscription_status
 [X] 0005_client_stripe_customer_id
 [X] 0006_alter_client_name
 [X] 0007_add_loopback_domains
 [X] 0008_fix_tenant_domains_production  ← Applied Nov 12

monitors
 [X] 0001_initial
 [X] 0002_endpoint_last_enqueued_at
 [X] 0003_add_performance_indexes
 [X] 0004_remove_endpoint_indexes
```

### Health Check Results

**Command:**

```bash
./scripts/health-check.sh
```

**Full Output (Nov 12, 2025, 22:17 CET):**

```
═══════════════════════════════════════════════════
  StatusWatch Production Health Check
  2025-11-12 22:17:58 CET
═══════════════════════════════════════════════════

ℹ️  Checking SSH connection to EC2...
✅ SSH connection OK

ℹ️  Checking Docker containers...
✅ db is running
✅ redis is running
✅ web is running
✅ worker is running
✅ beat is running
✅ caddy is running

ℹ️  Checking backend health endpoint...
✅ Backend health OK (172ms)

ℹ️  Checking frontend...
✅ Frontend OK (HTTP 200)

ℹ️  Checking PostgreSQL connection...
✅ Database connection OK

ℹ️  Checking Redis connection...
✅ Redis connection OK

ℹ️  Checking disk space...
✅ Disk usage: 62% (threshold: 80%)

ℹ️  Checking memory usage...
✅ Memory usage: 75% (threshold: 80%)

ℹ️  Checking SSL certificate expiry...
✅ SSL cert expires in 88 days

ℹ️  Checking recent errors in logs...
⚠️  Found 1 error lines in recent logs
ℹ️  Run: ssh ubuntu@<your-ec2-ip> 'cd /opt/statuswatch && docker compose logs --tail=50 web'
```

**Error Investigation:**

```bash
./scripts/tail-logs.sh web --errors
```

**Result:** Auth warnings from expired tokens (expected user behavior, not system errors)

```
[WARNING] NotAuthenticated: Authentication credentials were not provided.
[WARNING] InvalidToken: Token is expired
```

**Assessment:** ✅ All critical systems healthy

## Consequences

### Positive

**Security Improvements:**

- ✅ Production defaults to DEBUG=False (prevents information disclosure)
- ✅ HTTPS enforced with HSTS headers
- ✅ Secure cookies prevent session hijacking
- ✅ Automatic TLS certificate management (no manual renewals)
- ✅ Secrets validation at startup (prevents misconfiguration)
- ✅ Rate limiting protects authentication endpoints

**Operational Excellence:**

- ✅ 5 emergency scripts for rapid incident response
- ✅ Comprehensive health monitoring (10 checks)
- ✅ Database diagnostics in one command
- ✅ Live log streaming with error filtering
- ✅ Automated deployment process

**Developer Experience:**

- ✅ Local dev mirrors production (same Docker Compose base)
- ✅ Clear separation between dev/prod settings
- ✅ Django dev server for local (auto-reload, better debugging)
- ✅ No commented code to maintain
- ✅ Easy to audit security configuration

**Multi-Tenant Architecture:**

- ✅ Automatic subdomain routing (tenant1.domain.com)
- ✅ On-demand TLS for each tenant (no manual certificates)
- ✅ Correct domain suffix enforced (environment-specific)
- ✅ Idempotent migrations (safe to re-run)

### Negative

**Complexity:**

- ❌ More files to maintain (4 settings files vs 1)
- ❌ Docker Compose file merging requires understanding
- ❌ Emergency scripts need to be kept in sync with infrastructure

**Migration Debt:**

- ❌ Redundant migrations remain (0002, 0003, 0007 overlap)
- ❌ Migration 0008 is one-time data fix (not schema change)
- ❌ Performance index migrations cancel each other out

**Operational Overhead:**

- ❌ Manual deployment (no CI/CD auto-deploy yet)
- ❌ Health checks require SSH access (not automated alerts)
- ❌ Log rotation needs monitoring (not automated cleanup)

### Mitigations

**Migration Cleanup (Future):**

- Phase 3: Squash overlapping migrations when safe
- Document purpose of each migration in comments
- Add validation tests for migration idempotence

**Automation (Future):**

- Phase 3: GitHub Actions auto-deploy to EC2 via SSH
- Phase 3: Prometheus/Grafana for automated health monitoring
- Phase 3: Automated alerting (Sentry, PagerDuty)

**Documentation:**

- ✅ Comprehensive ADR (this document)
- ✅ EC2 deployment guide (`.github/deployment/EC2_DEPLOYMENT_GUIDE.md`)
- ✅ Docker Compose explained (`.github/deployment/DOCKER_COMPOSE_EXPLAINED.md`)
- ✅ Script usage documented (`scripts/README.md`)

## Related Decisions

- **ADR 01:** Multi-tenant architecture with django-tenants
- **ADR 02:** JWT authentication with token blacklist in public schema
- **ADR 05:** Stripe billing integration with webhooks
- **ADR 07:** Smart multi-tenant login with organization selection

## References

- EC2 Deployment Guide: `.github/deployment/EC2_DEPLOYMENT_GUIDE.md`
- Docker Compose Documentation: `.github/deployment/DOCKER_COMPOSE_EXPLAINED.md`
- Emergency Scripts: `scripts/README.md`
- Caddyfile: `.github/deployment/Caddyfile.ondemand`
- Production Settings: `backend/app/settings_production.py`
- Migration 0008: `backend/tenants/migrations/0008_fix_tenant_domains_production.py`

## Appendix A: Production Checklist

**Pre-Deployment:**

- [x] SECRET_KEY generated (50+ characters)
- [x] DEBUG=False enforced
- [x] ALLOWED_HOSTS configured
- [x] HTTPS/HSTS enabled
- [x] Stripe production keys configured
- [x] SendGrid SMTP credentials configured
- [x] Sentry DSN configured
- [x] DNS wildcard record created
- [x] SSH key configured (`statuswatch-ec2-key.pem`)
- [x] Emergency scripts tested

**Deployment:**

- [x] Docker Compose files deployed to EC2
- [x] Environment variables configured (`.env`)
- [x] Caddyfile deployed
- [x] Database migrations applied
- [x] All containers started
- [x] Health checks passing

**Post-Deployment:**

- [x] Health monitoring verified
- [x] TLS certificates issued
- [x] Multi-tenant login tested
- [x] Endpoint creation tested
- [x] Billing checkout tested
- [x] Celery tasks running
- [x] Log streaming verified
- [x] Emergency scripts operational

## Appendix B: Rollback Plan

**If deployment fails:**

1. Check health: `./scripts/health-check.sh`
2. View errors: `./scripts/tail-logs.sh --errors`
3. Rollback: `dcp down && git checkout <previous-commit> && dcp up -d`
4. Verify: `./scripts/health-check.sh`

**If migration fails:**

1. Rollback migration: `dcp run --rm web python manage.py migrate tenants 0007`
2. Fix migration code
3. Reapply: `dcp run --rm web python manage.py migrate`

**If Caddy fails:**

1. Check logs: `dcp logs caddy`
2. Validate Caddyfile: `dcp exec caddy caddy validate --config /etc/caddy/Caddyfile`
3. Fix syntax and restart: `dcp restart caddy`

## Appendix C: Monitoring Plan (Phase 3)

**Automated Health Checks:**

- Uptime monitoring (StatusCake, Pingdom)
- Endpoint: `https://statuswatch.kontentwave.digital/health/`
- Frequency: Every 5 minutes
- Alert threshold: 2 consecutive failures

**Error Tracking:**

- Sentry for backend exceptions
- Frontend error boundary with Sentry
- Email alerts for critical errors

**Performance Monitoring:**

- Database query time (alert if >1s)
- API response time (alert if >500ms)
- Celery task queue depth (alert if >100)

**Resource Monitoring:**

- Disk space (alert at 80%)
- Memory usage (alert at 85%)
- CPU usage (alert at 90%)
- SSL certificate expiry (alert at 30 days)

**Log Analysis:**

- Centralized logging (CloudWatch, Logtail)
- Error rate trending
- Authentication failure patterns
- Billing event auditing

---

**Status:** ✅ Production deployed and stable  
**Last Updated:** November 12, 2025, 22:30 CET  
**Next Review:** 7 days (post-deployment monitoring)

---

## Related Documentation

- **[← Back to README](../../../../README.md)** - Project overview and quick start
- **[Deployment Guide](../../../deployment/EC2_DEPLOYMENT_GUIDE.md)** - Step-by-step EC2 setup
- **[Diagnostic Scripts](../../../deployment/diag-scripts/README.md)** - Production monitoring tools
- **[Project Documentation](../../StatusWatch_project_sheet.md)** - Complete specifications
- **[All ADRs](../)** - Architecture decision records
