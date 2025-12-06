---
title: "ADR 13 – Playwright E2E Testing"
status: Accepted
date: 2025-12-05
---

## Context

StatusWatch already exercised its core flows through unit and integration tests, but we lacked coverage for the customer-facing registration experience and no automation existed to prove the full stack (frontend ↔ backend ↔ tenants) works after code changes. Manual smoke tests were expensive, and regressions in throttling/tenant provisioning frequently slipped into PRs. Phase 4 therefore required a thin-yet-real end-to-end harness that can grow alongside the modular monolith work.

## Decision

- Adopt **Playwright** (tests live in `frontend/e2e/`) as the canonical browser automation tool.
- Ship Phase 1 with a single “new visitor provisions an organization” scenario to validate plumbing before expanding coverage.
- Reset backend data before every run using a purpose-built Django management command so tests remain deterministic.
- Run the suite locally and in CI against the **modular compose stack** (`compose.yaml + docker-compose.mod.yml`) to mirror the eventual production topology.
- Gate every PR with a dedicated `Playwright E2E` workflow that uploads traces/screenshots on failure and never touches production resources.

## Implementation Details

### Test Harness

- `frontend/e2e/specs/auth.spec.ts` drives the happy-path registration UI, asserting the success toast and redirect to `/login`.
- Page helpers live in `frontend/e2e/pages/auth-page.ts` with shared data builders under `frontend/e2e/support/registration-data.ts`.
- `playwright.config.ts`:
  - Detects `VITE_DEV_SERVER_URL`/TLS certs to pick the base URL.
  - Defines Chromium/Firefox/WebKit projects, `trace: on-first-retry`, screenshot/video capture, and `globalSetup`.
  - Reads `PLAYWRIGHT_BASE_URL` / `PLAYWRIGHT_SKIP_RESET` for advanced workflows.
- `frontend/e2e/global-setup.ts` calls `reset_e2e_data` via `python manage.py` unless `PLAYWRIGHT_SKIP_RESET=1`. The helper honors `PLAYWRIGHT_MANAGE_PATH` and `PLAYWRIGHT_PYTHON_BIN` for containerized runs.

### Backend Test Data Command

- `backend/api/management/commands/reset_e2e_data.py` drops every tenant schema, removes orphan `Domain` rows, and preserves the `public` schema so migrations stay intact.
- Guarded by `DEBUG`/`--force` to ensure the command is never invoked accidentally in production.
- Emits structured logs so Playwright runs show up in CI output.

### CI/CD Workflow

- `.github/workflows/e2e.yml` runs on pushes + PRs:
  1.  Checks out the repo and installs Node/Playwright dependencies.
  2.  Ensures `backend/.env` and `backend/.env.mod` exist (copied from examples committed to git).
  3.  Pulls the published `ghcr.io/kontentwave/statuswatch-web:edge` image so the modular services (`mod_api`, `mod_worker`, `mod_beat`) match the latest backend build.
  4.  Spins up `mod_db`/`mod_redis`, runs `python manage.py migrate` + `reset_e2e_data` inside `mod_api`, then brings up the rest of the stack.
  5.  Starts `npm run dev -- --host 0.0.0.0 --port 5173` in the background, exports `PLAYWRIGHT_SKIP_RESET=1`, and executes `npx playwright test`.
  6.  Uploads `frontend/playwright-report` + `frontend/test-results` when failures occur, and tears down both the dev server and compose stack in `finally` blocks.
- The pipeline never connects to production; everything runs on the ephemeral GitHub runner.

### Local Workflow

```bash
# Backend
cd backend
python manage.py reset_e2e_data --force

# Frontend
cd ../frontend
PLAYWRIGHT_BASE_URL=https://localhost:5173 npm run test:e2e
```

Developers can set `PLAYWRIGHT_SKIP_RESET=1` when they want to iterate quickly against an existing database snapshot.

### Observability

- Playwright logs announce the reset command, making it obvious in CI output when/if it fails.
- `docker-compose.mod.yml` still exposes `logs/mod/*.log`, so any backend errors triggered by the suite appear alongside normal worker output.

## Consequences & Future Work

- ✅ Registration flow now has full-stack regression coverage with <40s runtime (all three browsers, single worker).
- ✅ E2E jobs are isolated from production and reuse the modular stack, so upcoming cutover work reaps the same benefits.
- 🚧 Next milestones include: smart multi-tenant login playback, monitors CRUD (with Celery assertions), billing upgrade + Stripe portal redirect, and authentication storage-state reuse to shorten runtime.
- 🚧 Once coverage grows, evaluate splitting specs across two jobs (headless vs headed) and caching the Playwright browser binaries between runs.
