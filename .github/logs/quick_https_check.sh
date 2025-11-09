#!/bin/bash
# Quick HTTPS troubleshooting commands

echo "Quick HTTPS Checks"
echo "=================="
echo ""

# 1. Is Caddy running and healthy?
echo "1. Caddy status:"
docker ps | grep caddy
echo ""

# 2. Caddy logs (errors)
echo "2. Recent Caddy errors:"
docker logs --tail 30 statuswatch-caddy-1 2>&1 | grep -i error || echo "No errors found"
echo ""

# 3. What's the Caddy config?
echo "3. Caddy configuration file:"
docker exec statuswatch-caddy-1 cat /etc/caddy/Caddyfile 2>/dev/null || echo "No Caddyfile found"
echo ""

# 4. Test HTTP (should work or redirect)
echo "4. Testing HTTP to Caddy:"
curl -I -H "Host: acme.statuswatch.kontentwave.digital" http://127.0.0.1/ 2>&1
echo ""

# 5. Test HTTPS
echo "5. Testing HTTPS to Caddy:"
curl -Ik https://127.0.0.1/ 2>&1 | head -20
echo ""

# 6. What's listening on 443?
echo "6. Port 443 listener:"
sudo ss -tlnp | grep :443 || sudo netstat -tlnp | grep :443 || echo "Cannot check"
echo ""

# 7. Can we reach web directly?
echo "7. Django (web) container direct test:"
docker exec statuswatch-web-1 curl -s -H "Host: acme.statuswatch.kontentwave.digital" http://127.0.0.1:8000/api/ping/ 2>&1
echo ""

# 8. ALLOWED_HOSTS setting
echo "8. Current ALLOWED_HOSTS:"
docker exec statuswatch-web-1 python -c "
import django; django.setup()
from django.conf import settings
print(settings.ALLOWED_HOSTS)
" 2>&1 | tail -1
