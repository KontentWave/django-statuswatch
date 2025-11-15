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

### 1. Backend Setup

```bash
# Clone repository
git clone https://github.com/KontentWave/django-statuswatch.git
cd django-statuswatch

# Start services (PostgreSQL + Redis)
docker compose up -d

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
cd backend
pip install -r requirements.txt

# Copy environment template
cp ../.env.example ../.env

# Run migrations
python manage.py migrate_schemas --shared
python manage.py migrate_schemas

# Create superuser (optional)
python manage.py createsuperuser

# Start development server
python manage.py runserver 0.0.0.0:8000
```

### 2. Frontend Setup

```bash
# In a new terminal
cd frontend

# Install dependencies
npm install

# Copy environment template
cp .env.example .env

# Start dev server
npm run dev
```

### 3. Access Application

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000/api/
- **Admin Panel:** http://localhost:8000/admin/

**Create your first tenant:**

1. Register at http://localhost:5173/register
2. Your tenant will be available at `{your-org}.localhost:5173`

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
**Last Updated:** November 13, 2025
