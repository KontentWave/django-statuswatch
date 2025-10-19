# Code Audit Report - Unused/Legacy Code

**Date:** October 19, 2025  
**Project:** StatusWatch  
**Audit Type:** Identify unused files, legacy code, and cleanup opportunities

---

## Summary

Found **5 items** that could be cleaned up:

1. ✅ **Keep:** `db.sqlite3` - Used as fallback database
2. ❌ **Remove:** `backend/app/urls.py` - Legacy/unused file
3. ❌ **Remove:** Duplicate pytest.ini (root level)
4. ⚠️ **Review:** `templates/welcome.html` - Might be unused
5. ⚠️ **Review:** Test utility scripts - Keep for now

---

## Detailed Findings

### 1. ✅ KEEP: `backend/db.sqlite3`

**Status:** Keep (used as fallback)

**Location:** `/home/marcel/projects/statuswatch-project/backend/db.sqlite3`

**Size:** 128KB (as of Oct 16)

**Reason:**

```python
# settings.py line 119
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}
```

**Why Keep:**

- Defined as fallback in settings when `DATABASE_URL` not set
- Useful for quick local development without PostgreSQL
- Small file size (128KB)
- May contain test data

**Action:** ✅ **Keep as is**

**Recommendation:** Add to `.gitignore` if not already there:

```gitignore
# Database
backend/db.sqlite3
backend/db.sqlite3-journal
```

---

### 2. ❌ REMOVE: `backend/app/urls.py`

**Status:** Legacy/Unused

**Location:** `/home/marcel/projects/statuswatch-project/backend/app/urls.py`

**Issue:** This file is **NOT** being used. The project uses:

- `app/urls_public.py` for public schema (root domain)
- `app/urls_tenant.py` for tenant schemas

**Evidence:**

```python
# settings.py
PUBLIC_SCHEMA_URLCONF = "app.urls_public"  # ✅ Used
ROOT_URLCONF = "app.urls_tenant"           # ✅ Used
# No reference to "app.urls"                ❌ Unused
```

**Content Issues:**

1. Imports `home` from `.views` but `views.py` doesn't exist
2. References `welcome.html` template (might be unused too)
3. Has JWT token URLs in wrong format (`/api/token/` vs `/api/auth/token/`)
4. Duplicate includes (`path("api/", include("api.urls"))` twice)

**Action:** ❌ **REMOVE THIS FILE**

**Command:**

```bash
cd /home/marcel/projects/statuswatch-project/backend
rm app/urls.py
```

**Verification After Removal:**

```bash
# Run tests to ensure nothing breaks
python -m pytest -v
# Should still pass all 120 tests
```

---

### 3. ❌ REMOVE: Duplicate `pytest.ini`

**Status:** Duplicate Configuration

**Issue:** Two `pytest.ini` files exist:

**File 1:** `/home/marcel/projects/statuswatch-project/pytest.ini`

```ini
[pytest]
DJANGO_SETTINGS_MODULE = app.settings
python_files = tests.py test_*.py *_test.py
testpaths = backend
addopts = -q --reuse-db
```

**File 2:** `/home/marcel/projects/statuswatch-project/backend/pytest.ini`

```ini
[pytest]
DJANGO_SETTINGS_MODULE = app.settings
python_files = tests.py test_*.py *_tests.py
testpaths = tests
```

**Problem:**

- Root level points `testpaths = backend` (correct)
- Backend level points `testpaths = tests` (also works from backend/)
- Having both is confusing and can lead to different behavior

**Which One is Used?**
Pytest uses the **closest** pytest.ini to where the command is run:

- Run from project root: Uses root `pytest.ini` → looks in `backend/`
- Run from `backend/`: Uses `backend/pytest.ini` → looks in `backend/tests/`
- Both work, but it's inconsistent

**Recommendation:** Keep root-level, remove backend-level

**Action:** ❌ **REMOVE** `backend/pytest.ini`

**Command:**

```bash
cd /home/marcel/projects/statuswatch-project
rm backend/pytest.ini
```

**Why Keep Root Level:**

- Allows running tests from project root (common in mono-repo)
- Has better options (`-q --reuse-db` for speed)
- More flexible for CI/CD

