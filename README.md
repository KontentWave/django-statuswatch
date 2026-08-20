# StatusWatch

**Multi-tenant SaaS uptime monitoring platform** — Monitor website availability with automated HTTP checks, real-time status dashboards, and Stripe-powered subscription plans.

Built as a production-ready demonstration of modern web architecture, deployment automation, and operational best practices.

---

## 🎯 Live Demo

- **Production:** https://statuswatch.kontentwave.digital/
- **Demo Tenant:** `acme.statuswatch.kontentwave.digital`

---

## ⚡ Tech Stack

**Backend:**

- Django 5.1 + Django REST Framework
- Multi-tenant architecture (django-tenants with schema-based isolation)
- PostgreSQL 16 (tenant schemas)
- Redis 7 (Celery broker)
- Celery Beat + Worker (automated endpoint monitoring)

**Frontend:**

- React 19 + TypeScript + Vite
- TanStack Router + TanStack Query + TanStack Table
- shadcn/ui + Tailwind CSS
- Stripe integration for subscriptions

**Infrastructure:**

- Docker Compose (development + production)
- Caddy 2 (reverse proxy with on-demand TLS for wildcard subdomains)
- GitHub Actions (CI/CD to GitHub Container Registry)
- AWS EC2 (production deployment)

---

## 🚀 Quick Start (Local Development)

### Prerequisites

- Docker + Docker Compose
- Python 3.12+ (pyenv recommended)
- Node.js 20+ (nvm recommended)

### Recommended Local Mode

The repo currently contains two local backend paths:

- the legacy stack from `compose.yaml`
- the modular stack from `docker-compose.mod.yml`

For day-to-day local work, use the modular stack plus the HTTPS Vite frontend. This is the path that currently matches the working tenant flow.

### 1. Backend Setup

```bash
# Clone repository
git clone https://github.com/KontentWave/django-statuswatch.git
cd django-statuswatch

# Copy the modular env template if needed
cp backend/.env.mod.example backend/.env.mod

# Start modular backend services
docker compose -f compose.yaml -f docker-compose.mod.yml up -d --build mod_db mod_redis mod_api mod_worker mod_beat

# Run migrations
docker compose -f compose.yaml -f docker-compose.mod.yml exec mod_api python manage.py migrate_schemas --shared
docker compose -f compose.yaml -f docker-compose.mod.yml exec mod_api python manage.py migrate_schemas

# Optional: inspect backend health
curl http://localhost:8081/health/
```

### 2. Frontend Setup

```bash
# In a new terminal
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev -- --host 0.0.0.0 --port 5173
```

No frontend env override is required for the current working modular flow.

### 3. Access Application

- **Frontend:** https://localhost:5173
- **Tenant Frontend:** https://acme.localhost:5173
- **Modular Backend API/Health:** http://localhost:8081/
- **Legacy Backend API/Health:** http://localhost:8003/

**Create your first tenant:**

1. Register at `https://localhost:5173/register`
2. Your tenant will be available at `https://{your-org}.localhost:5173`

### 4. Required Local Hosts Entry

Add this to `/etc/hosts` if local tenant routing does not resolve:

```text
127.0.0.1 acme.localhost
```

### 5. Notes

- If Vite finds local SSL certs, it serves HTTPS only. Use `https://...:5173`, not `http://...:5173`.
- Accept the local browser certificate warning once if Firefox or Chromium prompts for it.
- The modular stack builds from `backend/` and bind-mounts that source into the dev containers, so local backend code changes affect the modular API directly.
- If you change values loaded through Docker `env_file`, recreate the containers with `up -d --build --force-recreate`; `restart` does not reload env files.
- See [.github/docs/LOCAL_DEV_RUNBOOK.md](.github/docs/LOCAL_DEV_RUNBOOK.md) for the current working local runbook.

---

## 📦 Production Deployment

This project includes a **complete production deployment** on AWS EC2:

- **Docker-based deployment** using GitHub Container Registry
- **Automated builds** via GitHub Actions
- **On-demand TLS** for wildcard tenant subdomains (\*.statuswatch.kontentwave.digital)
- **Frontend built separately** and served from host filesystem
- **5 operational diagnostic scripts** for production monitoring

Compose overrides live under `.github/deployment/`:

- `.github/deployment/docker-compose.production.yml` — merges with `compose.yaml` for EC2
- `.github/deployment/docker-compose.override.yml` — pins the `edge` tag for web/worker/beat during deploys

Use them with:

```bash
docker compose -f compose.yaml -f .github/deployment/docker-compose.production.yml up -d
```

👉 **See:** [`.github/deployment/EC2_DEPLOYMENT_GUIDE.md`](.github/deployment/EC2_DEPLOYMENT_GUIDE.md)

### Emergency Diagnostic Scripts

Production-ready scripts for 2AM incidents:

