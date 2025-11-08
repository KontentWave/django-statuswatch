# EC2 Authentication Diagnostics - CRITICAL FINDINGS

**Date:** November 8, 2025  
**Status:** 🔴 **3 CRITICAL ISSUES IDENTIFIED**

---

## 🔴 ISSUE #1: Missing `.env` File

**Error:** `env file /opt/statuswatch/django-statuswatch/backend/.env not found`

**Impact:** Django cannot load environment variables (DATABASE_URL, SECRET_KEY, etc.)

**Location:** Expected at `/opt/statuswatch/django-statuswatch/backend/.env`

### Fix:

```bash
cd /opt/statuswatch

# Create .env file (adjust paths as needed)
cat > .env << 'EOF'
# Django
DJANGO_ENV=production
SECRET_KEY=your-production-secret-key-change-this
DEBUG=False
ALLOWED_HOSTS=statuswatch.kontentwave.digital,*.kontentwave.digital

# Database
DATABASE_URL=postgresql://user:password@db:5432/statuswatch
DB_CONN_MAX_AGE=600

# Redis
REDIS_URL=redis://redis:6379/0

# Stripe (optional for now)
STRIPE_PUBLIC_KEY=pk_test_xxx
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Frontend
FRONTEND_URL=https://statuswatch.kontentwave.digital
EOF
```

---

## 🔴 ISSUE #2: No Domains Configured

**Error:**

```
Detected domains:
  public: <none>
  acme:   <none>
```

**Impact:** Tenant routing doesn't work - no domain maps to any tenant

### Fix:

```bash
# Add domains to database
docker compose exec -T web python manage.py shell << 'PY'
from tenants.models import Client, Domain

# Get or create public tenant
public, _ = Client.objects.get_or_create(
    schema_name='public',
    defaults={'name': 'Public'}
)

# Create public domain
Domain.objects.get_or_create(
    domain='statuswatch.kontentwave.digital',
    defaults={'tenant': public, 'is_primary': True}
)

# Get or create acme tenant
acme, created = Client.objects.get_or_create(
    schema_name='acme',
    defaults={'name': 'Acme Corp'}
)

if created:
    print("Created acme tenant")

# Create acme domain
Domain.objects.get_or_create(
    domain='acme.statuswatch.kontentwave.digital',
    defaults={'tenant': acme, 'is_primary': True}
)

print("Domains configured:")
for d in Domain.objects.all():
    print(f"  {d.domain} -> {d.tenant.schema_name}")
PY
```

---

## 🔴 ISSUE #3: Wrong API Field Name

**Error:** `{"username":["This field is required."]}`

**Cause:** Test script sends `"email"` but API expects `"username"`

### Fix Test Script:

The login endpoint accepts **`username`** field (which can be an email address).

Update test to use:

```json
{ "username": "jwt@example.com", "password": "TestPass123!" }
```

Not:

```json
{ "email": "jwt@example.com", "password": "TestPass123!" }
```

---

## 📋 DIAGNOSTIC COMMANDS TO RUN

Run these **in order** on your EC2 instance:

### 1. Structure Investigation

```bash
cd /opt/statuswatch
chmod +x .github/logs/investigate_structure.sh
./.github/logs/investigate_structure.sh > structure_report.txt 2>&1
```

### 2. Check Current Working Directory

```bash
pwd
ls -la
```

### 3. Find Compose File

```bash
find . -name "compose.yml" -o -name "docker-compose.yml"
```

### 4. Check Container Names

```bash
docker ps --format "{{.Names}}\t{{.Image}}"
```

### 5. Test Database Connection

```bash
docker compose exec -T web python -c "
from django.db import connection
with connection.cursor() as c:
    c.execute('SELECT version()')
    print(c.fetchone()[0])
"
```

### 6. Check Tenants

```bash
docker compose exec -T web python -c "
from tenants.models import Client
for c in Client.objects.all():
    print(f'{c.schema_name} | {c.name}')
"
```

### 7. Check Domains

```bash
docker compose exec -T web python -c "
from tenants.models import Domain
for d in Domain.objects.all():
    print(f'{d.domain} -> {d.tenant.schema_name}')
"
```

### 8. Check User Exists

```bash
docker compose exec -T web python -c "
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
User = get_user_model()
with schema_context('acme'):
    try:
        u = User.objects.get(email='jwt@example.com')
        print(f'User found: {u.email}')
        print(f'Active: {u.is_active}')
        print(f'Password OK: {u.check_password(\"TestPass123!\")}'  )
    except User.DoesNotExist:
        print('User NOT found in acme schema')
"
```

### 9. Test Login API (Corrected)

```bash
# External test with correct field name
curl -k -X POST "https://statuswatch.kontentwave.digital/api/auth/token/" \
  -H "Content-Type: application/json" \
  -d '{"username":"jwt@example.com","password":"TestPass123!"}' \
  -v
```

---

## 🚀 QUICK FIX SEQUENCE

```bash
cd /opt/statuswatch

# 1. Create .env file (copy production values)
nano .env  # or use cat > .env << 'EOF' ... EOF

# 2. Restart containers to pick up .env
docker compose restart web

# 3. Add domains
docker compose exec -T web python manage.py shell << 'PY'
from tenants.models import Client, Domain
public, _ = Client.objects.get_or_create(schema_name='public', defaults={'name': 'Public'})
Domain.objects.get_or_create(domain='statuswatch.kontentwave.digital', defaults={'tenant': public, 'is_primary': True})
acme, _ = Client.objects.get_or_create(schema_name='acme', defaults={'name': 'Acme Corp'})
Domain.objects.get_or_create(domain='acme.statuswatch.kontentwave.digital', defaults={'tenant': acme, 'is_primary': True})
print("Done!")
PY

# 4. Create user if doesn't exist
docker compose exec -T web python manage.py shell << 'PY'
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
User = get_user_model()
with schema_context('acme'):
    user, created = User.objects.get_or_create(
        email='jwt@example.com',
        defaults={'username': 'jwt@example.com'}
    )
    user.set_password('TestPass123!')
    user.is_active = True
    user.save()
    print(f"User {'created' if created else 'updated'}: {user.email}")
PY

# 5. Test login with correct field
curl -k -X POST "https://acme.statuswatch.kontentwave.digital/api/auth/token/" \
  -H "Content-Type: application/json" \
  -d '{"username":"jwt@example.com","password":"TestPass123!"}'
```

---

## ⚠️ PRIORITY

1. **FIRST**: Run `investigate_structure.sh` and share output
2. **SECOND**: Create `.env` file with production values
3. **THIRD**: Add domains to database
4. **FOURTH**: Test login with corrected API call

---

**Next Step:** Run the investigation script and share the output so I can provide exact commands for your setup.
