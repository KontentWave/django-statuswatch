# ADR: User Authentication (Login/Logout)

- **Status:** Accepted
- **Date:** 2025-10-21
- **Related Specs:** `StatusWatch_project_sheet.md` — Feature 2, SimpleJWT configuration in `backend/app/settings.py`

## Context

Authenticated access is required for tenant dashboards and future management features. The backend already exposes Django REST Framework endpoints and relies on SimpleJWT for token issuance. The frontend is a Vite-powered SPA that interacts with the API over HTTPS via the OpenResty proxy. We must provide a login experience, protect private routes, support logout and token rotation, and avoid exposing secrets in logs.

## Decision

1. **Authentication Endpoints** — Keep SimpleJWT endpoints public schema (`/api/auth/token/`, `/api/auth/token/refresh/`) and implement `/api/auth/logout/` plus `/api/auth/me/` within the API app.
   - `TokenObtainPairWithLoggingView` extends SimpleJWT to add structured logging, login throttling, and sanitized metadata.
   - `LogoutView` requires an access token, blacklists the submitted refresh token, and emits sanitized audit entries.
   - `CurrentUserView` returns the serialized user profile for dashboard display, scoped to the active tenant schema.
2. **Frontend Flow** — Implement login, logout, and protected routing with TanStack Router + Query.
   - `/login` renders `LoginPage`, posts credentials to `/api/auth/token/`, and stores access/refresh tokens using `storeAuthTokens` (localStorage).
   - An Axios interceptor (`src/lib/api.ts`) attaches the bearer token to each request and silently refreshes tokens on 401 responses, retrying the original request after storing the rotated pair.
   - Router-level `authenticated` parent route enforces access via `beforeLoad`; unauthenticated visitors are redirected to `/login` with state-based messaging and redirect hints.
   - `DashboardPage` queries `/auth/me/`, surfaces account details, and offers a logout mutation that clears tokens, invalidates the React Query cache, and navigates to `/login` with confirmation messaging.
3. **Observability & Safety** — Logging utilities sanitize secrets (stripe keys, bearer tokens, IPs) before writing to `statuswatch.log` or `security.log`, satisfying the log hygiene requirement introduced during logout work.
4. **Testing & Tooling** —
   - Backend coverage lives in `backend/tests/test_login.py`, `test_logout.py`, and related throttling/exception tests.
   - Frontend coverage includes `LoginPage.test.tsx`, `DashboardPage.test.tsx`, and `RequireAuth.test.tsx` (now validating pass-through behaviour because routing owns the guard).
   - Dev scripts (`scripts/create_acme_user.py`, `scripts/fix_dev_database.py`) seed the `acme` tenant user used for manual verification.

## Consequences

- Session continuity improves: expired access tokens refresh automatically until the refresh token rotates out or is blacklisted on logout.
- Router-level guarding simplifies future protected routes (just nest beneath `authenticated`); legacy components relying on `RequireAuth` still function via the pass-through shim.
- LocalStorage continues to hold tokens, so browser extensions or shared devices remain a residual risk; future iterations may consider cookie-based storage.
- Silent refresh introduces concurrent request coordination; a single in-flight promise prevents token thrash, but unexpected refresh failures clear tokens and surface as 401s.

## Follow-up

- Replace console-based Axios logging with structured debug logging or remove it before production builds.
- Evaluate moving token storage to secure cookies once backend CSRF/session strategy stabilises.
- Add automated integration tests (Playwright or Cypress) covering the full login→dashboard→logout journey across tenant domains.
