#!/bin/bash
# Final diagnostic for validation endpoint
# Run from: /opt/statuswatch/

set -euo pipefail

echo "═══════════════════════════════════════════════════════════════"
echo "  VALIDATION ENDPOINT FINAL DIAGNOSTIC"
echo "  $(date)"
echo "═══════════════════════════════════════════════════════════════"

# ============================================================================
# SECTION 1: CHECK MIDDLEWARE ORDER
# ============================================================================
echo ""
echo "━━━ 1. MIDDLEWARE ORDER ━━━"
echo ""

docker compose exec web python manage.py shell -c "
from django.conf import settings
print('First 5 middleware:')
for i, m in enumerate(settings.MIDDLEWARE[:5]):
    print(f'  {i}: {m}')
"

# ============================================================================
# SECTION 2: TEST ENDPOINT WITH PROPER HEADERS
# ============================================================================
echo ""
echo "━━━ 2. TEST WITH X-Forwarded-Proto HEADER ━━━"
echo ""

echo "Testing from within web container with proper headers:"
docker compose exec web python -c "
import django
django.setup()

from django.test import Client
from django.test.utils import override_settings

# Test without HOST header issues
c = Client(HTTP_HOST='web:8000')

print('Test 1: With X-Forwarded-Proto: https')
response = c.get(
    '/api/internal/validate-domain/?domain=acme.statuswatch.kontentwave.digital',
    HTTP_X_FORWARDED_PROTO='https'
)
print(f'  Status: {response.status_code}')
if response.status_code == 200:
    print(f'  Body: {response.content.decode()}')
else:
    print(f'  Body: {response.content.decode()[:500]}')

print()
print('Test 2: Direct HTTP (should not redirect for internal endpoint)')
response = c.get('/api/internal/validate-domain/?domain=acme.statuswatch.kontentwave.digital')
print(f'  Status: {response.status_code}')
if response.status_code in [200, 404]:
    print(f'  Body: {response.content.decode()[:500]}')
elif response.status_code == 301:
    print(f'  ⚠️  Still redirecting! Location: {response.get(\"Location\", \"N/A\")}')
else:
    print(f'  Body: {response.content.decode()[:500]}')
"

# ============================================================================
# SECTION 3: CHECK ALLOWED_HOSTS
# ============================================================================
echo ""
echo "━━━ 3. ALLOWED_HOSTS CHECK ━━━"
echo ""

docker compose exec web python manage.py shell -c "
from django.conf import settings
print('ALLOWED_HOSTS:', settings.ALLOWED_HOSTS)
print()
print('Should include: web, localhost, 127.0.0.1 for internal requests')
"

# ============================================================================
# SECTION 4: TEST FROM CADDY CONTAINER
# ============================================================================
echo ""
echo "━━━ 4. TEST FROM CADDY CONTAINER ━━━"
echo ""

echo "Attempt 1: Plain HTTP"
docker compose exec caddy sh -c 'wget -S -O- "http://web:8000/api/internal/validate-domain/?domain=acme.statuswatch.kontentwave.digital" 2>&1 | head -20' || echo "(failed)"

echo ""
echo "Attempt 2: With Host header"
docker compose exec caddy sh -c 'wget -S -O- --header="Host: web" "http://web:8000/api/internal/validate-domain/?domain=acme.statuswatch.kontentwave.digital" 2>&1 | head -20' || echo "(failed)"

# ============================================================================
# SECTION 5: CHECK TENANT ROUTING
# ============================================================================
echo ""
echo "━━━ 5. TENANT ROUTING CHECK ━━━"
echo ""

docker compose exec web python manage.py shell -c "
from django_tenants.utils import get_public_schema_name
from django.conf import settings

print('PUBLIC_SCHEMA_NAME:', get_public_schema_name())
print('PUBLIC_SCHEMA_URLCONF:', settings.PUBLIC_SCHEMA_URLCONF)
print('ROOT_URLCONF (tenant):', settings.ROOT_URLCONF)
"

# ============================================================================
# SECTION 6: CHECK IF INTERNAL ENDPOINT IS EXEMPT
# ============================================================================
echo ""
echo "━━━ 6. TEST INTERNAL ENDPOINT MIDDLEWARE ━━━"
echo ""

docker compose exec web python -c "
import django
django.setup()

from app.middleware_internal import InternalEndpointMiddleware

middleware = InternalEndpointMiddleware(lambda r: None)

test_paths = [
    '/api/internal/validate-domain/',
    '/health/',
    '/healthz',
    '/api/ping/',
]

for path in test_paths:
    is_internal = middleware._is_internal_endpoint(path)
    print(f'{path:50s} -> {\"EXEMPT\" if is_internal else \"HTTPS ENFORCED\"}')"

# ============================================================================
# SECTION 7: CHECK ACTUAL HTTP REQUEST
# ============================================================================
echo ""
echo "━━━ 7. SIMULATE ACTUAL CADDY REQUEST ━━━"
echo ""

docker compose exec web python -c "
import django
django.setup()

from django.test import RequestFactory
from django.urls import get_resolver

# Create request factory
factory = RequestFactory()

# Simulate Caddy's request
request = factory.get(
    '/api/internal/validate-domain/',
    {'domain': 'acme.statuswatch.kontentwave.digital'},
    HTTP_HOST='web:8000',
)

print('Request created:')
print(f'  Path: {request.path}')
print(f'  GET params: {dict(request.GET)}')
print(f'  Host header: {request.META.get(\"HTTP_HOST\")}')

# Try to resolve
try:
    match = get_resolver().resolve(request.path)
    print(f'  ✓ Resolves to: {match.func.__name__}')

    # Try calling the view
    try:
        response = match.func(request)
        print(f'  ✓ View called successfully')
        print(f'  Status: {response.status_code}')
        print(f'  Content: {response.content.decode()[:200]}')
    except Exception as e:
        print(f'  ✗ View execution failed: {e}')
except Exception as e:
    print(f'  ✗ Resolution failed: {e}')
"

# ============================================================================
# SECTION 8: SOLUTION
# ============================================================================
echo ""
echo "━━━ 8. LIKELY ISSUES ━━━"
echo ""

cat << 'EOF'
IF middleware still redirects:
  → InternalEndpointMiddleware not working
  → Check: Is it first in MIDDLEWARE list?
  → Check: Does _is_internal_endpoint() match the path?

IF 404 despite URL resolving:
  → ALLOWED_HOSTS blocking the request
  → Add 'web' to ALLOWED_HOSTS in .env

IF health endpoint redirects:
  → /health/ needs to be in HTTP_ALLOWED_PATHS
  → Update InternalEndpointMiddleware

QUICK FIX: Add to .env
  ALLOWED_HOSTS=127.0.0.1,localhost,web,statuswatch.kontentwave.digital,.statuswatch.kontentwave.digital

EOF

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  END OF DIAGNOSTIC"
echo "═══════════════════════════════════════════════════════════════"
