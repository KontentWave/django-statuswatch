# EC2 Authentication Diagnostics - Instructions

**Generated:** November 7, 2025  
**Issue:** Login works on local machine but fails on EC2 with "No active account found with the given credentials"  
**User:** jwt@example.com | Password: TestPass123! | Tenant: acme

---

## Summary

I've created comprehensive diagnostic tools and enhanced logging to identify why authentication fails on EC2 but works locally.

### What Was Done

1. ✅ **Created comprehensive diagnostic script** (`ec2_auth_diagnostics.sh`)
2. ✅ **Enhanced authentication logging** (added detailed debug logs to `/app/logs/auth_debug.log`)
3. ✅ **Created log analysis helpers** (scripts to read and test authentication)

---

## 🔧 Diagnostic Scripts Created

### 1. **Main Diagnostic Script** - `.github/logs/ec2_auth_diagnostics.sh`

**Comprehensive system check** that gathers:

- Container status & health
- Django deployment checks
- All tenants and domains in database
- User details in acme schema (including password hash verification)
- Direct authentication endpoint testing
- Django settings inspection
- Environment variables (sanitized)
- Middleware & authentication backend configuration
- Recent application logs
- Database password hash queries
- SimpleJWT configuration
- Nginx/proxy logs
- File permissions

**Run this FIRST:**

```bash
cd /home/marcel/projects/statuswatch-project
chmod +x .github/logs/ec2_auth_diagnostics.sh
./.github/logs/ec2_auth_diagnostics.sh > .github/logs/diagnostic_output.txt 2>&1
```

### 2. **Quick Auth Test** - `.github/logs/test_auth.sh`

**Fast authentication testing** that:

- Tests login from outside container (via nginx)
- Tests login from inside container (direct Django)
- Reads auth debug logs
- Checks user in database with password verification

**Usage:**

```bash
chmod +x .github/logs/test_auth.sh
./.github/logs/test_auth.sh jwt@example.com TestPass123! acme.statuswatch.kontentwave.digital
```

### 3. **Log Reader** - `.github/logs/read_auth_debug_logs.sh`

**Read debug logs** from enhanced authentication logging:

```bash
chmod +x .github/logs/read_auth_debug_logs.sh
./.github/logs/read_auth_debug_logs.sh 50  # Last 50 lines
```

**Real-time monitoring:**

```bash
docker exec backend tail -f /app/logs/auth_debug.log | python3 -m json.tool
```

---

## 🔍 Enhanced Authentication Logging

Modified `/backend/api/views.py` to add **detailed debug logging** that captures:

### Login Attempt Data:

- Email & password length
- Tenant schema & routing info
- User existence check
- User active status
- Password hash prefix
- **Direct password verification result**
- Host, origin, IP address
- User agent

### Login Failure Data:

- Exception type & message
- Detailed reason for failure

### Login Success Data:

- User ID & email
- Schema confirmation
- Request metadata

**Log Location:** `/app/logs/auth_debug.log` (inside backend container)

---

## 📋 Step-by-Step Diagnostic Procedure

### Step 1: Run Main Diagnostics

```bash
cd /home/marcel/projects/statuswatch-project
chmod +x .github/logs/ec2_auth_diagnostics.sh
./.github/logs/ec2_auth_diagnostics.sh > .github/logs/diagnostic_output_$(date +%Y%m%d_%H%M%S).txt 2>&1
```

### Step 2: Test Authentication

```bash
chmod +x .github/logs/test_auth.sh
./.github/logs/test_auth.sh
```

### Step 3: Attempt Login via Browser

Try logging in through the web interface while monitoring logs in real-time:

**Terminal 1 - Watch debug logs:**

```bash
docker exec backend tail -f /app/logs/auth_debug.log | python3 -m json.tool
```

**Terminal 2 - Watch Django logs:**

```bash
docker logs -f backend
```

**Terminal 3 - Watch Nginx logs:**

```bash
docker logs -f nginx
```

### Step 4: Collect Output

After attempting login, collect all outputs:

```bash
# Read debug logs
./.github/logs/read_auth_debug_logs.sh 100 > .github/logs/auth_debug_output.txt

# Get recent backend logs
docker logs --tail 200 backend > .github/logs/backend_logs.txt 2>&1

# Get recent nginx logs
docker logs --tail 200 nginx > .github/logs/nginx_logs.txt 2>&1
```

