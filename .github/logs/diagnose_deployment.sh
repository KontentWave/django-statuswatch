#!/bin/bash
# Diagnose why validation endpoint is not accessible
# Run from: /opt/statuswatch/

set -euo pipefail

echo "═══════════════════════════════════════════════════════════════"
echo "  VALIDATION ENDPOINT DIAGNOSTIC"
echo "  $(date)"
echo "═══════════════════════════════════════════════════════════════"

# ============================================================================
# SECTION 1: CHECK IF CODE IS DEPLOYED
# ============================================================================
echo ""
echo "━━━ 1. CHECK IF MIDDLEWARE FILES EXIST ━━━"
echo ""

echo "Checking for middleware_internal.py in container:"
docker compose exec web sh -c 'ls -lah app/middleware_internal.py 2>&1'
echo ""

echo "Checking for middleware_security_custom.py in container:"
docker compose exec web sh -c 'ls -lah app/middleware_security_custom.py 2>&1'
echo ""

# ============================================================================
# SECTION 2: CHECK IF VIEW EXISTS
# ============================================================================
echo ""
echo "━━━ 2. CHECK IF VALIDATION VIEW EXISTS ━━━"
echo ""

echo "Checking for validate_domain_for_tls in views.py:"
docker compose exec web sh -c 'grep -n "validate_domain_for_tls" api/views.py | head -5 || echo "NOT FOUND"'
echo ""

# ============================================================================
# SECTION 3: CHECK URL REGISTRATION
# ============================================================================
echo ""
echo "━━━ 3. CHECK URL REGISTRATION ━━━"
echo ""

echo "Checking urls_public.py for validation endpoint:"
docker compose exec web sh -c 'grep -n "validate-domain" app/urls_public.py || echo "NOT FOUND"'
echo ""

echo "Checking imports in urls_public.py:"
docker compose exec web sh -c 'grep -n "validate_domain_for_tls" app/urls_public.py || echo "NOT FOUND"'
echo ""

# ============================================================================
# SECTION 4: TEST URL RESOLUTION
# ============================================================================
echo ""
echo "━━━ 4. TEST URL RESOLUTION IN DJANGO ━━━"
echo ""

echo "Checking if URL resolves:"
docker compose exec web python manage.py shell -c "
from django.urls import get_resolver
try:
    match = get_resolver().resolve('/api/internal/validate-domain/')
    print('✓ URL resolves to:', match.func.__name__)
except Exception as e:
    print('✗ URL resolution failed:', e)
"
echo ""

# ============================================================================
# SECTION 5: CHECK GIT REPO STATUS
# ============================================================================
echo ""
echo "━━━ 5. CHECK GIT REPO STATUS ━━━"
echo ""

echo "Current commit in git repo:"
cd /opt/statuswatch/django-statuswatch
git log -1 --oneline
echo ""

echo "Checking for uncommitted changes:"
git status --short
echo ""

# ============================================================================
# SECTION 6: CHECK CONTAINER IMAGE
# ============================================================================
echo ""
echo "━━━ 6. CHECK CONTAINER IMAGE ━━━"
echo ""

echo "Web container image:"
docker compose ps web --format json | grep -o '"Image":"[^"]*"' || docker compose ps web
echo ""

echo "When was the image built?"
docker inspect $(docker compose ps -q web) --format '{{.Created}}' 2>/dev/null || echo "Cannot inspect"
echo ""

# ============================================================================
# SECTION 7: CHECK IF RESTART IS NEEDED
# ============================================================================
echo ""
echo "━━━ 7. CHECK CONTAINER UPTIME ━━━"
echo ""

echo "Container started at:"
docker inspect $(docker compose ps -q web) --format '{{.State.StartedAt}}' 2>/dev/null || echo "Cannot inspect"
echo ""

# ============================================================================
# SECTION 8: SOLUTION
# ============================================================================
echo ""
echo "━━━ 8. LIKELY SOLUTIONS ━━━"
echo ""

cat << 'EOF'
IF middleware files don't exist in container:
  → Code not deployed. Need to rebuild or redeploy container

IF view doesn't exist in api/views.py:
  → Git repo not updated. Run: cd /opt/statuswatch/django-statuswatch && git pull

IF URL not registered:
  → urls_public.py not updated. Run git pull

IF container is old:
  → Restart needed: docker compose restart web

DEPLOYMENT STEPS:
1. cd /opt/statuswatch/django-statuswatch
2. git pull origin main
3. cd /opt/statuswatch
4. docker compose restart web
5. Wait 10 seconds
6. Test: docker compose exec web python manage.py shell -c "from api.views import validate_domain_for_tls; print('OK')"

EOF

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  END OF DIAGNOSTIC"
echo "═══════════════════════════════════════════════════════════════"
