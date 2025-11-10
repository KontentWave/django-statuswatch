#!/bin/bash
# Diagnostic commands for login flow investigation

echo "=== 1. Check public schema users ==="
ssh -i ~/.ssh/discourse-poc-key.pem ubuntu@13.62.178.108 "cd /opt/statuswatch && docker compose exec -T web python manage.py shell <<'EOF'
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context
User = get_user_model()

print('\n--- PUBLIC SCHEMA USERS ---')
with schema_context('public'):
    users = User.objects.all()
    print(f'Total users in public schema: {users.count()}')
    for u in users:
        print(f'  - {u.email} (active: {u.is_active})')
EOF
"

echo -e "\n=== 2. Check acme tenant schema users ==="
ssh -i ~/.ssh/discourse-poc-key.pem ubuntu@13.62.178.108 "cd /opt/statuswatch && docker compose exec -T web python manage.py shell <<'EOF'
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context
User = get_user_model()

print('\n--- ACME TENANT SCHEMA USERS ---')
with schema_context('acme'):
    users = User.objects.all()
    print(f'Total users in acme schema: {users.count()}')
    for u in users:
        print(f'  - {u.email} (active: {u.is_active})')
EOF
"

echo -e "\n=== 3. Check which schema is used for statuswatch.kontentwave.digital ==="
ssh -i ~/.ssh/discourse-poc-key.pem ubuntu@13.62.178.108 "cd /opt/statuswatch && docker compose exec -T web python manage.py shell <<'EOF'
from tenants.models import Domain, Client
from django.db import connection

print('\n--- DOMAIN ROUTING ---')
# Check statuswatch.kontentwave.digital
try:
    domain = Domain.objects.get(domain='statuswatch.kontentwave.digital')
    print(f'statuswatch.kontentwave.digital -> tenant: {domain.tenant.schema_name} ({domain.tenant.name})')
    print(f'  is_primary: {domain.is_primary}')
except Domain.DoesNotExist:
    print('statuswatch.kontentwave.digital -> NOT FOUND (will use public schema)')

# Check acme subdomain
try:
    domain = Domain.objects.get(domain='acme.statuswatch.kontentwave.digital')
    print(f'acme.statuswatch.kontentwave.digital -> tenant: {domain.tenant.schema_name} ({domain.tenant.name})')
    print(f'  is_primary: {domain.is_primary}')
except Domain.DoesNotExist:
    print('acme.statuswatch.kontentwave.digital -> NOT FOUND')

# List all domains
print('\n--- ALL DOMAINS ---')
for d in Domain.objects.all():
    print(f'{d.domain} -> {d.tenant.schema_name} (primary: {d.is_primary})')
EOF
"

echo -e "\n=== 4. Check authentication endpoints in urls_public.py ==="
ssh -i ~/.ssh/discourse-poc-key.pem ubuntu@13.62.178.108 "cd /opt/statuswatch && docker compose exec -T web cat app/urls_public.py | grep -A 5 -B 5 'token'"

echo -e "\n=== 5. Check authentication endpoints in urls_tenant.py ==="
ssh -i ~/.ssh/discourse-poc-key.pem ubuntu@13.62.178.108 "cd /opt/statuswatch && docker compose exec -T web cat app/urls_tenant.py | grep -A 5 -B 5 'token'"

echo -e "\n=== 6. Test login API on public domain ==="
echo "Attempting login on public domain (should fail):"
curl -X POST https://statuswatch.kontentwave.digital/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email":"jwt@example.com","password":"TestPass123!"}' \
  -s | jq . 2>/dev/null || echo "Failed or no JSON response"

echo -e "\n=== 7. Test login API on acme subdomain ==="
echo "Attempting login on acme subdomain (should succeed):"
curl -X POST https://acme.statuswatch.kontentwave.digital/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email":"jwt@example.com","password":"TestPass123!"}' \
  -s | jq . 2>/dev/null || echo "Failed or no JSON response"

echo -e "\n=== 8. Check SHOW_PUBLIC_IF_NO_TENANT_FOUND setting ==="
ssh -i ~/.ssh/discourse-poc-key.pem ubuntu@13.62.178.108 "cd /opt/statuswatch && docker compose exec -T web python manage.py shell <<'EOF'
from django.conf import settings
print(f'SHOW_PUBLIC_IF_NO_TENANT_FOUND = {settings.SHOW_PUBLIC_IF_NO_TENANT_FOUND}')
print(f'PUBLIC_SCHEMA_URLCONF = {settings.PUBLIC_SCHEMA_URLCONF}')
print(f'ROOT_URLCONF = {settings.ROOT_URLCONF}')
EOF
"

echo -e "\n=== DONE ==="
