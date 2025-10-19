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
