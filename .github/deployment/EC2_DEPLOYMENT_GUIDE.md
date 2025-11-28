# EC2 Deployment Guide - StatusWatch Production

> **Navigation:** [← Back to README](../../README.md) | [Diagnostic Scripts](diag-scripts/README.md) | [ADR: Deployment](../docs/ADRs/Phase%202/08-deployment.md)

---

## Your EC2 File Structure

```
/opt/statuswatch/
├── docker-compose.yml           # Base production config (complete)
├── docker-compose.override.yml  # Forces edge tag
├── .env                         # Environment variables
├── caddy/
│   └── Caddyfile               # Caddy config for HTTPS
├── django-statuswatch/          # Git repo with source code
└── logs/                        # Application logs
```

---

## Your Current Deployment Command

```bash
# What you're currently using (CORRECT!)
cd /opt/statuswatch
dcp up -d --pull always
```

This is the **standard Docker Compose pattern** using your alias! Perfect! 🎯

Your alias: `dcp='docker compose -f docker-compose.yml -f docker-compose.override.yml'`

---

## How It Works

### File 1: `docker-compose.yml` (Base Config)

- Complete production configuration
- Defines all services: db, redis, web, worker, beat, caddy
- Uses `${IMAGE_TAG}` variable
- Production volumes, healthchecks, etc.

### File 2: `docker-compose.override.yml` (Tag Override)

```yaml
services:
  web:
    image: ghcr.io/kontentwave/statuswatch-web:edge
  worker:
    image: ghcr.io/kontentwave/statuswatch-web:edge
  beat:
    image: ghcr.io/kontentwave/statuswatch-web:edge
```

- Overrides the image tag to `edge`
- This file "wins" when merged with docker-compose.yml

---

## Standard Deployment Workflow

### 1. Local - Push Changes

```bash
cd /home/marcel/projects/statuswatch-project
git add -A
git commit -m "fix: Add django_celery_beat to SHARED_APPS"
git push origin main
```

### 2. Wait for GitHub Actions

- Check: https://github.com/KontentWave/django-statuswatch/actions
- Wait for build to complete (~5-10 min)
- New `edge` image pushed to GHCR

### 3. EC2 - Update Code & Deploy

```bash
ssh ubuntu@ec2-13-62-178-108.eu-north-1.compute.amazonaws.com
cd /opt/statuswatch

# Pull new images and restart
dcp pull
dcp up -d

# Check status
dcp ps
dcp logs -f web
```

---

## Simplified Commands (Create Alias)

Add to `/home/ubuntu/.bashrc` on EC2:

```bash
# Docker Compose shortcut for statuswatch (already set up!)
alias dcp='docker compose -f docker-compose.yml -f docker-compose.override.yml'
cd() { builtin cd "$@" && [ "$PWD" = "/opt/statuswatch" ] && echo "✓ Using dcp alias for docker compose"; }

# Reload shell
source ~/.bashrc
```

Then use:

```bash
cd /opt/statuswatch

# Pull latest images
dcp pull

# Start all services
dcp up -d

# Restart specific services
dcp restart web worker beat

# View logs
dcp logs -f web
dcp logs -f beat
dcp logs -f caddy

# Check status
dcp ps

# Stop everything
dcp down

# Remove orphans
dcp up -d --remove-orphans
```

---

## Beat Fix Deployment (Your Current Issue)

### Complete Fix Script

```bash
#!/bin/bash
# Run on EC2 after pushing django_celery_beat fix

cd /opt/statuswatch

# Pull new images with django_celery_beat in SHARED_APPS
dcp pull

# Run migrations to create django_celery_beat tables
dcp run --rm web python manage.py migrate_schemas --shared

# Restart services
dcp up -d

# Wait for startup
sleep 10

# Check Beat status
dcp logs beat --tail 20

# Verify tables exist
dcp exec db psql -U postgres -d dj01 -c "\dt public.django_celery_beat*"
```

### Or simplified:

```bash
cd /opt/statuswatch
dcp pull
dcp run --rm web python manage.py migrate_schemas --shared
dcp up -d
dcp logs beat --tail 20
```

---

## Local vs EC2 Comparison

### Local WSL2

```bash
cd /home/marcel/projects/statuswatch-project

# Uses: compose.yaml only (development config)
docker compose up -d

# Services: db, redis, web, worker, beat
# Reverse proxy: Nginx/OpenResty (separate)
# Logs: ./logs
# Database: Docker volume (ephemeral)
```

