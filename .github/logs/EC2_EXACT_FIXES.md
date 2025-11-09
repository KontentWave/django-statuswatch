# EC2 Setup - Exact Fix Commands

**Based on structure investigation from:** November 8, 2025, 19:37 UTC  
**Your Setup:**

- **Compose dir:** `/opt/statuswatch/`
- **Git repo:** `/opt/statuswatch/django-statuswatch/`
- **Containers:** statuswatch-web-1, statuswatch-caddy-1, statuswatch-db-1, statuswatch-redis-1
- **Image:** ghcr.io/kontentwave/statuswatch-web:edge

---

## 📋 Run This Complete Diagnostic First

```bash
cd /opt/statuswatch/django-statuswatch
chmod +x .github/logs/final_diagnostics.sh
./.github/logs/final_diagnostics.sh
```

This will show you:

1. If `/opt/statuswatch/.env` exists (it probably doesn't)
2. Current tenants and domains in database
3. Whether jwt@example.com user exists in acme schema
4. Password verification results
5. Actual login endpoint responses

---

## 🔧 Complete Fix Sequence (Copy-Paste Ready)

### Step 1: Create Missing .env File

```bash
cd /opt/statuswatch

# Create .env file (the symlink target)
cat > .env << 'EOF'
# Django Core
DJANGO_ENV=production
SECRET_KEY=CHANGE-THIS-TO-RANDOM-50-CHARACTER-STRING-IN-PRODUCTION
DEBUG=False
ALLOWED_HOSTS=statuswatch.kontentwave.digital,*.kontentwave.digital,localhost,127.0.0.1

# Database (matches your compose.yaml)
DATABASE_URL=postgresql://postgres:devpass@db:5432/dj01
DB_CONN_MAX_AGE=600

# Redis (matches your compose.yaml)
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Stripe (get real values from Stripe dashboard)
STRIPE_PUBLIC_KEY=pk_live_your_public_key_here
STRIPE_SECRET_KEY=sk_live_your_secret_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here
STRIPE_PRO_PRICE_ID=price_your_price_id_here

# Frontend
FRONTEND_URL=https://statuswatch.kontentwave.digital

# Logging
LOG_TO_FILE=1
EOF

# Verify it was created
ls -la /opt/statuswatch/.env
```

### Step 2: Restart Web Container

```bash
cd /opt/statuswatch
docker compose restart web

# Wait for it to be healthy
sleep 5
docker ps | grep web
```

### Step 3: Add Domains to Database

```bash
cd /opt/statuswatch

docker compose exec -T web python manage.py shell << 'PYEOF'
import django
django.setup()

from tenants.models import Client, Domain

# Create/get public tenant
public, created_pub = Client.objects.get_or_create(
    schema_name='public',
    defaults={'name': 'StatusWatch'}
)
print(f"Public tenant: {'created' if created_pub else 'exists'}")

# Create public domain
pub_domain, created_pd = Domain.objects.get_or_create(
    domain='statuswatch.kontentwave.digital',
    defaults={'tenant': public, 'is_primary': True}
)
print(f"Public domain: {'created' if created_pd else 'exists'} - {pub_domain.domain}")

# Create/get acme tenant
acme, created_acme = Client.objects.get_or_create(
    schema_name='acme',
    defaults={'name': 'Acme Corporation'}
)
print(f"Acme tenant: {'created' if created_acme else 'exists'}")

# If acme was just created, run migrations for it
if created_acme:
    from django.core.management import call_command
    call_command('migrate_schemas', schema_name='acme', interactive=False)
    print("Ran migrations for acme schema")

# Create acme domain
acme_domain, created_ad = Domain.objects.get_or_create(
    domain='acme.statuswatch.kontentwave.digital',
    defaults={'tenant': acme, 'is_primary': True}
)
print(f"Acme domain: {'created' if created_ad else 'exists'} - {acme_domain.domain}")

print("\nAll domains:")
for d in Domain.objects.all():
    print(f"  {d.domain:45} -> {d.tenant.schema_name:15} (primary={d.is_primary})")
PYEOF
```

### Step 4: Create/Update User in Acme Schema

```bash
cd /opt/statuswatch

docker compose exec -T web python manage.py shell << 'PYEOF'
import django
django.setup()

from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
from tenants.models import Client

User = get_user_model()

# Verify acme tenant exists
try:
    acme = Client.objects.get(schema_name='acme')
    print(f"✓ Acme tenant found: {acme.name}")

    with schema_context('acme'):
        # Create or get user
        user, created = User.objects.get_or_create(
            email='jwt@example.com',
            defaults={
                'username': 'jwt@example.com',
                'is_active': True,
                'is_staff': False,
                'is_superuser': False,
            }
        )

        # Set password (always, to ensure it's correct)
        user.set_password('TestPass123!')
        user.is_active = True
        user.save()

        # Verify
        pwd_ok = user.check_password('TestPass123!')
        print(f"{'✓ Created' if created else '✓ Updated'} user: {user.email}")
        print(f"  - Active: {user.is_active}")
        print(f"  - Password correct: {pwd_ok}")
        print(f"  - Hash: {user.password[:40]}...")

        if not pwd_ok:
            print("  ❌ WARNING: Password verification failed!")

except Client.DoesNotExist:
    print("❌ ERROR: Acme tenant doesn't exist. Run Step 3 first!")
PYEOF
```

### Step 5: Test Login

```bash
echo "Testing login endpoint..."
echo ""

echo "1. Test with acme subdomain (should work):"
curl -k -X POST "https://acme.statuswatch.kontentwave.digital/api/auth/token/" \
  -H "Content-Type: application/json" \
  -d '{"username":"jwt@example.com","password":"TestPass123!"}' \
  -w "\n\nHTTP Status: %{http_code}\n" 2>&1

echo ""
echo "2. Test internal (direct to gunicorn with Host header):"
docker compose exec -T web curl -sS -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -H "Host: acme.statuswatch.kontentwave.digital" \
  -d '{"username":"jwt@example.com","password":"TestPass123!"}' \
  -w "\n\nHTTP Status: %{http_code}\n"
```

---

## ✅ Expected Results

After running all steps, you should see:

**Step 3 output:**

```
Public tenant: exists
Public domain: created - statuswatch.kontentwave.digital
Acme tenant: exists
Acme domain: created - acme.statuswatch.kontentwave.digital
```

**Step 4 output:**

```
✓ Acme tenant found: Acme Corporation
✓ Updated user: jwt@example.com
  - Active: True
  - Password correct: True
```

**Step 5 output:**

```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
HTTP Status: 200
```

---

## 🚨 Troubleshooting

### If Step 3 fails with "Apps aren't loaded yet"

```bash
# The django.setup() call should fix it, but if not:
docker compose restart web
# Wait 10 seconds and try again
```

### If Step 4 shows "Password correct: False"

```bash
# Check what's in the database
docker compose exec -T web python manage.py shell << 'PYEOF'
import django
django.setup()
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
User = get_user_model()
with schema_context('acme'):
    u = User.objects.get(email='jwt@example.com')
    print(f"Hash in DB: {u.password}")
    # Try setting password again with different method
    from django.contrib.auth.hashers import make_password
    u.password = make_password('TestPass123!')
    u.save()
    print(f"New hash: {u.password}")
    print(f"Check: {u.check_password('TestPass123!')}")
PYEOF
```

### If login returns 404

- Check Caddy is running: `docker ps | grep caddy`
- Check Caddy logs: `docker compose logs caddy | tail -50`
- Verify DNS: `dig acme.statuswatch.kontentwave.digital`

### If login returns 400 "username required"

- You're using `email` field instead of `username` in the JSON
- Use: `{"username":"jwt@example.com","password":"TestPass123!"}`

---

## 📊 Verification Commands

After fixes, verify everything:

```bash
# Check .env exists
ls -la /opt/statuswatch/.env

# Check domains
docker compose exec -T web python -c "
import django; django.setup()
from tenants.models import Domain
for d in Domain.objects.all(): print(f'{d.domain} -> {d.tenant.schema_name}')
"

# Check user
docker compose exec -T web python -c "
import django; django.setup()
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
User = get_user_model()
with schema_context('acme'):
    u = User.objects.get(email='jwt@example.com')
    print(f'User: {u.email}, Active: {u.is_active}, Password OK: {u.check_password(\"TestPass123!\")}')"

# Test login
curl -k -X POST "https://acme.statuswatch.kontentwave.digital/api/auth/token/" \
  -H "Content-Type: application/json" \
  -d '{"username":"jwt@example.com","password":"TestPass123!"}'
```

---

## 📝 Summary of Changes

1. ✅ Created `/opt/statuswatch/.env` (was missing, breaking config loading)
2. ✅ Added domains: `statuswatch.kontentwave.digital` (public) and `acme.statuswatch.kontentwave.digital` (acme)
3. ✅ Created/updated user `jwt@example.com` in acme schema with correct password
4. ✅ Verified login works with correct `username` field

---

**Run the final diagnostics first to confirm what needs fixing, then apply these steps!** 🚀
