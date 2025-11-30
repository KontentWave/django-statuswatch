# ADR 12: Modular Stack Cutover & Tenant Domain Cleanup

> **Navigation:** [← Back to Project Sheet](../../StatusWatch_project_sheet.md) | [Phase 3 ADRs](../Phase%203/) | Related ADRs: [ADR 09 – Modular Auth Refresh Alignment](09-auth-refresh-alignment.md), [ADR 10 – Billing Service Extraction](10-billing-module-extraction.md), [ADR 11 – Shared Settings Router & Logging Helper](11-shared-settings-router.md)

---

**Date:** November 30, 2025  
**Status:** Implemented  
**Decision Makers:** Solo developer (Marcel)  
**Tags:** #deployment #modular-monolith #tenants #operations

## Context

Phase 3 introduced a parallel "mod" stack (`docker-compose.mod.yml`) so we could refactor the Django project into a modular monolith without destabilizing production. By late November the modular images (`ghcr.io/kontentwave/statuswatch-web:mod`) had parity with the legacy stack, but production was still running the legacy layout and the documented cutover steps only lived in `StatusWatch_project_sheet.md`. During final smoke tests we also found that the demo login still redirected to `acme.staging.statuswatch.kontentwave.digital` because stale tenant-domain rows were left in Postgres. We needed an auditable decision that (a) locks the modular stack in as the production baseline and (b) codifies the tenant-domain cleanup that unblocked the cutover.

## Decision Drivers

1. **Isolated rehearsals** – ability to run the modular API/worker/beat plus dedicated Postgres/Redis alongside the legacy services for blue/green validation.
2. **Deterministic cutover** – production should consume the same compose overlay and image tags we test locally to avoid “worked on my laptop” mismatches.
3. **Tenant safety** – demo/public tenants must only reference production hostnames so login shortcuts never leak users back to staging domains.
4. **Rollback clarity** – reverting to the legacy image must stay trivial (compose tag swap + overlay removal) if an unknown regression appears.

## Decision

1. **Adopt the modular image + overlay everywhere.** The `ghcr.io/kontentwave/statuswatch-web:mod` tag becomes the default for `web`, `worker`, and `beat` in production. Local/staging environments load the same code via `docker compose -f compose.yaml -f docker-compose.mod.yml` (or the production compose + mod override) so rehearsals and the real cutover share identical manifests.
2. **Keep the mod stack isolated.** The overlay provisions dedicated services (`mod_api`, `mod_worker`, `mod_beat`, `mod_db`, `mod_redis`) on alternate ports plus their own volumes. Frontend smoke tests point to `http://acme.localhost:8081` (via `VITE_BACKEND_ORIGIN`) during rehearsals, then revert once the modular services replace legacy containers.
3. **Enforce canonical tenant domains.** Production now treats `*.statuswatch.kontentwave.digital` as the only allowed suffix. We promoted the existing `acme.statuswatch.kontentwave.digital` record to `is_primary=true` and deleted every row containing `.staging.statuswatch.kontentwave.digital`, ensuring demo login always lands on the production domain. Future migrations (`DEFAULT_TENANT_DOMAIN_SUFFIX`) prevent `.staging` suffixes from reappearing.
4. **Document rollback + diagnostics.** The cutover doc spells out how to revert (`docker compose ... pull ghcr.io/...:edge && docker compose ... up -d web worker beat`) and references the diagnostic scripts that validate tenant domains (`scripts/diagnose-tenant-domains.sh`) so incidents can be triaged quickly.

## Consequences

- Production, staging, and local dev now share a single compose overlay + image tag, so every smoke test exercises the exact artifacts that ship.
- Engineers must keep the mod overlay healthy; compose changes always need to touch both the legacy stack and `docker-compose.mod.yml` until the legacy services are retired.
- Tenant provisioning scripts inherit the stricter domain suffix defaults; manual DB edits must honor the canonical suffix or the login helpers break.
- The additional containers increase resource usage during rehearsals, but the isolation eliminates accidental double-processing or schema conflicts.
- Rollbacks remain low-risk: swapping image tags or dropping the overlay immediately returns the legacy stack without touching databases.

## Validation

1. **Manual smoke tests (Nov 30):** Used the production demo login button and dashboard flows against the modular containers (edge→mod tag) to confirm authentication, endpoint CRUD, billing upgrade redirects, and Celery activity all remained green.
2. **Domain verification:** Queried `SELECT id, domain, is_primary FROM tenants_domain ORDER BY id;` inside the production Postgres container after the cleanup; results show only `.statuswatch.kontentwave.digital` hostnames with a single `is_primary=true` per tenant.
3. **Compose parity check:** Ran `docker compose -f compose.yaml -f docker-compose.mod.yml up -d mod_api mod_worker mod_beat` locally plus `python manage.py migrate_schemas --shared` inside `mod_api` to ensure migrations, logging, and health checks work before promoting the image.
4. **Rollback rehearsal:** Documented (and dry-ran) the rollback commands that retag the legacy `edge` image and bring the old containers back up, confirming that stateful services (Postgres/Redis) remain untouched by the overlay swap.

---

```bash
# Example verification snippet (run inside the prod db container)
psql $DATABASE_URL -c "SELECT domain, is_primary FROM tenants_domain ORDER BY domain;"
```