### EC2 Production

```bash
cd /opt/statuswatch

# Uses: docker-compose.yml + docker-compose.override.yml
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d

# Services: db, redis, web, worker, beat, caddy
# Reverse proxy: Caddy (in compose)
# Logs: /var/log/statuswatch (persistent)
# Database: Docker volume (persistent: dbdata)
```

---

## File Mapping: Repo → EC2

### In Git Repo (Local)

```
/home/marcel/projects/statuswatch-project/
├── compose.yaml                                # Local dev (no Caddy)
├── .github/deployment/
│   ├── docker-compose.production.yml           # Source of /opt/statuswatch/docker-compose.yml
│   ├── docker-compose.override.yml             # Source of /opt/statuswatch/docker-compose.override.yml
│   └── Caddyfile.ondemand                      # Caddy config synced to EC2
```

> Copy the two compose files from `.github/deployment/` whenever you update infrastructure, e.g. `cp .github/deployment/docker-compose.production.yml /opt/statuswatch/docker-compose.yml`.

### On EC2 Server

```
/opt/statuswatch/
├── docker-compose.yml              # Copy from docker-compose.production.yml
├── docker-compose.override.yml     # Copy from docker-compose.override.yml
├── .env                            # Environment variables (NOT in git!)
├── caddy/
│   └── Caddyfile                   # Copy from .github/deployment/Caddyfile.ondemand
├── django-statuswatch/             # Git repo with source code
│   ├── backend/
│   └── frontend/                   # Source code (for building)
└── frontend-dist/                  # Production build (served by Caddy)
    ├── index.html
    ├── assets/
    └── vite.svg
```

---

## Updating EC2 Compose Files

If you need to update EC2 compose config:

```bash
# Local: Edit and commit
cd /home/marcel/projects/statuswatch-project
vim docker-compose.production.yml
git add docker-compose.production.yml
git commit -m "chore: Update production compose config"
git push

# EC2: Pull and apply
ssh ubuntu@ec2-13-62-178-108.eu-north-1.compute.amazonaws.com
cd /opt/statuswatch/django-statuswatch
git pull

# Copy updated file
cp django-statuswatch/docker-compose.production.yml /opt/statuswatch/docker-compose.yml

# Restart services
cd /opt/statuswatch
dcp up -d --force-recreate
```

---

## Frontend Deployment (Separate from Docker)

The frontend is **NOT** built inside Docker containers. It's built separately and served by Caddy from `/opt/statuswatch/frontend-dist/`.

### Option A: Build on Server (Recommended)

```bash
# SSH to EC2
ssh ubuntu@<your-ec2-ip>

# Pull latest code
cd /opt/statuswatch/django-statuswatch
git pull --ff-only

# Build frontend
cd frontend

# Optional: Use correct Node version (if you have nvm)
nvm use || true

# Install dependencies and build
npm ci
npm run build    # Creates ./dist/ directory

# Deploy to Caddy's document root
sudo rsync -av --delete ./dist/ /opt/statuswatch/frontend-dist/

# Verify deployment
ls -la /opt/statuswatch/frontend-dist/
# Caddy serves files immediately (no restart needed)
```

**Why `sudo rsync`?**

- `/opt/statuswatch/frontend-dist/` may be owned by root
- `--delete` removes old files (cache busting)
- `-av` preserves permissions and shows progress

### Option B: Build Locally and Deploy via rsync

```bash
# On your local machine (WSL2/laptop)
cd /home/marcel/projects/statuswatch-project/frontend

# Install dependencies and build
npm ci
npm run build    # Creates ./dist/ directory

# Deploy to EC2 (push artifacts)
rsync -av --delete \
  --rsync-path="sudo rsync" \
  ./dist/ ubuntu@<your-ec2-ip>:/opt/statuswatch/frontend-dist/

# Verify deployment
ssh ubuntu@<your-ec2-ip> 'ls -la /opt/statuswatch/frontend-dist/'
```

**Benefits of Local Build:**

- Faster (no need to install Node.js/npm on EC2)
- Works from CI/CD pipelines
- Consistent builds (same Node version)
- No build dependencies on production server

### Troubleshooting Frontend Deployment

**Issue: Permission denied**

```bash
# Fix ownership on EC2
ssh ubuntu@<your-ec2-ip>
sudo chown -R ubuntu:ubuntu /opt/statuswatch/frontend-dist/
```

