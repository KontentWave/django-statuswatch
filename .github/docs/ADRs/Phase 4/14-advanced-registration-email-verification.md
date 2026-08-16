---
title: "ADR 14 – Advanced Registration & Email Verification"
status: Accepted
date: 2025-12-06
tags: [auth, registration, verification, frontend]
---

## Context

This ADR captured the hardening work for tenant-aware registration and email verification. The implemented flow now blocks unverified logins, keeps registration on a durable "Check your inbox" state, supports `/verify-email`, invalidates used or superseded tokens, and preserves safe redirect targets through verification and login.

## Problem

- The earlier implementation allowed unverified accounts to obtain tokens even though a verification token already existed.
- Reserved subdomain rules needed to be enforced consistently to avoid collisions with internal hostnames (`www`, `api`, etc.).
- Verification links needed explicit expiry, single-use semantics, and resend rotation.
- The SPA needed a dedicated verification page instead of pushing users toward an implicit login flow.
- Test coverage needed to include blocked logins, resend invalidation, expiry, and redirect preservation.

## Decision

1. **Enforce verification at login** – `TokenObtainPairWithLoggingView` (and smart login flows) will check `user.profile.email_verified` before issuing tokens and return an `AuthenticationFailed` error (`error.code = "email_unverified"`) when the account is pending verification.
2. **Strengthen registration validation** – `TenantProvisioner` gains a centralized reserved-subdomain check (configurable list) reused by the serializer and future admin forms. Password validation continues to rely on the existing custom validators.
3. **Harden verification endpoints** – Successful verification clears the token (single-use) and triggers a welcome email; expired tokens return an explicit flag; `resend_verification_email` is rate-limited and regenerates tokens before dispatching mail.
4. **Frontend UX updates** – `/register` transitions into a durable “Check your inbox” success state that survives refreshes, `/verify-email` consumes the token and displays success/error/resend states, and `/login` surfaces a targeted alert when the backend rejects unverified users.
5. **Testing-first implementation** – Backend unit tests and frontend Vitest suites cover registration/login/email verification, and the Playwright spec (`frontend/e2e/specs/registration-advanced.spec.ts`) covers blocked logins, resend invalidation, expiry recovery, and redirect preservation.

## Implementation Plan

### Backend

1. Update `TokenObtainPairWithLoggingView` (and any smart login helpers) to short-circuit when `email_verified` is false, returning HTTP 403 with machine-readable error metadata. Add tests in `tests/test_login.py`.
2. Extend `modules/tenancy/provisioning.TenantProvisioner` with a reusable `RESERVED_SUBDOMAINS` guard and ensure `RegistrationSerializer` surfaces validation errors when users pick reserved names.
3. After a successful verification, clear `email_verification_token`, set `email_verification_sent_at` to the verification timestamp, and fire `send_welcome_email`. Introduce a throttle for the resend endpoint and confirm rate limits in tests.
4. Keep `send_verification_email` synchronous for now but document how to swap to Celery if needed; ensure every registration logs the audit events already captured.
5. Update `tests/test_email_verification.py` and related API tests to cover reserved names, unverified login blocks, single-use tokens, and resend throttling.

### Frontend

1. Create `VerifyEmailPage.tsx` and register `/verify-email` in `src/app/router.tsx`. The page reads a `token` param, calls `POST /api/auth/verify-email/`, and renders loading/success/error states with CTAs for “Continue to Login” or “Resend link”.
2. Modify `RegisterPage` to stay on-page with a success module instructing users to check their inbox; persist the state via router state or a `?status=check-email` query param so refreshes keep the messaging.
3. Adjust `LoginPage` error handling: when the API returns `error.code === "email_unverified"`, display a banner with a resend button tied to the new endpoint.
4. Add helper APIs/types for `verifyEmail`, `resendVerificationEmail`, and the new response contracts in `src/types/api.ts`.
5. Expand Vitest coverage (Register/Login/VerifyEmail page) and add a Playwright spec that walks through registration → email fetch (via test helper) → verification → login-gated completion.

## Work Completed (2025-12-12)

- Reproduced the failing pytest-django run for `tests/test_email_verification.py` with `--keepdb` and traced the database handle turning BAD immediately after `test_verify_email_token_single_use`, confirming fixture-driven connection churn.
- Updated [backend/tests/conftest.py](backend/tests/conftest.py) with `_build_raw_db_params` and `_truncate_token_tables` helpers so JWT cleanup runs through a dedicated psycopg connection instead of the `transactional_db` handle that pytest keeps inside an atomic block.
- Adjusted the `cleanup_jwt_tokens` fixture to call the new helper and stop invoking `schema_context` within the active transaction, preventing Django from closing the connection mid-suite.
- Verified that the revised fixtures reset the schema back to public after cleanup, aligning with the multi-tenant isolation rules already outlined in this ADR.

### Historical Validation Note

- `python -m pytest tests/test_email_verification.py` still reports four failures (`EmailVerificationEndpointTests.test_verify_email_success`, `EmailVerificationEndpointTests.test_verify_email_token_single_use`, `EmailVerificationEndpointTests.test_verify_email_triggers_welcome_email`, `ResendVerificationEmailTests.test_resend_verification_success`). Each failure shows `psycopg.Connection [BAD]` within the Django-managed savepoint setup, indicating the connection is still being closed between tests while pytest keeps an outer atomic block open.

## Status

- Accepted and implemented. The validation note above is retained as historical context from the Dec 2025 rollout work.

## Consequences

- Users cannot obtain JWTs until they verify their email, reducing risk from typoed or compromised addresses.
- Reserved subdomain collisions are prevented at creation time, protecting deployment hostnames.
- The new `/verify-email` route and improved registration UX clarify the onboarding journey.
- Additional tests (unit, Vitest, Playwright) increase coverage and guard against regressions in auth/registration flows.
