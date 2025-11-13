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

1. ✅ GitHub Actions runs `.github/workflows/publish.yml`
2. ✅ Builds Docker image from `backend/Dockerfile`
3. ✅ Pushes to GHCR: `ghcr.io/kontentwave/statuswatch-web:edge`
4. ❌ **Does NOT run `docker compose`** - that's manual!

**Important:** GitHub Actions **only builds the image**. It doesn't deploy or run containers.

---

## Local Development (WSL2)

### File: `compose.yaml`

**What it includes:**

- ✅ PostgreSQL (port 5432)
- ✅ Redis (port 6379)
- ✅ Web (Django **dev server** - auto-reload, better debugging)
- ✅ Worker (Celery worker)
- ✅ Beat (Celery beat scheduler)
- ❌ **NO Caddy** (you use Nginx/OpenResty)

### Usage:

```bash
cd /home/marcel/projects/statuswatch-project

# Start all services (db, redis, web, worker, beat)
docker compose up -d

# Pull latest images from GHCR
docker compose pull

# View logs
docker compose logs -f
```

**Why no Caddy?**

- You already have Nginx/OpenResty for reverse proxy
- Caddy would conflict on ports 80/443
- Local dev doesn't need HTTPS certificates

---

## Production (EC2)

### Files: `compose.yaml` + `compose.production.yaml`

**What it includes:**

- Everything from `compose.yaml` PLUS:
- ✅ Caddy (reverse proxy + HTTPS/TLS)
- ✅ Data persistence volumes
- ✅ Production environment variables

### Usage on EC2:

```bash
cd /opt/statuswatch

# Start all services INCLUDING Caddy
docker compose -f compose.yaml -f compose.production.yaml up -d

# Pull latest images
export IMAGE_TAG=edge
docker compose -f compose.yaml -f compose.production.yaml pull

# View logs
docker compose -f compose.yaml -f compose.production.yaml logs -f
```

**Or create an alias:**

```bash
# Add to ~/.bashrc on EC2
alias dcp='docker compose -f compose.yaml -f compose.production.yaml'

# Then use:
dcp up -d
dcp logs -f
dcp ps
```

---

## How Compose Override Works

Docker Compose **merges** files from left to right:

```bash
docker compose -f compose.yaml -f compose.production.yaml up
#                     ↑                    ↑
#                   base           production overrides
```

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
