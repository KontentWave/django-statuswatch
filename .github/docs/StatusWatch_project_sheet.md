## `project_sheet.md`: Phase 1 MVP Specification

Here is a detailed breakdown of the features for your MVP. Each feature includes the user goal, front-end tasks, and the back-end tasks required to support them.

### 1. User Registration & Tenant Creation

- **Action:** Allow a new user to sign up, which automatically provisions a new, isolated organization (tenant) for them.
- **Test Plan:**
  - Backend: Test that a POST request to the register endpoint creates a `User`, a `Tenant`, and a new database schema.
  - Frontend: Test that a valid form submission redirects to the login page and an invalid one shows error messages.

#### **Frontend Tasks (React)**

- Create a public route and view for `/register`.
- Build the registration form using **React Hook Form** for state and **Zod** for validation (e.g., organization name, email, password, password confirmation).
- On form submission, use **Axios** to send a `POST` request to the back-end API endpoint.
- Handle API responses: on success, redirect the user to the `/login` page with a success message; on failure, display validation errors from the API.

#### **Backend Tasks (Django)**

- Create a DRF `APIView` for the `/api/auth/register/` endpoint.
- This view's `post` method will:
  1.  Validate the incoming data (organization name, email, password).
  2.  Create the `Tenant` (Organization) object. `django-tenants` will automatically create the corresponding schema.
  3.  Within the new tenant's context, create the new `User` and assign them the "Owner" role.
  4.  Return a `201 Created` status on success.

---

#### **Implementation Notes**

- **Frontend**
  - `/register` route defined via TanStack Router; `RegisterPage` uses React Hook Form + Zod for validation and Axios for submission.
  - Successful submissions navigate to `/login` with a replacement state message so the banner survives refresh; backend validation errors hydrate field-level messages.
  - Vitest suite (`src/pages/__tests__/RegisterPage.test.tsx`) covers happy path, client-side mismatch, and API error propagation.
- **Backend**
  - `RegistrationView` (DRF `APIView`) persists tenant data through `RegistrationSerializer`, which slugifies schema names, provisions `Domain` entries, and creates an owner `User` within the tenant schema.
  - `backend/tests/test_registration.py` ensures tenant, domain, and owner group membership are created; parametric cases cover mismatch and invalid payloads.
  - Migrations `0002_add_localhost_domain` and `0003_add_dev_domains` seed development hostnames (`localhost`, `statuswatch.local`, `acme.statuswatch.local`) on the public tenant for nginx/OpenResty routing.
- **Tooling & Verification**
  - Helper script `backend/scripts/list_tenants.py` lists tenants, domains, and owner accounts for manual verification.
  - Vite dev proxy forwards `/api` calls to the configured backend origin (`https://acme.statuswatch.local`), keeping local HTTPS consistent with production routing.

---

### 2. User Authentication (Login/Logout)

- **Action:** Allow a registered user to log in to access their private dashboard and log out to end their session.
- **Test Plan:**
  - Backend: Test that correct credentials yield JWT tokens and incorrect ones yield a 401 error.
  - Frontend: Test that a successful login stores tokens and redirects, granting access to protected routes.

#### **Frontend Tasks (React)**

- Create a public route and view for `/login`.
- Build the login form (email, password).
- On submission, `POST` credentials to the back-end's token endpoint.
- On success:
  - Receive and store the JWT access and refresh tokens securely (e.g., in-memory with **Zustand** or in a secure, httpOnly cookie managed by the backend).
  - Set up an **Axios interceptor** to automatically attach the `Authorization: Bearer <access_token>` header to all subsequent API requests.
  - Redirect the user to their `/dashboard`.
- Implement a "Logout" button that clears the stored tokens and redirects to the login page.
- Create a protected route wrapper that redirects unauthenticated users from `/dashboard` back to `/login`.

#### **Backend Tasks (Django)**

- Expose the `djangorestframework-simplejwt` endpoints for `/api/auth/token/` (to get tokens) and `/api/auth/token/refresh/`.
- Ensure all data-sensitive API endpoints (like for endpoints) require authentication (`IsAuthenticated` permission class).

#### **Implementation Notes**

