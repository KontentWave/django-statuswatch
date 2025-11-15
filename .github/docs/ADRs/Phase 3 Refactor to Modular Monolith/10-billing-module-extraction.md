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

1. **Module layout** – All billing business logic lives in `modules/billing/services.py`. Separate files are overkill right now; the single module exposes typed service functions for checkout, portal, cancellation, and webhook dispatch.
2. **Shared helpers** – `_resolve_frontend_base_url` remains in `payments.views` and is passed into the services via plain strings. This keeps tenant-domain heuristics co-located with DRF request handling.
3. **Logging + audit boundary** – Services return structured dataclasses (`CheckoutSessionResult`, `PortalSessionResult`, `CancellationResult`, `WebhookDispatchResult`). DRF views own all logging, metrics, and audit events, preserving existing log formats.
4. **Stripe integration** – Services call `stripe.*` directly (same as legacy code) but accept the module as an injectable dependency so tests can keep patching `stripe.checkout.Session.create` et al.
5. **Webhook scope** – The Stripe webhook dispatcher joins this extraction. Views continue to verify signatures, then hand the event to `dispatch_billing_webhook_event()` so tenant updates live beside the rest of the billing logic.

## Consequences

- DRF views shrink to validation + logging glue while services encapsulate Stripe-specific code paths.
- Tests can mock `modules.billing.services` in view-level suites and directly unit-test the services for payload correctness.
- Future modules (e.g., CLI scripts, Celery tasks) can reuse the same services without importing DRF views.
- `_resolve_frontend_base_url` stays put for now; once other features depend on it we can lift it into a shared helper without blocking this milestone.

## Validation

- Unit tests: `backend/tests/test_modules_billing_services.py` covers payload construction, tenant synchronization, cancellation results, and webhook updates.
- Regression tests: reuse the existing billing suites against the modular stack. Added `tests/test_monitors_tasks_module.py` + `tests/test_celery_tasks.py` so legacy module paths and Celery beat registration stay intact while billing code moves. `tests/test_billing_cancellation.py::test_cancel_subscription_surfaces_stripe_errors` now locks the customer-facing “Unable to contact the payment processor…” detail to prevent further regressions during service refactors.

```bash
cd backend
pytest tests/test_modules_billing_services.py \
       tests/test_billing_checkout.py \
       tests/test_billing_cancellation.py \
       tests/test_billing_webhooks.py -q
```

All tests must pass on both the legacy stack and the `docker-compose.mod.yml` stack before merging.
