# Local Dev Runbook

This is the current local setup that matches the repo's working development flow.

## Recommended Mode

Use the HTTPS frontend on port `5173` and the modular backend stack on port `8081`.

- Frontend: `https://localhost:5173`
- Tenant frontend: `https://acme.localhost:5173`
- Modular backend health: `http://localhost:8081/health/`
- Legacy backend health: `http://localhost:8003/health/`

The repo still contains both the legacy stack and the modular stack. Prefer the modular stack for daily local work.

## Prerequisites

- Docker + Docker Compose
- Node.js 20+
- `/etc/hosts` entries for local tenant routing

Add these host mappings if they are missing:

```text
127.0.0.1 localhost
127.0.0.1 acme.localhost
```

## Env Files

Active local env values should line up like this:

- Root env in [.env](../../.env): `FRONTEND_URL=https://localhost:5173`
- Modular env in [backend/.env.mod](../../backend/.env.mod): `FRONTEND_URL=https://acme.localhost:5173`
- Modular Stripe values in [backend/.env.mod](../../backend/.env.mod) must be real Stripe test credentials, not placeholders:
  - `STRIPE_PUBLIC_KEY=pk_test_...`
  - `STRIPE_SECRET_KEY=sk_test_...`
  - `STRIPE_PRO_PRICE_ID=price_...`
  - `STRIPE_WEBHOOK_SECRET=whsec_...` for local webhook testing

When you change values loaded through Docker `env_file`, recreate the affected containers. A plain restart does not reload env files.

## Start The Modular Stack

From the repo root:

```bash
cp backend/.env.mod.example backend/.env.mod
docker compose -f compose.yaml -f docker-compose.mod.yml up -d --build mod_db mod_redis mod_api mod_worker mod_beat
docker compose -f compose.yaml -f docker-compose.mod.yml exec mod_api python manage.py migrate_schemas --shared
docker compose -f compose.yaml -f docker-compose.mod.yml exec mod_api python manage.py migrate_schemas
```

The modular stack is intended to run the local backend source from this workspace. After backend code changes, `mod_api` picks them up automatically through Django's dev server reload. Recreate `mod_worker` and `mod_beat` when you need Celery to load backend code changes.

## Start The Frontend

From `frontend/`:

```bash
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

If local dev certificates exist at the configured paths, Vite serves HTTPS only. In that case, use `https://...:5173`, not `http://...:5173`.
You may need to accept the local browser certificate warning once.
If the configured certificate only covers `localhost` and not `acme.localhost`, direct tenant-subdomain visits can trigger browser certificate warnings or blank pages during login handoff. For demo/local verification, either accept the browser warning for `acme.localhost` or use a dev certificate whose SAN includes both `localhost` and `acme.localhost`.

## Working URLs

- Public home: `https://localhost:5173/`
- Public login: `https://localhost:5173/login`
- Public register: `https://localhost:5173/register`
- Tenant dashboard/login flows: `https://acme.localhost:5173/`
- Modular backend direct API/health: `http://localhost:8081/`

## Demo Flow

- Open `https://localhost:5173/`
- Use the demo login button on the homepage
- You should land on `https://acme.localhost:5173/dashboard`
- Billing should open at `https://acme.localhost:5173/billing`

If the demo login button stalls on the public origin, verify two local prerequisites first:

- the `acme` tenant still has a single canonical `jwt@example.com` demo user with `email_verified=True`
- the browser trusts the HTTPS certificate presented for `https://acme.localhost:5173`

## Legacy Stack Notes

Legacy local services still exist in `compose.yaml`:

- Django web: port `8003`
- Postgres: port `5432`
- Redis: port `6379`

If `beat` exits immediately with an error like `django_celery_beat_crontabschedule does not exist`, run:

```bash
docker compose exec web python manage.py migrate_schemas --shared
docker compose exec web python manage.py migrate_schemas
docker compose up -d beat
```

## Common Fixes

If billing shows `Payment system authentication failed.` after clicking `Upgrade to Pro`, the backend is reaching Stripe with invalid or placeholder credentials. Replace the Stripe values in [backend/.env.mod](../../backend/.env.mod) with real Stripe test keys and a valid recurring Pro price ID from your Stripe dashboard, then recreate the modular containers:

```bash
docker compose -f compose.yaml -f docker-compose.mod.yml up -d --build --force-recreate mod_api mod_worker mod_beat
docker compose -f compose.yaml -f docker-compose.mod.yml exec mod_api python manage.py shell -c "from django.conf import settings; print(settings.STRIPE_SECRET_KEY[:7], settings.STRIPE_PRO_PRICE_ID)"
```

If the frontend works on `https://localhost:5173` but redirects or email/billing links use the wrong origin:

```bash
docker compose up -d --force-recreate web worker beat
docker compose -f compose.yaml -f docker-compose.mod.yml up -d --build --force-recreate mod_api mod_worker mod_beat
```

If you want to confirm what Django is using:

```bash
docker compose exec web python manage.py shell -c "from django.conf import settings; print(settings.FRONTEND_URL)"
docker compose -f compose.yaml -f docker-compose.mod.yml exec mod_api python manage.py shell -c "from django.conf import settings; print(settings.FRONTEND_URL)"
docker compose -f compose.yaml -f docker-compose.mod.yml exec mod_api python manage.py shell -c "from django.conf import settings; print(settings.STRIPE_SECRET_KEY[:7], settings.STRIPE_PRO_PRICE_ID)"
```