---

## 🎯 What to Look For

### Critical Questions the Diagnostics Answer:

1. **Does the user exist in the database?**

   - Check: Section 4 of diagnostics

2. **Is the password hash correct?**

   - Check: Section 4 (password hash prefix)
   - Check: Section 10 (direct database query)

3. **Does password verification work?**

   - Check: Section 4 (`user.check_password()` result)
   - Check: `auth_debug.log` → `password_check_result`

4. **Is the tenant routing correct?**

   - Check: Section 3 (tenant & domain list)
   - Check: `auth_debug.log` → `schema_name`, `host`

5. **Are environment variables correct?**

   - Check: Section 7 (sanitized env vars)
   - Look for: `DATABASE_URL`, `DJANGO_ENV`, `ALLOWED_HOSTS`

6. **Is Django using the right settings?**

   - Check: Section 6 (Django settings)
   - Verify: `DEBUG`, `ALLOWED_HOSTS`, tenant configuration

7. **What does the authentication serializer see?**
   - Check: `auth_debug.log` → all captured request data

---

## 🔥 Common Issues to Check

### 1. Password Hash Mismatch

**Symptom:** User exists but password check fails  
**Check:** Compare password hash prefix between local and EC2  
**Solution:** May need to recreate user on EC2

### 2. Wrong Schema/Tenant

**Symptom:** Request routes to wrong tenant  
**Check:** `schema_name` in logs vs expected "acme"  
**Solution:** Domain configuration or nginx routing issue

### 3. Database Connection

**Symptom:** Cannot query user table  
**Check:** Section 2 & 10 of diagnostics  
**Solution:** Database connection or migration issue

### 4. Environment Mismatch

**Symptom:** Settings differ between local and EC2  
**Check:** Section 7 (env vars) and Section 6 (Django settings)  
**Solution:** Environment configuration issue

### 5. Middleware/Auth Backend

**Symptom:** Request doesn't reach authentication view  
**Check:** Section 8 (middleware stack)  
**Solution:** Middleware ordering or configuration issue

---

## 📤 What to Share

After running the diagnostics, please share these files:

1. **Full diagnostic output:** `.github/logs/diagnostic_output.txt`
2. **Auth debug logs:** `.github/logs/auth_debug_output.txt`
3. **Backend logs:** `.github/logs/backend_logs.txt`
4. **Nginx logs:** `.github/logs/nginx_logs.txt`
5. **Test auth output:** Output from `test_auth.sh`

You can create a single archive:

```bash
cd .github/logs
tar -czf ec2_diagnostics_$(date +%Y%m%d_%H%M%S).tar.gz *.txt *.log diagnostic_output* 2>/dev/null
```

---

## 🚀 Quick Commands Reference

```bash
# Make scripts executable
chmod +x .github/logs/*.sh

# Run full diagnostics
./.github/logs/ec2_auth_diagnostics.sh > .github/logs/diagnostic_output.txt 2>&1

# Quick auth test
./.github/logs/test_auth.sh

# Watch debug logs live
docker exec backend tail -f /app/logs/auth_debug.log | python3 -m json.tool

# Read last 50 debug entries
./.github/logs/read_auth_debug_logs.sh 50

# Check if user exists
docker exec backend python manage.py shell -c "
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
User = get_user_model()
with schema_context('acme'):
    user = User.objects.get(email='jwt@example.com')
    print(f'User: {user.email}, Active: {user.is_active}')
    print(f'Password check: {user.check_password(\"TestPass123!\")}')"

# Restart backend to apply logging changes
docker restart backend

# View container logs
docker logs -f backend
docker logs -f nginx
```

---

## 🔄 Next Steps

1. **On EC2 instance**, run the main diagnostic script
2. **Attempt login** via browser while monitoring logs
3. **Collect all outputs** using commands above
4. **Share the files** here for analysis
5. Based on the diagnostics, I'll provide specific fixes

---

## ⚠️ Important Notes

- **Restart backend container** after pulling updated code to apply logging changes:

  ```bash
  docker restart backend
  ```

- **Debug logs persist** across restarts (in mounted volume or container storage)

- **Sanitization:** The scripts mask sensitive data (passwords, keys) in output

- **Performance:** Debug logging has minimal impact but can be disabled after fixing by commenting out `_write_debug_log()` calls

---

Ready to diagnose! Run the scripts and share the output. 🔍✨
