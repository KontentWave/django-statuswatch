# ADR: User Registration & Tenant Creation

- **Status:** Accepted
- **Date:** 2025-10-19
- **Related Specs:** `StatusWatch_project_sheet.md` — Feature 1, `mvp.feature`

## Context

StatusWatch must onboard a new organization by provisioning an isolated tenant schema and an owner account in one step. The architecture already uses `django-tenants` for multi-tenancy and React + Vite for the SPA. Traffic in development is routed through OpenResty (`https://acme.statuswatch.local`), so the solution must work over HTTPS via the proxy while preserving fast local iteration.

## Decision

1. **API Endpoint** — Implement `POST /api/auth/register/` using a DRF `APIView` backed by `RegistrationSerializer`.
   - Serializer slugifies the requested organization name to derive the tenant schema, ensures uniqueness, and creates a `Client` + primary `Domain` record.
   - Owner `User` is created inside the tenant schema using `schema_context`, with automatic assignment to the `Owner` group.
2. **Frontend Flow** — Add a public `/register` route rendered by `RegisterPage`.
   - Form state is managed with React Hook Form and validated with Zod; Axios submits JSON to `/api/auth/register/`.
   - On success the page redirects to `/login` (TanStack Router navigation) and passes the success message via navigation state; on failure field, form, and network errors surface inline.
3. **Environment Alignment** — Configure Vite’s dev proxy to forward `/api` calls to `https://acme.statuswatch.local`, aligning local behavior with the OpenResty reverse proxy. Migrations seed the public tenant with domains for `localhost`, `statuswatch.local`, and `acme.statuswatch.local` to support this routing.
4. **Verification** — Maintain automated coverage (`backend/tests/test_registration.py`, `RegisterPage.test.tsx`) and ship a CLI helper (`scripts/list_tenants.py`) to inspect tenants/domains/users for manual checks.

## Consequences

- New tenant schemas are provisioned automatically and remain isolated per `django-tenants`.
- Frontend and backend tests cover validation, error handling, and the happy path, reducing regression risk.
- Local development matches production HTTPS routing, but relies on the OpenResty proxy and certificates being available; without it, developers must override `VITE_BACKEND_ORIGIN`.
- Owner group assignment depends on the presence of the `Owner` group; migrations or fixtures may be required in other environments.

## Follow-up

- Build the `/login` experience to surface the success message more visibly.
- Consider rate limiting or CAPTCHA on the registration endpoint before public launch.
- Automate creation of the `Owner` group (e.g., via a data migration) to guarantee its availability in all deployments.
