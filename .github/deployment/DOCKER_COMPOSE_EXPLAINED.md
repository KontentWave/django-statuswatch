# Docker Compose Files - How They Work

## Overview

This project has **TWO** compose files for **TWO** different environments:

```
compose.yaml             ← Local development (WSL2 + Nginx)
compose.production.yaml  ← EC2 production (with Caddy for HTTPS)
```

---

## How GitHub Actions Works

### When you push backend changes:

```bash
git push origin main
```

**What happens:**

.github/deployment/docker-compose.production.yml ← EC2 production (with Caddy for HTTPS) 2. ✅ Builds Docker image from `backend/Dockerfile` 4. ❌ **Does NOT run `docker compose`** - that's manual!

**Important:** GitHub Actions **only builds the image**. It doesn't deploy or run containers.

---

## Local Development (WSL2)

### File: `compose.yaml`

**What it includes:**
docker compose -f compose.yaml -f .github/deployment/docker-compose.production.yml up -d

- ✅ PostgreSQL (port 5432)
- ✅ Redis (port 6379)
- ✅ Web (Django **dev server** - auto-reload, better debugging)
  docker compose -f compose.yaml -f .github/deployment/docker-compose.production.yml pull
- ✅ Beat (Celery beat scheduler)
- ❌ **NO Caddy** (you use Nginx/OpenResty)
  docker compose -f compose.yaml -f .github/deployment/docker-compose.production.yml logs -f

### Usage:

```bash
cd /home/marcel/projects/statuswatch-project

# Start all services (db, redis, web, worker, beat)
alias dcp='docker compose -f compose.yaml -f .github/deployment/docker-compose.production.yml'

# Pull latest images from GHCR
docker compose pull

# View logs
docker compose logs -f
```

**Why no Caddy?**

- You already have Nginx/OpenResty for reverse proxy
- Caddy would conflict on ports 80/443
- Local dev doesn't need HTTPS certificates

docker compose -f compose.yaml -f .github/deployment/docker-compose.production.yml up

## Production (EC2)

### Files: `compose.yaml` + `compose.production.yaml`

**What it includes:**

- Everything from `compose.yaml` PLUS:
- ✅ Caddy (reverse proxy + HTTPS/TLS)
- ✅ Data persistence volumes
- ✅ Production environment variables

### Usage on EC2:

````bash

# Start all services INCLUDING Caddy
docker compose -f compose.yaml -f compose.production.yaml up -d

# Pull latest images
export IMAGE_TAG=edge
docker compose -f compose.yaml -f compose.production.yaml pull
docker compose -f compose.yaml -f .github/deployment/docker-compose.production.yml pull
# View logs
docker compose -f compose.yaml -f compose.production.yaml logs -f
docker compose -f compose.yaml -f .github/deployment/docker-compose.production.yml up -d --force-recreate

**Or create an alias:**
docker compose -f compose.yaml -f .github/deployment/docker-compose.production.yml ps
```bash
# Add to ~/.bashrc on EC2

# Then use:
dcp up -d
dcp logs -f
dcp ps
````

docker compose -f compose.yaml -f .github/deployment/docker-compose.production.yml up -d
docker compose -f compose.yaml -f .github/deployment/docker-compose.production.yml logs -f caddy
docker compose -f compose.yaml -f .github/deployment/docker-compose.production.yml ps

Docker Compose **merges** files from left to right:

```bash
docker compose -f compose.yaml -f compose.production.yaml up
#                     ↑                    ↑
#                   base           production overrides
```

## Modular Stack (refactor/mod-monolith)

Use this stack when experimenting with the parallel "mod-monolith" architecture so the existing services keep running untouched.

### Files

- `docker-compose.mod.yml` (top level)
- `backend/.env.mod` (copy from `.env.mod.example`)
- `frontend/.env.development.local` (points Vite at `http://acme.localhost:8081`)
- `.mod-data/` (local volumes for the mod DB/Redis/logs – ignored by git)

### 1. Build + tag the backend image

```bash
docker build \
  --file backend/Dockerfile \
  --tag statuswatch-backend:mod \
  backend
```

### 2. Prepare env files

```bash
cp backend/.env.mod.example backend/.env.mod
cp frontend/.env.example frontend/.env.development.local  # keep only the mod overrides
```

Fill in the DB/Redis URLs plus Stripe keys in `backend/.env.mod`, and set `VITE_BACKEND_ORIGIN=http://acme.localhost:8081` in the frontend env so the browser hits the mod API container via the dev proxy.

### 3. Bring the stack up

