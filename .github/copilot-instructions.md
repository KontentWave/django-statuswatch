# 1) Repository layout (mono-repo)

```
statuswatch-project/
├─ README.md
├─ LICENSE
├─ .gitignore
├─ .editorconfig
├─ .env.example                 # shared sample, no secrets
├─ copilot-instructions.md      # high-level rules for Copilot
├─ docker-compose.dev.yml       # optional: pg + redis for local
├─ backend/
│  ├─ manage.py
│  ├─ requirements.txt
│  ├─ requirements-dev.txt
│  ├─ constraints.txt           # pin transitive deps (optional)
│  ├─ .python-version           # e.g. 3.12.x (pyenv)
│  ├─ scripts/                  # one-off admin scripts
│  ├─ app/                      # Django project
│  │  ├─ settings.py            # env-driven; dev/prod split later
│  │  ├─ urls_public.py
│  │  ├─ urls_tenant.py
│  │  └─ wsgi.py
│  ├─ tenants/ api/ payments/ monitors/   # Django apps
│  ├─ tests/
│  └─ staticfiles/ templates/
└─ frontend/
   ├─ package.json
   ├─ tsconfig.json
   ├─ vite.config.ts
   ├─ postcss.config.cjs
   ├─ tailwind.config.ts
   ├─ .eslintrc.cjs  .prettierrc
   └─ src/
      ├─ app/ providers.tsx router.tsx
      ├─ pages/ components/ features/
      ├─ lib/ hooks/ styles/ types/
      └─ index.tsx
```

> ✔️ Keep Python in a **pyenv** version file (`backend/.python-version`) and your **virtualenv** wherever you like (e.g., `~/.venvs/statuswatch`). Node: recommend **Node 20+**.

---

# 2) Backend dependencies (pin or range)

`backend/requirements.txt` (runtime)

```txt
Django>=5.0,<6.0
djangorestframework>=3.14,<3.16
django-environ>=0.11,<0.12
django-tenants>=3.6,<3.7
djangorestframework-simplejwt>=5.3,<6.0
django-cors-headers>=4.3,<5.0
psycopg[binary]>=3.1,<3.2
celery>=5.4,<6.0
redis>=5.0,<6.0
stripe>=10.0,<11.0
whitenoise>=6.6,<7.0
gunicorn>=21.2,<22.0
drf-spectacular>=0.27,<0.28   # OpenAPI for frontend
```

`backend/requirements-dev.txt` (dev + test + quality)

```txt
-r requirements.txt
pytest>=8.0,<9.0
pytest-django>=4.8,<5.0
model-bakery>=1.20,<2.0
factory-boy>=3.3,<4.0
pytest-cov>=5.0,<6.0
black>=24.0
ruff>=0.6
isort>=5.13
mypy>=1.10
django-stubs[compatible-mypy]>=5.0
types-requests
```

Optional: `backend/constraints.txt` if you want fully repeatable installs (freeze transitive versions once CI is green).

---

# 3) Frontend dependencies

`frontend/package.json` (just the key bits; Copilot can scaffold files)

```json
{
  "name": "statuswatch-frontend",
  "private": true,
  "type": "module",
  "engines": { "node": ">=20" },
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest",
    "lint": "eslint .",
    "format": "prettier -w ."
  },
  "dependencies": {
    "react": "^18",
    "react-dom": "^18",
    "@tanstack/react-query": "^5",
    "@tanstack/react-router": "^1",
    "@tanstack/react-table": "^8",
    "axios": "^1",
    "zod": "^3",
    "react-hook-form": "^7",
    "zustand": "^4",
    "@stripe/stripe-js": "^3",
    "tailwind-merge": "^2",
    "clsx": "^2",
    "sonner": "^1",
    "lucide-react": "^0.4",
    "recharts": "^2",
    "@radix-ui/react-slot": "^1",
    "class-variance-authority": "^0.7",
    // shadcn/ui is installed via CLI & exports; no single npm name
    "dayjs": "^1"
  },
  "devDependencies": {
    "typescript": "^5",
    "vite": "^5",
    "@vitejs/plugin-react-swc": "^3",
    "tailwindcss": "^3",
    "postcss": "^8",
    "autoprefixer": "^10",
    "eslint": "^9",
    "@eslint/js": "^9",
    "typescript-eslint": "^8",
    "prettier": "^3",
    "vitest": "^2",
    "@testing-library/react": "^16",
    "@testing-library/jest-dom": "^6",
    "jsdom": "^25"
  }
}
```

---

# 4) Copilot guidance (high-level, not prescriptive)

`copilot-instructions.md`

```markdown
# Copilot Rules: StatusWatch

## Architecture
- Mono-repo with `backend/` (Django/DRF) and `frontend/` (Vite/React/TS).
- Multi-tenant backend using `django-tenants` with subdomain routing.
- JWT auth (Simple JWT). Payments via Stripe Checkout redirect.

## Frontend
- Use React + TS + Vite.
- Styling: Tailwind + shadcn/ui (Radix). Accessible components.
- Routing: TanStack Router. Data fetching: TanStack Query.
- Forms: React Hook Form + Zod. Client-only state: small Zustand stores.
- HTTP: Axios with a request interceptor that adds JWT from localStorage.
- API base URL = `${window.location.origin}/api` (no hard-coded domains).
- For Stripe: call `/api/pay/create-checkout-session/` and redirect to returned `url`.

## Backend
- DRF viewsets or function views; return OpenAPI via drf-spectacular.
- Settings are env-driven (`django-environ`); no secrets in VCS.
- Keep `payments`, `api`, `tenants`, `monitors` as separate Django apps.
- Write integration-friendly endpoints:
  - `POST /api/auth/token/`, `POST /api/auth/token/refresh/`
  - `GET /api/ping/`
  - `GET /api/pay/config/`, `POST /api/pay/create-checkout-session/`

## Code quality
- Python: black, ruff, isort, mypy; tests with pytest/pytest-django.
- Frontend: ESLint + Prettier; unit tests with Vitest + RTL.
- Prefer small, typed modules; avoid `any`; extract DTO types.

## Output
- Generate files under the correct repo subfolders.
- Use path aliases like `@/lib`, `@/components` in frontend.
- Include docstrings/JSDoc where useful.
```

---

# 5) Environments & examples

* **Backend `backend/.env.example`**

  ```
  DATABASE_URL=postgresql://postgres:devpass@127.0.0.1:5432/dj01
  DB_CONN_MAX_AGE=600
  REDIS_URL=redis://127.0.0.1:6379/0
  STRIPE_PUBLIC_KEY=pk_test_xxx
  STRIPE_SECRET_KEY=sk_test_xxx
  STRIPE_WEBHOOK_SECRET=whsec_xxx
  ```

* **Frontend `frontend/.env.example`**

  ```
  VITE_STRIPE_PUBLIC_KEY=pk_test_xxx
  ```

---

# 6) Tooling & CI (optional but nice)

* **pre-commit** at repo root with hooks for black/ruff/isort/mypy & eslint/prettier.
* **GitHub Actions**:

  * Backend: setup Python, install `-r requirements-dev.txt`, run `pytest -q`.
  * Frontend: Node 20, `pnpm i`/`npm ci`, run `npm run test` & `npm run build`.

---
