#!/bin/bash
# Final diagnostics for EC2 - now with correct paths and setup
# Based on structure investigation results

set -euo pipefail

echo "======================================================================"
echo "StatusWatch EC2 - Final Diagnostics"
echo "Date: $(date)"
echo "======================================================================"
echo ""

# From investigation: compose files are in /opt/statuswatch, repo in /opt/statuswatch/django-statuswatch
REPO_DIR="/opt/statuswatch/django-statuswatch"
COMPOSE_DIR="/opt/statuswatch"

echo "1. ENVIRONMENT FILE CHECK"
echo "----------------------------------------------------------------------"
echo "Checking .env file location (symlink points to /opt/statuswatch/.env):"
ls -la "$REPO_DIR/backend/.env" || echo ".env symlink not found"
echo ""
echo "Checking target file:"
ls -la /opt/statuswatch/.env || echo "/opt/statuswatch/.env NOT FOUND - THIS IS THE PROBLEM!"
echo ""
if [ -f /opt/statuswatch/.env ]; then
    echo "Environment variables (sanitized):"
    grep -E '^(DJANGO_ENV|DATABASE_URL|REDIS_URL|SECRET_KEY|DEBUG|ALLOWED_HOSTS|FRONTEND_URL)' /opt/statuswatch/.env | sed 's/\(SECRET_KEY\|PASSWORD\)=.*/\1=***/' || echo "No matching vars"
else
    echo "❌ CRITICAL: /opt/statuswatch/.env does not exist!"
    echo "This is why Django fails to load configuration."
fi
echo ""

echo "2. CONTAINER ENVIRONMENT VARIABLES"
echo "----------------------------------------------------------------------"
echo "What the web container actually sees:"
docker exec statuswatch-web-1 env | grep -E '(DJANGO_ENV|DATABASE_URL|REDIS_URL|SECRET_KEY|DEBUG|ALLOWED_HOSTS)' | sed 's/\(SECRET_KEY\|PASSWORD\)=.*/\1=***/'
echo ""
echo "Note: DJANGO_ENV shows 'production' but compose.yaml says 'development'"
echo "This means container env overrides .env file settings"
echo ""

echo "3. DJANGO INITIALIZATION TEST"
echo "----------------------------------------------------------------------"
echo "Can Django load settings?"
docker exec statuswatch-web-1 python -c "
import django
django.setup()
from django.conf import settings
print(f'✓ Django loaded successfully')
print(f'  DEBUG: {settings.DEBUG}')
print(f'  ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}')
print(f'  DJANGO_ENV: {settings.DJANGO_ENV}')
" 2>&1 || echo "❌ Django setup failed"
echo ""

echo "4. DATABASE CONNECTION"
echo "----------------------------------------------------------------------"
docker exec statuswatch-web-1 python -c "
import django
django.setup()
from django.db import connection
try:
    with connection.cursor() as c:
        c.execute('SELECT version()')
        print('✓ Database connected:', c.fetchone()[0][:50])
except Exception as e:
    print('❌ Database error:', e)
"
echo ""

echo "5. TENANTS IN DATABASE"
echo "----------------------------------------------------------------------"
docker exec statuswatch-web-1 python -c "
import django
django.setup()
from tenants.models import Client
print('Tenants in database:')
for c in Client.objects.all():
    print(f'  - {c.schema_name:15} | {c.name:20} | subscription={c.subscription_status}')
if not Client.objects.exists():
    print('  ❌ NO TENANTS FOUND')
"
echo ""

echo "6. DOMAINS IN DATABASE"
echo "----------------------------------------------------------------------"
docker exec statuswatch-web-1 python -c "
import django
django.setup()
from tenants.models import Domain
print('Domains in database:')
for d in Domain.objects.all():
    print(f'  {d.domain:40} -> {d.tenant.schema_name:15} (primary={d.is_primary})')
if not Domain.objects.exists():
    print('  ❌ NO DOMAINS FOUND - THIS IS WHY TENANT ROUTING FAILS')
"
echo ""

echo "7. USER CHECK IN ACME SCHEMA"
echo "----------------------------------------------------------------------"
docker exec statuswatch-web-1 python -c "
import django
django.setup()
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
from tenants.models import Client

