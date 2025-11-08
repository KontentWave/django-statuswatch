# EC2 Authentication Diagnostic Package - Ready ✅

**Date:** November 7, 2025  
**Status:** All diagnostic tools created and enhanced logging deployed  
**Next Step:** Run on EC2 instance

---

## 🎯 What Was Done

### 1. ✅ Enhanced Backend Authentication Logging

**File Modified:** `backend/api/views.py`

Added comprehensive debug logging that captures:

- Email, password length, tenant schema
- User existence verification
- **Direct password hash checking** (`user.check_password()`)
- Password hash prefix for comparison
- User active status
- Tenant routing information
- Request metadata (host, origin, IP, user agent)

**Log Location:** `/app/logs/auth_debug.log` (inside backend container)

### 2. ✅ Created 5 Diagnostic Scripts

| Script                    | Purpose                             | Output                        |
| ------------------------- | ----------------------------------- | ----------------------------- |
| `preflight_check.sh`      | Verify system ready for diagnostics | Console                       |
| `run_all_diagnostics.sh`  | **Run everything** (recommended)    | Organized directory + tarball |
| `ec2_auth_diagnostics.sh` | Comprehensive system inspection     | Text file                     |
| `test_auth.sh`            | Quick authentication endpoint test  | Console                       |
| `read_auth_debug_logs.sh` | Parse enhanced auth logs            | Pretty JSON                   |

### 3. ✅ Created Documentation

- `README_DIAGNOSTICS.md` - Complete diagnostic guide
- `QUICK_REFERENCE.txt` - Command cheat sheet
- Auto-generated `SUMMARY.md` in each diagnostic run

---

## 🚀 How to Run (On Your EC2 Instance)

### Option A: Run Everything (Recommended)

```bash
# 1. Pull latest code
cd ~/statuswatch-project
git pull origin main

# 2. Restart backend to apply logging changes
docker restart backend

# 3. Run preflight check
chmod +x .github/logs/preflight_check.sh
./.github/logs/preflight_check.sh

# 4. Run all diagnostics
./.github/logs/run_all_diagnostics.sh
```

**This creates:**

- Organized directory: `.github/logs/diagnostics_TIMESTAMP/`
- Archive file: `.github/logs/diagnostics_TIMESTAMP.tar.gz`
- All diagnostic outputs in one place

### Option B: Individual Commands

```bash
# Quick auth test
./.github/logs/test_auth.sh

# Full diagnostics
./.github/logs/ec2_auth_diagnostics.sh > diagnostics.txt 2>&1

# Watch logs live while testing
docker exec backend tail -f /app/logs/auth_debug.log | python3 -m json.tool
```

---

## 📊 What the Diagnostics Will Tell Us

### Critical Information Captured:

1. **User Verification**

   - Does user exist in database?
   - Is user active?
   - What's the password hash?
   - **Does password verification work?** ← Key question

2. **Tenant Routing**

   - Which schema is request routed to?
   - Are domains configured correctly?
   - Is tenant resolution working?

3. **Configuration**

   - Django settings (DEBUG, ALLOWED_HOSTS)
   - Environment variables
   - Database connection
   - Middleware stack

4. **Authentication Flow**
   - Request metadata (host, origin)
   - JWT serializer behavior
   - Exact failure reason

---

## 🔍 Expected Findings

Based on the symptoms, likely culprits:

### Scenario 1: Password Hash Mismatch (Most Likely)

**Symptoms:**

- User exists ✓
- User active ✓
- Password check fails ✗

**Diagnostic will show:**

```json
{
  "user_exists": true,
  "user_is_active": true,
  "password_check_result": false
}
```

**Fix:** Recreate user with correct password on EC2

### Scenario 2: Wrong Tenant Routing

**Symptoms:**

- Request routes to wrong schema
- User not found in that schema

**Diagnostic will show:**

```json
{
  "schema_name": "public", // Should be "acme"
  "user_exists": false
}
```

**Fix:** Domain configuration issue

### Scenario 3: Database/Migration Issue

**Symptoms:**

- User table not accessible
- Query errors

**Diagnostic will show:**

- Database connection errors
- Missing table errors

**Fix:** Run migrations or check database

---

## 📤 What to Share Back

After running diagnostics on EC2:

### Quick Share:

```bash
# Download to your local machine
scp ubuntu@<EC2-IP>:~/statuswatch-project/.github/logs/diagnostics_*.tar.gz .
```

Then share the `.tar.gz` file here or extract and paste key sections from:

- `full_diagnostics.txt` (Section 4: User details)
- `auth_debug_logs.txt` (Last few login attempts)

### Manual Share:

If you prefer, just copy-paste output from:

1. Section 4 of `ec2_auth_diagnostics.sh` (user verification)
2. Last 10 lines from `auth_debug.log`

---

## 🛠️ Quick Fixes Reference

### If password check fails:

```bash
docker exec -it backend python manage.py shell -c "
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
User = get_user_model()
with schema_context('acme'):
    user = User.objects.get(email='jwt@example.com')
    user.set_password('TestPass123!')
    user.save()
    print('✓ Password reset complete')"
```

### If user doesn't exist:

```bash
docker exec -it backend python manage.py shell
>>> from django_tenants.utils import schema_context
>>> from django.contrib.auth import get_user_model
>>> from tenants.models import Client
>>> User = get_user_model()
>>> tenant = Client.objects.get(schema_name='acme')
>>> with schema_context('acme'):
...     user = User.objects.create_user(
...         email='jwt@example.com',
...         username='jwt@example.com',
...         password='TestPass123!'
...     )
...     print(f'✓ User created: {user.email}')
```

### If schema routing is wrong:

Check domain configuration in database and nginx

---

## 📋 Files Created

```
.github/logs/
├── README_DIAGNOSTICS.md      # Complete guide (you're reading summary)
├── QUICK_REFERENCE.txt        # Command cheat sheet
├── preflight_check.sh         # System readiness check
├── run_all_diagnostics.sh     # One-command solution ⭐
├── ec2_auth_diagnostics.sh    # Comprehensive system check
├── test_auth.sh               # Quick auth test
└── read_auth_debug_logs.sh    # Log parser
```

---

## ⚡ TL;DR - Copy These Commands

```bash
# On EC2:
cd ~/statuswatch-project
git pull origin main
docker restart backend
chmod +x .github/logs/*.sh
./.github/logs/run_all_diagnostics.sh

# Then download results:
# (From your local machine)
scp ubuntu@<EC2-IP>:~/statuswatch-project/.github/logs/diagnostics_*.tar.gz .
```

---

## ✅ Next Steps

1. **Run diagnostics on EC2** (use commands above)
2. **Share the output** (tar.gz file or key sections)
3. **I'll analyze** and provide specific fix
4. **Apply fix** and test
5. **Success!** 🎉

---

**Ready to diagnose!** 🔍✨

Run the commands on your EC2 instance and share the results. The enhanced logging will tell us exactly why authentication is failing.
