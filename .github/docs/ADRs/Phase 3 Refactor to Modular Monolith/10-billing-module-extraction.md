# ADR 02: Billing Service Extraction

> **Navigation:** [← Back to Project Sheet](../../StatusWatch_project_sheet.md) | [Phase 3 ADRs](../Phase%203/) | [API Docs](../../api/README.md)

---

**Date:** November 15, 2025  
**Status:** Implemented  
**Decision Makers:** Solo developer (Marcel)  
**Tags:** #billing #stripe #modular-monolith

## Context

Milestone M2 of the modular monolith refactor moves payment flows out of the legacy `payments` Django app into `modules/billing`. The DTO layer already mirrors frontend contracts, but the business logic (checkout, portal sessions, cancellations, Stripe webhooks) still lives in the DRF views. We need clear seams so the views stay thin adapters (auth, throttles, logging) while Stripe work and tenant mutations live in reusable services.

## Decision Drivers

1. **Single orchestration layer** for Stripe calls shared by both the legacy views and future module consumers.
2. **Logging ownership** stays in DRF views so existing telemetry and audit hooks remain untouched.
3. **Testability**: services can be unit-tested without DRF plumbing; views can be mocked at the service boundary.
4. **Incremental migration**: keep `_resolve_frontend_base_url` and routing in `payments.views` to avoid churn outside billing scope.

## Decisions

1. **Module layout** – Canonical DRF views now live in `modules/billing/views.py`; they import DTO helpers from `modules/billing/__init__.py` and expose the exact class/function names the legacy app expects. The legacy `payments/views.py` file became a shim that re-exports those views.
2. **Shared helpers** – `_resolve_frontend_base_url` moved with the canonical views so tenant-domain heuristics sit beside Stripe orchestration. Shims do not duplicate the helper; they simply import from the module.
3. **Logging + audit boundary** – Views continue to emit structured log lines and audit events while delegating Stripe operations to helper functions (`create_subscription_checkout_session`, `create_billing_portal_session`, etc.) imported from `modules.billing`.
4. **Stripe integration** – The module sets the Stripe client within each view and still accepts `stripe` as an injectable dependency for tests, but compatibility patches now target `payments.views.stripe` via the shim.
5. **Webhook scope** – The Stripe webhook dispatcher joins this extraction. Views continue to verify signatures, then hand the event to `dispatch_billing_webhook_event()` so tenant updates live beside the rest of the billing logic.
6. **Compatibility shim** – `payments/views.py` registers a `log_audit_event` resolver with the module so legacy tests that patch `payments.views.log_audit_event` or `stripe` still intercept the calls. This removes the need to duplicate implementation while keeping import paths stable until cutover.

## Consequences

- DRF views shrink to validation + logging glue inside `modules/billing/views.py` while the shim keeps import compatibility.
- Tests can continue patching `payments.views.stripe` and `payments.views.log_audit_event`; under the hood those proxies resolve back into the module implementation.
- Future modules (e.g., CLI scripts, Celery tasks) can reuse the `modules.billing` entry points without importing DRF views or legacy files.
- `_resolve_frontend_base_url` is now colocated with the canonical views; future refactors can lift it again if multiple modules need it.

## Validation

- Unit tests: `backend/tests/test_modules_billing_services.py` covers payload construction, tenant synchronization, cancellation results, and webhook updates.
- Regression tests: reuse the existing billing suites against the modular stack. Added `tests/test_monitors_tasks_module.py` + `tests/test_celery_tasks.py` so legacy module paths and Celery beat registration stay intact while billing code moves. `tests/test_billing_cancellation.py::test_cancel_subscription_surfaces_stripe_errors` now locks the customer-facing “Unable to contact the payment processor…” detail to prevent further regressions during service refactors.
- Frontend contract alignment: `frontend/src/types/api.ts` re-exports every billing DTO plus `SubscriptionPlan`/`CurrentUserResponse`, and billing pages/stores import from that barrel instead of reaching into `@/lib/billing-client`. Vitest’s Billing suite guards the shape parity and now runs as part of the milestone checklist.

```bash
cd backend
pytest tests/test_modules_billing_services.py \
       tests/test_billing_checkout.py \
       tests/test_billing_cancellation.py \
       tests/test_billing_webhooks.py -q
```

All tests must pass on both the legacy stack and the `docker-compose.mod.yml` stack before merging.

```bash
cd frontend
npm run test -- Billing
```
