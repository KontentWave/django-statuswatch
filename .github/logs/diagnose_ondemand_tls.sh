#!/bin/bash
# On-Demand TLS Diagnostic for StatusWatch
# Run from: /opt/statuswatch/caddy/
# Purpose: Gather info needed to configure on-demand TLS for dynamic tenant subdomains

set -euo pipefail

echo "═══════════════════════════════════════════════════════════════"
echo "  ON-DEMAND TLS DIAGNOSTIC"
echo "  $(date)"
echo "═══════════════════════════════════════════════════════════════"

# ============================================================================
# SECTION 1: CURRENT CADDYFILE
# ============================================================================
echo ""
echo "━━━ 1. CURRENT CADDYFILE ━━━"
echo ""

cat /opt/statuswatch/caddy/Caddyfile

# ============================================================================
# SECTION 2: TENANT DOMAIN MODEL
# ============================================================================
echo ""
echo "━━━ 2. TENANT DOMAINS IN DATABASE ━━━"
echo ""

echo "All tenant domains currently configured:"
docker compose exec web python manage.py shell -c "
from tenants.models import Domain
for d in Domain.objects.select_related('tenant').all():
    print(f'{d.domain:40s} -> {d.tenant.schema_name:15s} (primary={d.is_primary})')
"

echo ""
echo "Count of tenants:"
docker compose exec web python manage.py shell -c "
from tenants.models import Client
print(f'Total tenants: {Client.objects.count()}')
"

# ============================================================================
# SECTION 3: DOMAIN VALIDATION ENDPOINT CHECK
# ============================================================================
echo ""
echo "━━━ 3. DOMAIN VALIDATION ENDPOINT ━━━"
echo ""

echo "Checking if validation endpoint exists in urls:"
docker compose exec web sh -c 'grep -r "on.demand\|domain.*valid\|tls.*ask" app/ api/ tenants/ 2>/dev/null || echo "(no existing endpoint found)"'

echo ""
echo "Testing if we can query domains from Django shell:"
docker compose exec web python manage.py shell -c "
from tenants.models import Domain
test_domains = ['acme.statuswatch.kontentwave.digital', 'nonexistent.statuswatch.kontentwave.digital']
for domain in test_domains:
    exists = Domain.objects.filter(domain=domain).exists()
    print(f'{domain:50s} -> {\"EXISTS\" if exists else \"NOT FOUND\"}')"

# ============================================================================
# SECTION 4: CURRENT URL CONFIGURATION
# ============================================================================
echo ""
echo "━━━ 4. URL CONFIGURATION ━━━"
echo ""

echo "Public URLs (urls_public.py):"
docker compose exec web sh -c 'cat app/urls_public.py'

echo ""
echo "Tenant URLs (urls_tenant.py):"
docker compose exec web sh -c 'cat app/urls_tenant.py | head -40'

# ============================================================================
# SECTION 5: API AUTHENTICATION
# ============================================================================
echo ""
echo "━━━ 5. API AUTHENTICATION FOR CADDY ━━━"
echo ""

echo "Checking if internal API authentication exists:"
docker compose exec web sh -c 'grep -r "INTERNAL_API_KEY\|CADDY_API_KEY\|VALIDATION_KEY" app/settings*.py .env 2>/dev/null || echo "(no internal API key found)"'

# ============================================================================
# SECTION 6: NETWORK CONNECTIVITY (Caddy → Django)
# ============================================================================
echo ""
echo "━━━ 6. CADDY TO DJANGO CONNECTIVITY ━━━"
echo ""

echo "Testing if Caddy can reach Django web service:"
docker compose exec caddy sh -c 'wget -qO- --timeout=5 http://web:8000/health/live/ 2>&1 || echo "Connection failed"'

echo ""
echo "Docker network inspection:"
docker compose exec caddy sh -c 'cat /etc/hosts | grep web'
docker compose exec caddy sh -c 'nslookup web 2>&1 | head -10 || getent hosts web'

# ============================================================================
# SECTION 7: CADDY GLOBAL OPTIONS
# ============================================================================
echo ""
echo "━━━ 7. CADDY GLOBAL OPTIONS ━━━"
echo ""

echo "Checking for existing global options in Caddyfile:"
head -20 /opt/statuswatch/caddy/Caddyfile | grep -E '^\{|on_demand_tls|email|acme_' || echo "(no global options block found)"

# ============================================================================
# SECTION 8: RATE LIMIT CONSIDERATIONS
# ============================================================================
echo ""
echo "━━━ 8. ON-DEMAND TLS RATE LIMITS ━━━"
echo ""

