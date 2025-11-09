#!/bin/bash
# Diagnose HTTP redirect issue for on-demand TLS validation
# Run from: /opt/statuswatch/

set -euo pipefail

echo "═══════════════════════════════════════════════════════════════"
echo "  HTTP REDIRECT DIAGNOSTIC FOR ON-DEMAND TLS"
echo "  $(date)"
echo "═══════════════════════════════════════════════════════════════"

# ============================================================================
# SECTION 1: CHECK DJANGO HTTPS REDIRECT SETTINGS
# ============================================================================
echo ""
echo "━━━ 1. DJANGO HTTPS SETTINGS ━━━"
echo ""

echo "Checking SECURE_SSL_REDIRECT setting:"
docker compose exec web python manage.py shell -c "
from django.conf import settings
print(f'SECURE_SSL_REDIRECT: {settings.SECURE_SSL_REDIRECT}')
print(f'DEBUG: {settings.DEBUG}')
print(f'DJANGO_ENV: {getattr(settings, \"DJANGO_ENV\", \"not set\")}')
"

# ============================================================================
# SECTION 2: CHECK MIDDLEWARE
# ============================================================================
echo ""
echo "━━━ 2. MIDDLEWARE CONFIGURATION ━━━"
echo ""

echo "Checking for SecurityMiddleware:"
docker compose exec web python manage.py shell -c "
from django.conf import settings
middleware = settings.MIDDLEWARE
for i, m in enumerate(middleware):
    if 'Security' in m:
        print(f'{i}: {m} ⚠️')
    else:
        print(f'{i}: {m}')
"

# ============================================================================
# SECTION 3: TEST DIRECT HTTP ACCESS
# ============================================================================
echo ""
echo "━━━ 3. DIRECT HTTP TEST ━━━"
echo ""

echo "Testing HTTP access from Caddy container (should NOT redirect):"
docker compose exec caddy sh -c 'wget -S -O- --max-redirect=0 "http://web:8000/health/" 2>&1 | head -20'

# ============================================================================
# SECTION 4: TEST VALIDATION ENDPOINT
# ============================================================================
echo ""
echo "━━━ 4. VALIDATION ENDPOINT HTTP TEST ━━━"
echo ""

echo "Testing validation endpoint with max-redirect=0:"
docker compose exec caddy sh -c 'wget -S -O- --max-redirect=0 "http://web:8000/api/internal/validate-domain/?domain=acme.statuswatch.kontentwave.digital" 2>&1 | head -30' || echo "(redirect detected)"

# ============================================================================
# SECTION 5: CHECK URL ROUTING
# ============================================================================
echo ""
echo "━━━ 5. URL ROUTING CHECK ━━━"
echo ""

echo "Verifying validation endpoint is registered:"
docker compose exec web python manage.py shell -c "
from django.urls import get_resolver
resolver = get_resolver()
try:
    match = resolver.resolve('/api/internal/validate-domain/')
    print(f'✓ URL matches: {match.func.__name__}')
    print(f'  View: {match.func}')
except Exception as e:
    print(f'✗ URL not found: {e}')
"

# ============================================================================
# SECTION 6: TEST ENDPOINT DIRECTLY IN DJANGO
# ============================================================================
echo ""
echo "━━━ 6. DJANGO TEST CLIENT (bypasses middleware) ━━━"
echo ""

echo "Testing endpoint via Django test client:"
docker compose exec web python manage.py shell -c "
from django.test import Client
c = Client()
print('Test 1: Valid domain')
r = c.get('/api/internal/validate-domain/?domain=acme.statuswatch.kontentwave.digital')
print(f'  Status: {r.status_code}')
print(f'  Response: {r.json() if r.status_code == 200 else r.content}')

print()
print('Test 2: Invalid domain')
r = c.get('/api/internal/validate-domain/?domain=fake.statuswatch.kontentwave.digital')
print(f'  Status: {r.status_code}')
print(f'  Response: {r.json() if hasattr(r, \"json\") else r.content}')
"

# ============================================================================
# SECTION 7: SETTINGS FILE INSPECTION
# ============================================================================
echo ""
echo "━━━ 7. PRODUCTION SETTINGS FILE ━━━"
echo ""

echo "Checking settings_production.py for HTTPS redirects:"
docker compose exec web sh -c 'grep -n "SECURE_SSL_REDIRECT\|SECURE_PROXY_SSL\|SECURE_HSTS" app/settings_production.py || echo "(not found)"'

# ============================================================================
# SECTION 8: ENVIRONMENT VARIABLES
# ============================================================================
echo ""
echo "━━━ 8. ENVIRONMENT VARIABLES ━━━"
echo ""

echo "Checking for HTTPS-related env vars:"
docker compose exec web sh -c 'env | grep -E "HTTPS|SSL|SECURE" | sort || echo "(none found)"'

# ============================================================================
# SECTION 9: SOLUTION SUMMARY
# ============================================================================
echo ""
echo "━━━ 9. SOLUTION OPTIONS ━━━"
echo ""

cat << 'EOF'
PROBLEM: Django redirects HTTP → HTTPS in production, breaking Caddy's on-demand TLS

SOLUTION OPTIONS:

A) EXEMPT VALIDATION ENDPOINT FROM HTTPS REDIRECT (Recommended)
   - Add custom middleware to allow HTTP for /api/internal/validate-domain/
   - Keeps HTTPS enforcement for all other endpoints
   - Most secure and flexible

B) DISABLE SECURE_SSL_REDIRECT GLOBALLY
   - Set SECURE_SSL_REDIRECT = False in settings
   - Caddy handles HTTPS redirect instead
   - Simpler but less Django-native

C) USE CUSTOM DECORATOR ON VIEW
   - Use @csrf_exempt + custom decorator to allow HTTP
   - Only affects this specific view
   - Clean but requires middleware changes

RECOMMENDATION: Option A (custom middleware to exempt internal endpoints)

EOF

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  END OF DIAGNOSTIC"
echo "═══════════════════════════════════════════════════════════════"