User = get_user_model()

# Check if acme tenant exists
try:
    acme = Client.objects.get(schema_name='acme')
    print(f'✓ Acme tenant exists: {acme.name}')

    with schema_context('acme'):
        users = User.objects.all()
        print(f'  Total users in acme schema: {users.count()}')

        if users.exists():
            for user in users:
                pwd_check = user.check_password('TestPass123!')
                print(f'  - {user.email:30} active={user.is_active} pwd_ok={pwd_check}')
        else:
            print('  ❌ NO USERS IN ACME SCHEMA')

        # Specific check for jwt@example.com
        try:
            jwt_user = User.objects.get(email='jwt@example.com')
            print(f'\\n✓ User jwt@example.com found:')
            print(f'  - Active: {jwt_user.is_active}')
            print(f'  - Password correct: {jwt_user.check_password(\"TestPass123!\")}')
            print(f'  - Hash prefix: {jwt_user.password[:30]}')
        except User.DoesNotExist:
            print(f'\\n❌ User jwt@example.com NOT FOUND in acme schema')

except Client.DoesNotExist:
    print('❌ Acme tenant does NOT exist in database')
"
echo ""

echo "8. PUBLIC SCHEMA CHECK"
echo "----------------------------------------------------------------------"
docker exec statuswatch-web-1 python -c "
import django
django.setup()
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
from tenants.models import Client

User = get_user_model()

try:
    public = Client.objects.get(schema_name='public')
    print(f'✓ Public tenant exists: {public.name}')

    with schema_context('public'):
        users = User.objects.all()
        print(f'  Total users in public schema: {users.count()}')
        if users.exists():
            for user in users:
                print(f'  - {user.email:30} active={user.is_active}')
except Client.DoesNotExist:
    print('❌ Public tenant does NOT exist')
"
echo ""

echo "9. AUTH ENDPOINT TEST (Internal)"
echo "----------------------------------------------------------------------"
echo "Testing login endpoint from inside container:"
echo ""
echo "A) Without domain (should fail - no tenant routing):"
docker exec statuswatch-web-1 curl -sS -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"jwt@example.com","password":"TestPass123!"}' || true
echo ""
echo ""
echo "B) With acme.statuswatch.kontentwave.digital host header:"
docker exec statuswatch-web-1 curl -sS -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -H "Host: acme.statuswatch.kontentwave.digital" \
  -d '{"username":"jwt@example.com","password":"TestPass123!"}' || true
echo ""
echo ""
echo "C) With statuswatch.kontentwave.digital host header (public tenant):"
docker exec statuswatch-web-1 curl -sS -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -H "Host: statuswatch.kontentwave.digital" \
  -d '{"username":"jwt@example.com","password":"TestPass123!"}' || true
echo ""

echo ""
echo "10. EXTERNAL AUTH TEST (via Caddy)"
echo "----------------------------------------------------------------------"
echo "Testing from outside (what users experience):"
echo ""
echo "Public domain test:"
curl -k -sS -X POST "https://statuswatch.kontentwave.digital/api/auth/token/" \
  -H "Content-Type: application/json" \
  -d '{"username":"jwt@example.com","password":"TestPass123!"}' \
  -w "\nHTTP Status: %{http_code}\n" 2>&1 || true
echo ""
echo "Acme subdomain test:"
curl -k -sS -X POST "https://acme.statuswatch.kontentwave.digital/api/auth/token/" \
  -H "Content-Type: application/json" \
  -d '{"username":"jwt@example.com","password":"TestPass123!"}' \
  -w "\nHTTP Status: %{http_code}\n" 2>&1 || true
echo ""

echo "======================================================================"
echo "DIAGNOSTIC SUMMARY"
echo "======================================================================"
echo ""
echo "Key findings will be above. Look for:"
echo "  1. ❌ /opt/statuswatch/.env missing"
echo "  2. ❌ NO DOMAINS FOUND"
echo "  3. ❌ NO USERS IN ACME SCHEMA"
echo "  4. Password verification results"
echo ""
echo "======================================================================"