**Update Root pytest.ini (Optional Enhancement):**

```ini
[pytest]
# Django config
DJANGO_SETTINGS_MODULE = app.settings

# What files to treat as tests
python_files = tests.py test_*.py *_test.py *_tests.py

# Where to look for tests
testpaths = backend/tests

# Performance + output
addopts = -v --reuse-db --strict-markers --tb=short

# Mark declarations (prevents warnings)
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
```

---

### 4. ⚠️ REVIEW: `templates/welcome.html`

**Status:** Possibly Unused

**Location:** `/home/marcel/projects/statuswatch-project/backend/templates/welcome.html`

**Content:**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Django 5 + DRF</title>
  </head>
  <body>
    <h1>It worked 🎉</h1>
    <p>
      Your local stack is up behind OpenResty (HTTPS):
      <code>django-01.local</code>
    </p>
    <ul>
      <li><a href="/api/ping/">/api/ping/</a> – DRF health</li>
      <li><a href="/admin/">/admin/</a> – Django admin</li>
    </ul>
  </body>
</html>
```

**Usage Check:**

**❌ Not used in `urls_public.py`:**

```python
# urls_public.py
def home(_): return HttpResponse("public OK")  # Simple text response
path("", home),  # No template
```

**❌ Not used in `urls_tenant.py`:**

```python
# urls_tenant.py
path("", lambda r: HttpResponse("tenant OK"), name="tenant-home"),  # Simple text
```

**✅ Referenced in old `urls.py` (which we're removing):**

```python
# urls.py (legacy, being removed)
path('', TemplateView.as_view(template_name='welcome.html'), name='home'),
```

**Decision:**

**Option A:** Remove it (recommended)

- Not currently used in active URL configs
- Simple text responses work fine
- Frontend will handle all HTML rendering

**Option B:** Keep it for manual testing

- Useful for quick "is the server running?" check
- Can access directly via browser
- Minimal file size

**Recommendation:** ⚠️ **Keep for now** (useful for dev debugging), but consider removing before production.

**If Keeping, Update Content:**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>StatusWatch API</title>
    <style>
      body {
        font-family: system-ui;
        max-width: 600px;
        margin: 3rem auto;
        line-height: 1.6;
      }
      code {
        background: #f4f4f4;
        padding: 0.2em 0.4em;
        border-radius: 3px;
      }
    </style>
  </head>
  <body>
    <h1>StatusWatch API 🚀</h1>
    <p>Backend server is running successfully.</p>
    <h2>API Endpoints</h2>
    <ul>
      <li><a href="/api/ping/">/api/ping/</a> – Health check</li>
      <li>
        <a href="/api/auth/token/">/api/auth/token/</a> – JWT login (POST)
      </li>
      <li>
        <a href="/api/auth/register/">/api/auth/register/</a> – Registration
        (POST)
      </li>
      <li><a href="/admin/">/admin/</a> – Django admin panel</li>
    </ul>
    <h2>Documentation</h2>
    <ul>
      <li><a href="/api/schema/">/api/schema/</a> – OpenAPI schema</li>
      <li>
        <a href="/api/schema/swagger-ui/">/api/schema/swagger-ui/</a> – Swagger
        UI
      </li>
    </ul>
    <p>
      <small
        >For frontend, go to:
        <a href="http://localhost:5173">http://localhost:5173</a></small
      >
    </p>
  </body>
</html>
```

---

### 5. ⚠️ REVIEW: Test Utility Scripts

**Location:** `backend/scripts/`

**Files:**

1. `create_acme_user.py` - Creates test user in "acme" tenant
2. `create_jwt_user.py` - Creates JWT test user
3. `generate_secret_key.py` - Generates Django SECRET_KEY
4. `list_tenants.py` - Lists all tenants

**Analysis:**

#### `create_acme_user.py`

```python
# Creates user 'jwt' with password 'JwtP@ss123456' in 'acme' schema
```

**Status:** ✅ **Keep**  
**Reason:** Useful for setting up test users in specific tenants during development

#### `create_jwt_user.py`

```python
# Creates user 'jwt' with password 'JwtP@ss123456' in default schema
```

