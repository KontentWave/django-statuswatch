---
title: "ADR 14 – Advanced Registration & Email Verification"
status: Proposed
date: 2025-12-06
tags: [auth, registration, verification, frontend]
---

## Context

Phase 1 introduced tenant-aware registration and a basic email verification endpoint, but the login flow still issues JWTs to unverified accounts and the SPA redirects straight to `/login` after signup. Gherkin specs in `11. User Registration & Tenant Creation.feature` and the Phase 4 sheet now call for stricter behavior: unverified logins must be blocked, verification links should be single-use with resend throttling, and the frontend needs a `/verify-email` route plus resilient UX for the “check your inbox” state.

## Problem

- Users can currently log in immediately after registration even though an email verification token exists.
- Reserved subdomain rules are not enforced consistently, risking collisions with internal hostnames (`www`, `api`, etc.).
- Verification links remain valid indefinitely and can be reused.
- The SPA lacks a dedicated verification page, so the email CTA sends users back to `/login` without confirmation.
- Tests only cover the initial happy path and do not exercise the negative scenarios outlined in the new feature spec.

## Decision

1. **Enforce verification at login** – `TokenObtainPairWithLoggingView` (and smart login flows) will check `user.profile.email_verified` before issuing tokens and return an `AuthenticationFailed` error (`error.code = "email_unverified"`) when the account is pending verification.
2. **Strengthen registration validation** – `TenantProvisioner` gains a centralized reserved-subdomain check (configurable list) reused by the serializer and future admin forms. Password validation continues to rely on the existing custom validators.
3. **Harden verification endpoints** – Successful verification clears the token (single-use) and triggers a welcome email; expired tokens return an explicit flag; `resend_verification_email` is rate-limited and regenerates tokens before dispatching mail.
4. **Frontend UX updates** – `/register` transitions into a durable “Check your inbox” success state that survives refreshes, `/verify-email` becomes a new public route that consumes the token and displays success/error/resend states, and `/login` surfaces a targeted alert when the backend rejects unverified users.
5. **Testing-first implementation** – Update backend unit tests (registration/login/email verification) and frontend Vitest suites (Register/Login/new VerifyEmail page) before wiring feature code. Add a Playwright spec (`frontend/e2e/specs/registration-advanced.spec.ts`) to cover the end-to-end happy path plus the “blocked until verified” scenario.

## Implementation Plan

### Backend

1. Update `TokenObtainPairWithLoggingView` (and any smart login helpers) to short-circuit when `email_verified` is false, returning HTTP 403 with machine-readable error metadata. Add tests in `tests/test_login.py`.
2. Extend `modules/tenancy/provisioning.TenantProvisioner` with a reusable `RESERVED_SUBDOMAINS` guard and ensure `RegistrationSerializer` surfaces validation errors when users pick reserved names.
3. After a successful verification, clear `email_verification_token`, set `email_verification_sent_at` to the verification timestamp, and fire `send_welcome_email`. Introduce a throttle for the resend endpoint and confirm rate limits in tests.
4. Keep `send_verification_email` synchronous for now but document how to swap to Celery if needed; ensure every registration logs the audit events already captured.
5. Update `tests/test_email_verification.py` and related API tests to cover reserved names, unverified login blocks, single-use tokens, and resend throttling.

### Frontend

1. Create `VerifyEmailPage.tsx` and register `/verify-email` in `src/app/router.tsx`. The page should read a `token` param (query or path), call `POST /api/auth/verify-email/`, and render loading/success/error states with CTAs for “Continue to Dashboard” or “Resend link”.
2. Modify `RegisterPage` to stay on-page with a success module instructing users to check their inbox; persist the state via router state or a `?status=check-email` query param so refreshes keep the messaging.
3. Adjust `LoginPage` error handling: when the API returns `error.code === "email_unverified"`, display a banner with a resend button tied to the new endpoint.
4. Add helper APIs/types for `verifyEmail`, `resendVerificationEmail`, and the new response contracts in `src/types/api.ts`.
5. Expand Vitest coverage (Register/Login/new VerifyEmail page) and add a Playwright spec that walks through registration → email fetch (via test helper) → verification → auto-login + login-blocked negative case.

## Work Completed (2025-12-12)

- Reproduced the failing pytest-django run for `tests/test_email_verification.py` with `--keepdb` and traced the database handle turning BAD immediately after `test_verify_email_token_single_use`, confirming fixture-driven connection churn.
- Updated [backend/tests/conftest.py](backend/tests/conftest.py) with `_build_raw_db_params` and `_truncate_token_tables` helpers so JWT cleanup runs through a dedicated psycopg connection instead of the `transactional_db` handle that pytest keeps inside an atomic block.
- Adjusted the `cleanup_jwt_tokens` fixture to call the new helper and stop invoking `schema_context` within the active transaction, preventing Django from closing the connection mid-suite.
- Verified that the revised fixtures reset the schema back to public after cleanup, aligning with the multi-tenant isolation rules already outlined in this ADR.

### Remaining Issues

- `python -m pytest tests/test_email_verification.py` still reports four failures (`EmailVerificationEndpointTests.test_verify_email_success`, `EmailVerificationEndpointTests.test_verify_email_token_single_use`, `EmailVerificationEndpointTests.test_verify_email_triggers_welcome_email`, `ResendVerificationEmailTests.test_resend_verification_success`). Each failure shows `psycopg.Connection [BAD]` within the Django-managed savepoint setup, indicating the connection is still being closed between tests while pytest keeps an outer atomic block open.

## Status

- Proposal recorded. Implementation begins with test updates (backend + frontend + Playwright) before wiring code changes.

## Consequences

- Users cannot obtain JWTs until they verify their email, reducing risk from typoed or compromised addresses.
- Reserved subdomain collisions are prevented at creation time, protecting deployment hostnames.
- The new `/verify-email` route and improved registration UX clarify the onboarding journey.
- Additional tests (unit, Vitest, Playwright) increase coverage and guard against regressions in auth/registration flows.