- **Frontend**
  - `/login` renders `LoginPage`, storing access/refresh tokens via `storeAuthTokens`; TanStack Router redirects to `/dashboard` on success.
  - Shared Axios instance (`src/lib/api.ts`) attaches the bearer token and performs silent refresh on 401s, rotating tokens and retrying the original request.
  - Authenticated routes are declared beneath an `authenticated` parent route with a `beforeLoad` guard; the legacy `RequireAuth` wrapper is now a pass-through for backward compatibility.
  - `DashboardPage` uses React Query to load `/auth/me/`, handles 401 fallbacks, and wires a logout mutation that hits `/auth/logout/` then clears client state; Vitest suites cover happy path, 401 redirect, logout success, and failure messaging.
- **Backend**
  - `TokenObtainPairWithLoggingView` (SimpleJWT) logs structured login attempts and enforces throttles; `/api/auth/logout/` blacklists refresh tokens with sanitized logging.
  - `CurrentUserView` returns serialized profile data for the dashboard; pytest coverage includes credential validation, throttling, and logout behaviours.
  - Logging sanitization strips secrets from auth and payment events, ensuring rotation-friendly logs (`statuswatch.log`, `security.log`).

---

### 3. Core Feature: Endpoint Monitoring (CRUD)

- **Action:** Allow an authenticated user to create, view, and delete the URLs they want to monitor within their organization's dashboard.
- **Test Plan:**
  - Backend: Test that CRUD operations on endpoints are properly authenticated and scoped to the user's tenant.
  - Frontend: Test that the dashboard correctly displays the list of endpoints and that the create/delete actions update the UI.

#### **Frontend Tasks (React)**

- Create a protected route and view for `/dashboard`.
- Use **TanStack Query**'s `useQuery` hook to fetch the list of endpoints from the back-end API.
- Display the endpoints in a clean table using **TanStack Table**. Show the URL and the latest status.
- Build a "Create Endpoint" form (e.g., in a modal from **shadcn/ui**).
- Use **TanStack Query**'s `useMutation` hook to handle the `POST` request for creating a new endpoint. On success, automatically invalidate the endpoint list query to refetch the latest data.
- Add a "Delete" button to each row that triggers another `useMutation` to send a `DELETE` request.

#### **Backend Tasks (Django)**

- Create an `Endpoint` model within one of your apps. It should have a foreign key to the `Tenant` model to ensure it's tenant-specific.
- Create a Celery task `ping_endpoint(endpoint_id)` that performs the check and saves the result.
- Create a DRF `ModelViewSet` for the `Endpoint` model.
  - This provides `/api/endpoints/` with `GET`, `POST`, `PUT`, `DELETE` functionality out of the box.
  - **Crucially**, override the `get_queryset` method to filter by the current request's tenant: `Endpoint.objects.filter(tenant=request.tenant)`. This is the core of data isolation.
  - On creating a new `Endpoint` instance, trigger the initial Celery task.

#### **Implementation Notes**

- **Frontend**
  - `/dashboard` is nested beneath the authenticated TanStack Router branch (`frontend/src/app/router.tsx`) and renders `DashboardPage`.
  - `DashboardPage` (`frontend/src/pages/Dashboard.tsx`) fetches `/api/endpoints/` with `useQuery`, keeps previous data during pagination, and hands rows to `EndpointTable`.
  - `EndpointTable` (`frontend/src/components/EndpointTable.tsx`) builds the grid with TanStack Table, supplies stable row IDs, and exposes Prev/Next controls that call the parent `onPageChange` handler.
  - The inline “Add Endpoint” form posts through a `useMutation` hook that invalidates the endpoints query; delete buttons call a separate mutation and keep pagination state consistent.
  - Vitest coverage (`frontend/src/pages/__tests__/DashboardPage.test.tsx`) asserts list rendering, pagination logging, create/delete flows, auth guard redirects, and logout handling.
- **Backend**
  - `Endpoint` model (`backend/monitors/models.py`) associates monitors with tenants, tracks schedule metadata, and enforces per-tenant URL uniqueness.
  - `EndpointViewSet` (`backend/monitors/views.py`) scopes queries to `request.tenant`, logs create/delete events, schedules an immediate Celery ping, and exposes routes at `/api/endpoints/`.
  - Celery jobs (`backend/monitors/tasks.py`) implement `ping_endpoint` with retries and `schedule_endpoint_checks` to enqueue due monitors across tenant schemas.
  - Django tests (`backend/monitors/tests/test_endpoints_api.py`, `backend/monitors/tests/test_scheduler.py`) validate auth requirements, tenant isolation, create/delete behavior, and scheduler enqueue logic with captured task calls.