**Status:** ⚠️ **Duplicate of create_acme_user.py?**  
**Note:** Both create the same user (`jwt` / `JwtP@ss123456`), but in different schemas

- `create_acme_user.py`: Creates in `acme` tenant schema
- `create_jwt_user.py`: Creates in default/public schema

**Recommendation:** ✅ **Keep both** - they serve different purposes (public vs tenant users)

#### `generate_secret_key.py`

**Status:** ✅ **Keep**  
**Reason:** Useful utility for generating SECRET_KEY in production

#### `list_tenants.py`

**Status:** ✅ **Keep**  
**Reason:** Useful for debugging tenant issues

**Action:** ✅ **Keep all utility scripts** - they're small and useful for development/debugging

---

## TODO Comments Found

**File:** `backend/app/settings.py`

```python
# Line 411
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")  # TODO: Remove unsafe-inline when frontend uses nonces
```

**Status:** ✅ Documented in P1-03  
**Action:** No immediate action needed (tracked in docs)

**Future Task:** Implement CSP nonces when frontend is mature

---

## Additional Cleanup Opportunities

### 1. Unused Imports (Minor)

No significant unused imports found. The codebase is clean!

### 2. `.pyc` and `__pycache__` Cleanup

**Check:**

```bash
find /home/marcel/projects/statuswatch-project/backend -type d -name "__pycache__" | wc -l
# Shows count of __pycache__ directories
```

**Action:** Already ignored by `.gitignore` ✅

### 3. Log Files

**Location:** `backend/logs/`

**Action:** Check size and clean up old logs if needed

```bash
du -sh /home/marcel/projects/statuswatch-project/backend/logs/
```

**Recommendation:** Add to `.gitignore`:

```gitignore
# Logs
backend/logs/*.log
backend/logs/*.log.*
```

---

## Action Items Summary

| Item                     | Action             | Priority | Command                   |
| ------------------------ | ------------------ | -------- | ------------------------- |
| `backend/app/urls.py`    | **DELETE**         | High     | `rm backend/app/urls.py`  |
| `backend/pytest.ini`     | **DELETE**         | Medium   | `rm backend/pytest.ini`   |
| `templates/welcome.html` | **Keep or Update** | Low      | Update content (optional) |
| `scripts/*.py`           | **Keep**           | -        | No action                 |
| `db.sqlite3`             | **Keep**           | -        | Ensure in `.gitignore`    |

---

## Cleanup Commands

Run these commands to clean up legacy files:

```bash
# Navigate to project root
cd /home/marcel/projects/statuswatch-project

# Remove legacy URLs file
rm backend/app/urls.py

# Remove duplicate pytest config
rm backend/pytest.ini

# Verify tests still pass
cd backend && python -m pytest -v

# Should see: 120 passed
```

---

## Verification After Cleanup

1. **Run full test suite:**

   ```bash
   cd backend
   python -m pytest -v
   # Expected: 120 passed
   ```

2. **Check Django doesn't complain:**

   ```bash
   python manage.py check
   # Expected: System check identified no issues
   ```

3. **Start dev server:**

   ```bash
   python manage.py runserver
   # Should start without errors
   ```

4. **Test key endpoints:**
   ```bash
   curl http://localhost:8000/api/ping/
   # Expected: {"status":"ok"}
   ```

---

## .gitignore Additions

Ensure these patterns are in `.gitignore`:

```gitignore
# Database
backend/db.sqlite3
backend/db.sqlite3-journal
*.db

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Django
backend/staticfiles/
backend/mediafiles/
backend/logs/*.log

# Testing
.pytest_cache/
.coverage
htmlcov/

# Environment
.env
.venv/
venv/
env/

# IDEs
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

---

## Conclusion

**Files to Remove:** 2

- `backend/app/urls.py` (unused legacy)
- `backend/pytest.ini` (duplicate)

**Files to Keep:**

- `db.sqlite3` (fallback database)
- All scripts in `backend/scripts/` (useful utilities)
- `templates/welcome.html` (optional - can update or remove later)

**Next Steps:**

1. Run cleanup commands above
2. Verify tests pass (120/120)
3. Commit changes
4. Continue with product features or P1-04 (Audit Logging)

**Clean codebase achieved!** ✅
