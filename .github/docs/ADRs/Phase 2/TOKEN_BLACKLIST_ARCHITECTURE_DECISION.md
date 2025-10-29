# Architecture Decision: Token Blacklist Reverted to Per-Tenant

**Date:** October 29, 2025  
**Decision:** Revert token blacklist from PUBLIC schema back to per-tenant schemas

## Problem

Moving `token_blacklist` to PUBLIC schema (SHARED_APPS) caused FK constraint violations in tests because:

1. `token_blacklist_outstandingtoken` has FK to `auth_user(id)`
2. `auth_user` table exists in tenant schemas, not PUBLIC schema
3. Tests create users in tenant schemas, causing FK violations

## Options Considered

### Option 1: Keep auth_user in PUBLIC schema

- Add `django.contrib.auth` to SHARED_APPS
- **Rejected:** Creates duplicate user tables, breaks multi-tenancy isolation

### Option 2: Remove FK constraint from token_blacklist

- Create custom migration to drop FK
- **Rejected:** Complex, requires maintaining custom Simple JWT fork

### Option 3: Keep token_blacklist per-tenant (REVERT)

- Move `token_blacklist` back to TENANT_APPS
- Remove custom TokenRefreshView
- **SELECTED:** Simplest, maintains data isolation

## Decision

**Revert to per-tenant token blacklist:**

```python
# settings.py
SHARED_APPS = (
    "django_tenants",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "tenants",
)

TENANT_APPS = (
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework_simplejwt.token_blacklist",  # ← Back to per-tenant
    "api",
    "monitors",
)
```

## Consequences

### ✅ Advantages

- Tests pass - FK constraints work correctly
- Data isolation maintained
- No custom migrations needed
- Standard Simple JWT configuration

### ⚠️ Trade-offs

- Token blacklist per tenant (logout in one tenant doesn't affect others)
- Slightly more database overhead (blacklist tables in each schema)

### 📝 Changes Required

1. ✅ Move `token_blacklist` from SHARED_APPS to TENANT_APPS
2. ✅ Remove custom `MultiTenantTokenRefreshView`
3. ✅ Use standard `TokenRefreshView` from Simple JWT
4. ✅ Update `urls_public.py` and `urls_tenant.py`
5. ⏳ Update documentation (ADR, project sheet)

## Impact on Smart Multi-Tenant Login

**No impact on smart login feature:**

- Multi-tenant detection still works (queries across schemas)
- Tenant selector UI unchanged
- Login flow unchanged
- Only token refresh/blacklist behavior is per-tenant

**User Experience:**

- Logging out from one tenant doesn't log out from other tenants
- Each tenant maintains its own token blacklist
- This is actually **desired behavior** for multi-tenant systems

## Status

✅ **Implemented** - Reverted token blacklist to per-tenant architecture