```bash
docker compose -f docker-compose.mod.yml up -d
docker compose -f docker-compose.mod.yml ps
```

Services start as `mod_db`, `mod_redis`, `mod_api`, `mod_worker`, `mod_beat`, and `mod_frontend`. All volumes/logs live under `.mod-data/` so they stay isolated.

### 4. Run migrations + seed tenants

```bash
docker compose -f docker-compose.mod.yml exec mod_api python manage.py migrate_schemas --shared
docker compose -f docker-compose.mod.yml exec mod_api python manage.py migrate_schemas --tenant
docker compose -f docker-compose.mod.yml exec mod_api python manage.py shell  # create tenant + superuser
```

After seeding, update `/etc/hosts` with `acme.localhost` → `127.0.0.1` and verify the dashboard via `http://acme.localhost:5173` (frontend dev server) or `:8081` (mod Nginx).

### 5. Frontend toggle

Stop the regular Vite dev server before launching the mod version:

```bash
cd frontend
npm run dev -- --host acme.localhost --port 5173
```

Make sure the `.env.development.local` file points at the mod API so TanStack Query hits the right origin.

### 6. Teardown / cleanup

```bash
docker compose -f docker-compose.mod.yml down
docker compose -f docker-compose.mod.yml down -v  # drop mod volumes if you want a clean slate
```

Logs remain under `.mod-data/logs/` for later inspection without polluting the default stack.

---

**Example:**

**`compose.yaml` (base):**

```yaml
services:
  web:
    environment:
      DJANGO_ENV: development
```

**`compose.production.yaml` (override):**

```yaml
services:
  web:
    environment:
      DJANGO_ENV: production # ← This overwrites development
```

**Result on EC2:**

```yaml
services:
  web:
    environment:
      DJANGO_ENV: production # ← production wins!
```

---

## The Full Pipeline

### 1. Development (Local WSL2)

```bash
# Write code
vim backend/api/views.py

# Commit and push
git add -A
git commit -m "feat: new endpoint"
git push origin main
```

### 2. GitHub Actions (Cloud)

```bash
# Automatically triggered by push
# - Builds Docker image
# - Pushes to ghcr.io/kontentwave/statuswatch-web:edge
# - Takes ~3-5 minutes
```

### 3. Deployment (EC2)

```bash
# SSH to EC2
ssh ubuntu@ec2-13-62-178-108.eu-north-1.compute.amazonaws.com

# Pull latest code
cd /opt/statuswatch/django-statuswatch
git pull

# Pull new Docker images
cd /opt/statuswatch
export IMAGE_TAG=edge
docker compose -f compose.yaml -f compose.production.yaml pull

# Restart services
docker compose -f compose.yaml -f compose.production.yaml up -d --force-recreate

# Check status
docker compose -f compose.yaml -f compose.production.yaml ps
```

---

## Quick Reference

### Local (WSL2)

```bash
docker compose up -d                    # Start
docker compose down                     # Stop
docker compose logs -f web              # View logs
docker compose exec web python manage.py shell  # Django shell
```

### Production (EC2)

```bash
# Use the full command or create alias
docker compose -f compose.yaml -f compose.production.yaml up -d
docker compose -f compose.yaml -f compose.production.yaml logs -f caddy
docker compose -f compose.yaml -f compose.production.yaml ps
```

---

## Why This Approach?

### ✅ Advantages

- **Single source of truth**: Base config in `compose.yaml`
- **No duplication**: Production only defines differences
- **Clean separation**: Dev vs prod is explicit
- **Easy to maintain**: Changes to base apply everywhere
- **No commented code**: Each file is clean and readable

### ❌ Alternative (what we had before)

```yaml
# compose.yaml with commented sections
# caddy:  ← UGLY! Hard to maintain
#   image: caddy:2
#   ...
```

**Problems:**

- Confusing which sections are active
- Easy to forget to uncomment on EC2
- Hard to see what's actually running
- Messy git diffs when toggling comments

---

## Summary

**Question:** When I push backend changes, does `compose.yaml` get called?

**Answer:** NO! Here's what actually happens:

1. **GitHub Actions** runs → Builds image → Pushes to GHCR
2. **You manually** run `docker compose` on your machine (local or EC2)
3. **Compose pulls** the new image from GHCR
4. **Containers restart** with the new code

**Workflow:**

```
Your code → GitHub Actions → GHCR image → You pull → Containers restart
         (automatic)              (manual)
```

The commented Caddy lines were just a way to have **one file for two environments**. Now we have **two files** which is cleaner! 🎉