echo "Current tenant count:"
docker compose exec web python manage.py shell -c "
from tenants.models import Client
count = Client.objects.count()
print(f'Active tenants: {count}')
if count > 10:
    print('⚠️  WARNING: On-demand TLS is rate-limited by Let\\'s Encrypt')
    print('   Recommendation: Use staging during testing, then switch to production')
"

# ============================================================================
# SECTION 9: DJANGO SETTINGS CHECK
# ============================================================================
echo ""
echo "━━━ 9. DJANGO SETTINGS ━━━"
echo ""

echo "ALLOWED_HOSTS setting:"
docker compose exec web python manage.py shell -c "
from django.conf import settings
print('ALLOWED_HOSTS:', settings.ALLOWED_HOSTS)
print('DEBUG:', settings.DEBUG)
"

echo ""
echo "CSRF_TRUSTED_ORIGINS:"
docker compose exec web python manage.py shell -c "
from django.conf import settings
print('CSRF_TRUSTED_ORIGINS:', getattr(settings, 'CSRF_TRUSTED_ORIGINS', 'Not set'))
"

# ============================================================================
# SECTION 10: IMPLEMENTATION REQUIREMENTS
# ============================================================================
echo ""
echo "━━━ 10. IMPLEMENTATION PLAN ━━━"
echo ""

cat << 'EOF'
ON-DEMAND TLS REQUIREMENTS:

1. CREATE VALIDATION ENDPOINT IN DJANGO
   Path: /api/internal/validate-domain/
   Method: GET with ?domain=<subdomain>
   Response: HTTP 200 if domain exists in Domain model, 404 if not
   Authentication: Optional internal API key

2. MODIFY CADDYFILE
   Add global options block:
   {
       on_demand_tls {
           ask http://web:8000/api/internal/validate-domain
           interval 2m
           burst 5
       }
   }

   Change site block to:
   *.statuswatch.kontentwave.digital, statuswatch.kontentwave.digital {
       tls {
           on_demand
       }
       # ... rest of config
   }

3. SECURITY CONSIDERATIONS
   - Rate limiting (interval/burst in global options)
   - Optional: API key validation in Django endpoint
   - Monitor certificate usage to avoid Let's Encrypt limits

4. TESTING SEQUENCE
   - Create validation endpoint
   - Test endpoint: curl http://web:8000/api/internal/validate-domain?domain=acme.statuswatch.kontentwave.digital
   - Update Caddyfile with on_demand config
   - Reload Caddy
   - Create new tenant in Django admin
   - Access new tenant subdomain (triggers cert generation)
   - Verify in logs: "certificate obtained successfully"

EOF

# ============================================================================
# SECTION 11: SAMPLE IMPLEMENTATION CODE
# ============================================================================
echo ""
echo "━━━ 11. SAMPLE CODE PREVIEW ━━━"
echo ""

cat << 'EOF'
DJANGO VIEW (api/views.py):

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from tenants.models import Domain

@require_http_methods(["GET"])
def validate_domain_for_tls(request):
    """
    Endpoint for Caddy on-demand TLS validation.
    Returns 200 if domain exists, 404 if not.
    """
    domain = request.GET.get('domain', '').strip().lower()

    if not domain:
        return JsonResponse({'error': 'domain parameter required'}, status=400)

    # Optional: Check internal API key
    # api_key = request.headers.get('X-Internal-API-Key')
    # if api_key != settings.INTERNAL_API_KEY:
    #     return JsonResponse({'error': 'unauthorized'}, status=403)

    # Check if domain exists in tenant domains
    exists = Domain.objects.filter(domain=domain).exists()

    if exists:
        return JsonResponse({'domain': domain, 'valid': True}, status=200)
    else:
        return JsonResponse({'domain': domain, 'valid': False}, status=404)


URL PATTERN (app/urls_public.py):

from api.views import validate_domain_for_tls

urlpatterns = [
    # ... existing patterns
    path('api/internal/validate-domain/', validate_domain_for_tls, name='validate-domain-tls'),
]


CADDYFILE:

{
    on_demand_tls {
        ask http://web:8000/api/internal/validate-domain
        interval 2m
        burst 5
    }
    # acme_ca https://acme-staging-v02.api.letsencrypt.org/directory  # Use for testing
}

*.statuswatch.kontentwave.digital, statuswatch.kontentwave.digital {
    tls {
        on_demand
    }

    encode gzip

    # ... rest of your existing config
}

EOF

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  END OF DIAGNOSTIC - Ready to implement on-demand TLS"
echo "═══════════════════════════════════════════════════════════════"
