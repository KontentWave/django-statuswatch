# ADR 01: Modular Auth Refresh Alignment

> **Navigation:** [← Back to Project Sheet](../../StatusWatch_project_sheet.md) | [Phase 3 ADRs](../Phase%203/) | [API Docs](../../api/README.md)

---

**Date:** November 15, 2025  
**Status:** Implemented  
**Decision Makers:** Solo developer (Marcel)  
**Tags:** #auth #jwt #multi-tenant #modular-monolith

## Context

Milestone M1 of the modular monolith refactor requires the auth refresh flow to behave consistently across the isolated "mod" stack. The legacy `MultiTenantTokenRefreshView` performed SimpleJWT work inline, interacted directly with blacklist tables, and wrote logs without routing through the new module boundaries. This made it hard to reuse logic, limited audit visibility, and risked schema mistakes when multiple tenants refresh tokens concurrently.

## Decision Drivers

1. **Single source of truth** for JWT handling so both login and refresh flows share Tenant-aware infrastructure.
2. **Audit and performance visibility** for every refresh request (success, rejection, rotation latency).
3. **Safety in public schema**: blacklist tables live outside tenant schemas; failures must not poison transactions.
4. **Backward compatibility** with existing tests and frontend expectations (error shapes, rotation semantics).

## Considered Options

### Option A – Keep per-view logic (Rejected)

- Patch the existing view with small tweaks (extra logging, schema guards).
- **Cons:** logic stays fragmented; difficult to adopt in other endpoints; no obvious seam for future services.

### Option B – Delegate to `TenantAuthService` (Selected ✅)

- Move refresh/rotation/blacklisting into a dedicated service function, exposing a typed result for the view.
- View becomes a thin adapter adding audit + performance hooks and shaping the HTTP response.
- **Pros:** shared infrastructure, easier to test, respects module boundaries, central place to add throttling later.

## Outcome

- Added `TokenRefreshResult` + `TenantAuthService.refresh_tokens()` with injectable `token_class` for testing.
- Service blacklists/rotates tokens inside the active schema, rolls back the DB transaction on errors, and logs structured warnings.
- `MultiTenantTokenRefreshView` now wraps the service call in a `PerformanceMonitor`, emits `AuditEvent.TOKEN_REFRESH`, and re-exports `RefreshToken` so existing tests can keep patching `api.token_refresh.RefreshToken`.
- Audit enum extended with `TOKEN_REFRESH` so events land in `logs/audit.log`.

## Validation

```bash
cd backend
pytest tests/test_token_refresh.py tests/test_jwt_rotation.py -q
```

Manual smoke test (mod stack):

```bash
curl -X POST http://acme.localhost:8081/api/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh":"<refresh token>"}'
```

All cases return the existing payload contract (`{"access": ..., "refresh": ...}` when rotation is enabled) and produce audit entries.

Additional regression guardrails (Nov 15, 20:42 CET) ensured the refreshed auth flow did not break adjacent monitoring/billing endpoints while we prepare DTO extraction:

```bash
cd backend
pytest tests/test_endpoints_api.py tests/test_scheduler.py tests/test_ping_tasks.py -q
pytest tests/test_billing_checkout.py tests/test_billing_webhooks.py tests/test_billing_cancellation.py -q
```

Both suites pass (skipping the long-running Stripe live tests as expected), confirming the modular auth changes remain isolated.

## Consequences

- Future auth endpoints can lean on `TenantAuthService` without duplicating blacklist logic.
- Audit + performance logs for refreshes simplify incident response.
- Tests remain stable because the module still exposes `RefreshToken` for mocking and respects previous error messages.

## Follow-up

- Consider a dedicated DRF throttle scope (e.g., `token_refresh`) to complement login throttles.
- When we introduce per-tenant auth services, promote the refresh helper to a standalone module (e.g., `modules/accounts/token_service.py`).