```bash
.github/deployment/diag-scripts/health-check.sh           # 10 health checks (SSL, DB, Redis, disk, memory)
.github/deployment/diag-scripts/db-check.sh               # Database diagnostics
.github/deployment/diag-scripts/emergency-restart.sh      # Safe container restart
.github/deployment/diag-scripts/tail-logs.sh --errors     # Live error monitoring
.github/deployment/diag-scripts/deploy.sh                 # Deployment automation
```

👉 **See:** [`.github/deployment/diag-scripts/README.md`](.github/deployment/diag-scripts/README.md)

---

## 🏗️ Architecture & Documentation

### High-Level Architecture

- **Multi-tenant SaaS:** Each organization gets isolated database schema
- **Subdomain routing:** `{tenant}.statuswatch.kontentwave.digital`
- **JWT authentication:** Token-based auth with refresh tokens
- **Celery monitoring:** Background tasks for endpoint health checks
- **Stripe subscriptions:** Free tier + Pro plan ($9/month)

### Detailed Documentation

- **[Project Overview](.github/docs/StatusWatch_project_sheet.md)** - Complete feature specifications, implementation notes, and audit summaries
- **[Architecture Decision Records (ADRs)](.github/docs/ADRs/)** - Design decisions and rationale
  - [Phase 2: Production Deployment](.github/docs/ADRs/Phase%202/08-deployment.md)
- **[Deployment Guide](.github/deployment/EC2_DEPLOYMENT_GUIDE.md)** - Complete EC2 setup and workflows
- **[Diagnostic Scripts](.github/deployment/diag-scripts/README.md)** - Production monitoring tools

---

## 🔑 Key Features

### Phase 1 (MVP) ✅

- ✅ User registration with automatic tenant provisioning
- ✅ JWT-based authentication (login/logout/refresh)
- ✅ CRUD operations for monitored endpoints
- ✅ Automated HTTP health checks via Celery
- ✅ Real-time status dashboard
- ✅ Multi-tenant isolation (schema-based)

### Phase 2 (Production-Ready) ✅

- ✅ Stripe subscription checkout integration
- ✅ Tenant subdomain routing with on-demand TLS
- ✅ Production deployment on AWS EC2
- ✅ CI/CD pipeline (GitHub Actions → GHCR)
- ✅ Operational monitoring scripts
- ✅ Security hardening (HTTPS, HSTS, CSP, rate limiting)
- ✅ Comprehensive test coverage (88% backend)

---

## 🛠️ Development Commands

### Backend

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=. --cov-report=html

# Code quality
black .
ruff check .
mypy .

# Migrations
python manage.py makemigrations
python manage.py migrate_schemas --shared  # Public schema
python manage.py migrate_schemas           # All tenant schemas
python manage.py reset_e2e_data            # Clean tenant data for E2E runs (DEBUG only)
```

**Monitoring smoke check:**

```bash
pytest tests/test_monitors_tasks_module.py tests/test_ping_tasks.py
```

Run this focused command whenever you touch `monitors.tasks` or the Celery monitoring pipeline to quickly ensure the re-export contract and ping workflow still pass.

### Frontend

```bash
# Run tests
npm test

# Build for production
npm run build

# Lint
npm run lint

# Format
npm run format
```

### End-to-End Tests (Playwright)

Playwright lives under `frontend/e2e/` and exercises the `/register → /login` flow end-to-end.

```bash
# Terminal 1 – backend API (ensure Postgres/Redis running)
cd backend && python manage.py runserver 0.0.0.0:8000

# Terminal 2 – frontend dev server
cd frontend && npm run dev

# Terminal 3 – Playwright tests (resets tenant data automatically)
cd frontend && npm run test:e2e
```

Notes:

- `frontend/e2e/global-setup.ts` invokes `python manage.py reset_e2e_data --force` before the test suite so every run starts from a blank slate.
- Set `PLAYWRIGHT_BASE_URL` to override the default `http://localhost:5173` or `PLAYWRIGHT_SKIP_RESET=1` if you need to retain data between runs.
- Additional scripts:
  - `npm run test:e2e:headed` – debug in headed mode with a single worker
  - `npm run test:e2e:report` – open the last HTML report

---

## 📊 Production Metrics

- **Security Score:** 🟢 Production-ready (0 critical vulnerabilities)
- **Test Coverage:** 88% backend, Vitest suites for frontend
- **Performance:** API response <100ms, scheduler handles 10k+ endpoints
- **Uptime:** Health checks every 5 minutes, SSL monitoring
- **Technical Debt:** 10-15% (industry avg: 30%)

---

## 📝 License

MIT License - See [LICENSE](LICENSE) for details

---

## 🤝 Contributing

This is a portfolio/demonstration project. For production use cases or questions:

- **Issues:** Please open an issue for bugs or feature requests
- **Pull Requests:** Contributions welcome!

---

## 🙏 Acknowledgments

Built with modern best practices for:

- Multi-tenant SaaS architecture
- Production deployment automation
- Operational excellence and monitoring
- Security-first development

---

**Maintained by:** [KontentWave](https://github.com/KontentWave)  
**Last Updated:** December 1, 2025
