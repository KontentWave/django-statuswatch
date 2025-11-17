# ADR 11: Shared Settings Router & Logging Helper

> **Navigation:** [← Back to Project Sheet](../../StatusWatch_project_sheet.md) | [Phase 3 ADRs](../Phase%203/) | Related ADRs: [ADR 02 – Billing Service Extraction](10-billing-module-extraction.md)

---

**Date:** November 16, 2025  
**Status:** Implemented  
**Decision Makers:** Solo developer (Marcel)  
**Tags:** #settings #logging #environment-routing

## Context

Phase 3 refactors have been consolidating Django settings and modularizing cross-cutting concerns. After extracting billing logic, the next structural gap was inconsistent environment detection/logging across entrypoints:

- `app/settings.py` performed its own DJANGO_ENV/DEBUG parsing and logger wiring using emoji-laden messages.
- `app/asgi.py`, `app/wsgi.py`, `app/celery.py`, and `manage.py` simply set `DJANGO_SETTINGS_MODULE` and depended on Django defaults, so they logged nothing about which settings file was loaded.
- Diagnosing misconfigured deployments (e.g., DEBUG accidentally true, missing env vars in Celery workers) required guessing because each entrypoint behaved differently.

The goal was to centralize environment routing + boot logging so every process (web, Celery worker/beat, manage.py) emits the same metadata and shares the same fallback rules.

## Decision Drivers

1. **Observability parity** – any process booting Django should state which settings module/environment it picked and why.
2. **Single source of truth** – avoid copy/pasted DJANGO_ENV/DEBUG parsing logic that drifts over time.
3. **Reusability** – future entrypoints (scripts, tests) can hook into the helper with one import.
4. **Operational safety** – default to production when env vars are absent, but expose logs so misconfiguration is obvious.
5. **ASCII-only logging** – earlier emoji logs broke some terminals; the solution should default to portable text.

## Decision

- Added `modules/core/settings/logger.py` exporting `setup_settings_logging()` and `SettingsLoggingContext`.
  - Handles `DJANGO_ENV` / `DEBUG` evaluation with explicit source labeling.
  - Creates/ensures a rotating file handler at `logs/settings.log` plus a console handler (once per logger name).
  - Logs the selected settings module, `BASE_DIR`, and `LOG_DIR`, using ASCII messages.
- Re-exported the helper via `modules/core/settings/__init__.py` so it can be imported with other settings utilities.
- Updated `app/settings.py`, `app/asgi.py`, `app/wsgi.py`, `app/celery.py`, and `manage.py` to call the helper with scoped logger names (e.g., `app.settings_loader.celery`) before Django initializes.
- Ensured tests continue to rely on the shared helper by running `pytest tests/test_admin_url.py` after each batch of changes.

## Consequences

- Every process that loads Django now writes consistent log lines about environment selection and paths, simplifying incident response.
- Environment routing rules live in one place; changing fallback behavior or log formatting no longer requires editing multiple files.
- Entry points remain small: they set `DJANGO_SETTINGS_MODULE`, call `setup_settings_logging(...)`, then delegate to Django.
- The helper enforces ASCII output, so CI logs and minimal terminals handle the messages without encoding issues.
- Future scripts that call `django.setup()` can opt in by importing the helper, matching the guidance recorded here.

## Validation

1. Unit/regression: `pytest tests/test_admin_url.py -q` (green after helper addition and after wiring each entrypoint).
2. Manual smoke: ran `python backend/manage.py check` locally to confirm the helper logs once and Django still boots.
3. Logging inspection: Verified new `logs/settings.log` entries for ASGI/WSGI/Celery/manage.py, confirming environment detection strings and absence of emojis.

---

```bash
cd backend
pytest tests/test_admin_url.py -q
```
