# ADR: Stripe Customer Portal Integration

## Context

Phase 2 introduces self-service billing for Pro tenants. After the checkout/webhook flows stabilized, we needed a production-ready path for customers to update cards, review invoices, or cancel without manual support. Stripe's hosted customer portal offers those capabilities with minimal surface area in our app, provided we generate authenticated portal sessions per tenant.

## Decision

We expose `/api/billing/create-portal-session/` as an authenticated DRF `APIView`. The view verifies Stripe configuration, ensures the tenant has a `stripe_customer_id`, logs structured metadata, and calls `stripe.billing_portal.Session.create`. The resulting URL is returned to the frontend, which performs a top-level redirect so the session is consumed immediately.

## Implementation Details

- **Backend**

  - `BillingPortalSessionView` lives in `payments/views.py` and shares the billing throttle to avoid abuse.
  - On each request we gather `tenant_schema`, `stripe_customer_id`, and user context for logging and error reporting.
  - We log portal creation start/success to `payments.billing`, which writes to `logs/billing.log`.
  - Stripe errors bubble through the existing sanitised exception helpers, producing user-friendly responses and actionable logs.

- **Frontend**

  - The billing page (`frontend/src/pages/Billing.tsx`) exposes a "Manage Subscription" CTA only when the subscription store reports `pro`.
  - Clicking the button executes a TanStack Query mutation (`createBillingPortalSession`) that posts to the backend and performs `window.location.assign(url)` on success.
  - Tests cover the redirect flow and error handling to maintain regression safety.

- **Logging & Observability**

  - Portal session creation is captured with structured extras (tenant schema, user id, customer id, status) for easy filtering.
  - Combined with webhook diagnostics (`webhook_signatures.log`, `subscription_state.log`), we can trace a tenant from checkout → webhook → portal management.

- **Operational Notes**
  - Each tenant retains a single Stripe customer id; portal sessions therefore surface only that tenant's subscriptions and saved payment methods.
  - In production environments a publicly reachable HTTPS endpoint replaces the Stripe CLI listener. Only the signing secret (`STRIPE_WEBHOOK_SECRET`) needs to be kept in sync.

## Status

Implemented October 27, 2025. Demo tenants now see live portal data in Stripe's sandbox, and production tenants will receive the same experience once live keys and webhook endpoints are configured.