**Issue: Old files still served (cache)**

```bash
# Clear browser cache, or verify files on server
ssh ubuntu@<your-ec2-ip> 'ls -lt /opt/statuswatch/frontend-dist/assets/ | head -10'

# Check file timestamps - should be recent
# Vite uses content hashes in filenames, so new builds = new files
```

**Issue: Blank page / 404 errors**

```bash
# Check Caddy logs
ssh ubuntu@<your-ec2-ip>
cd /opt/statuswatch
dcp logs caddy --tail 50

# Verify Caddyfile path is correct
dcp exec caddy cat /etc/caddy/Caddyfile | grep "root"
# Should show: root * /opt/statuswatch/frontend-dist
```

### Frontend-Only Deployment (No Backend Changes)

```bash
# On server (fastest for quick frontend fixes)
cd /opt/statuswatch/django-statuswatch
git pull --ff-only
cd frontend
npm ci && npm run build
sudo rsync -av --delete ./dist/ /opt/statuswatch/frontend-dist/

# OR from local machine (if you don't have SSH access to build)
npm run build
rsync -av --delete --rsync-path="sudo rsync" \
  ./dist/ ubuntu@<your-ec2-ip>:/opt/statuswatch/frontend-dist/
```

**No service restart needed!** Caddy serves updated files immediately.

---

## Complete Deployment (Backend + Frontend)

### Full Stack Deployment

```bash
# 1. Local: Push all changes
cd /home/marcel/projects/statuswatch-project
git add -A
git commit -m "feat: New feature with frontend + backend changes"
git push origin main

# Wait for GitHub Actions to build backend image (~5 min)
# Check: https://github.com/KontentWave/django-statuswatch/actions

# 3. SSH to EC2
ssh ubuntu@<your-ec2-ip>
cd /opt/statuswatch

# 4. Deploy backend (Docker)
dcp pull                           # Pull latest edge image
dcp up -d                          # Restart containers
dcp run --rm web python manage.py migrate_schemas --shared  # If migrations

# 5. Deploy frontend (built on server)
cd django-statuswatch
git pull --ff-only
cd frontend
npm ci
npm run build
sudo rsync -av --delete ./dist/ /opt/statuswatch/frontend-dist/

# 6. Verify deployment
cd /opt/statuswatch
dcp ps                             # All containers running
dcp logs -f web --tail 20          # Backend logs
curl -I https://statuswatch.kontentwave.digital/  # Frontend (200 OK)
```

---

## Environment Variables on EC2

Your `/opt/statuswatch/.env` file should contain:

```bash
# Database
DATABASE_URL=postgresql://postgres:devpass@db:5432/dj01

# Redis
REDIS_URL=redis://redis:6379/0

# Django
DJANGO_ENV=production
DEBUG=False
SECRET_KEY=<your-secret-key>

# Allowed Hosts & CORS
ALLOWED_HOSTS=*.statuswatch.kontentwave.digital,statuswatch.kontentwave.digital
CSRF_TRUSTED_ORIGINS=https://*.statuswatch.kontentwave.digital,https://statuswatch.kontentwave.digital

# Stripe
STRIPE_PUBLIC_KEY=pk_live_xxx
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRO_PRICE_ID=price_xxx

# Logging
LOG_TO_FILE=1
LOG_DIR=/app/logs

# Image tag (optional - override file handles this)
IMAGE_TAG=edge
```

---

## Summary

Your EC2 setup is **already correct**! You're using:

✅ **Standard Docker Compose pattern**
✅ **Base file** (`docker-compose.yml`) + **Override file** (`docker-compose.override.yml`)
✅ **Correct deployment command** with `-f` flags
✅ **`--pull always`** to get latest images

The only thing needed for the Beat fix:

1. ✅ Push code with `django_celery_beat` in SHARED_APPS (already done locally)
2. ⏳ Wait for GitHub Actions to build new image
3. 🚀 Run migration script on EC2 (see above)

Perfect setup! 🎉

---

## Related Documentation

- **[← Back to README](../../README.md)** - Project overview and quick start
- **[Diagnostic Scripts](diag-scripts/README.md)** - Production monitoring tools
- **[ADR 08: Deployment](../docs/ADRs/Phase%202/08-deployment.md)** - Architecture decisions
- **[Project Documentation](../docs/StatusWatch_project_sheet.md)** - Complete specifications
