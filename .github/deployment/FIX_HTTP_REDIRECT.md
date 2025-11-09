# 🔧 Fix HTTP Redirect for On-Demand TLS

## Problem

Django's `SECURE_SSL_REDIRECT=True` redirects all HTTP requests to HTTPS, breaking Caddy's on-demand TLS validation which requires HTTP access to `/api/internal/validate-domain/`.

## Solution

Custom middleware that exempts internal endpoints from HTTPS redirect while maintaining security for all other routes.

## Files Created/Modified

1. ✅ `backend/app/middleware_internal.py` - Marks internal endpoints to skip HTTPS redirect
2. ✅ `backend/app/middleware_security_custom.py` - Custom SecurityMiddleware respecting skip flag
3. ✅ `backend/app/settings_base.py` - Updated MIDDLEWARE order
4. ✅ `.github/deployment/test_http_access.sh` - Test script

## Deployment Steps

### Step 1: Commit and Push Changes

```bash
# FROM LOCAL MACHINE
cd /home/marcel/projects/statuswatch-project

git add backend/app/middleware_internal.py \
        backend/app/middleware_security_custom.py \
        backend/app/settings_base.py \
        .github/deployment/test_http_access.sh

git commit -m "fix: Allow HTTP access to internal endpoints for Caddy on-demand TLS

- Add InternalEndpointMiddleware to exempt /api/internal/validate-domain/
- Replace SecurityMiddleware with CustomSecurityMiddleware
- Maintain HTTPS redirect for all non-internal endpoints
- Fixes on-demand TLS validation blocking"

git push origin main
```

### Step 2: Deploy to EC2

```bash
# SSH TO EC2
ssh ubuntu@YOUR_EC2_IP

# Pull latest code
cd /opt/statuswatch/django-statuswatch
git pull origin main

# Restart Django to load new middleware
cd /opt/statuswatch
docker compose restart web

# Wait for container to be ready
sleep 5
```

### Step 3: Test HTTP Access

```bash
# ON EC2
cd /opt/statuswatch

# Test validation endpoint (should work without redirect)
docker compose exec caddy sh -c 'wget -S -O- "http://web:8000/api/internal/validate-domain/?domain=acme.statuswatch.kontentwave.digital" 2>&1 | head -20'

# Expected output:
#   HTTP/1.1 200 OK
#   Content-Type: application/json
#   {"domain":"acme.statuswatch.kontentwave.digital","valid":true}

# Test non-existent domain (should return 404)
docker compose exec caddy sh -c 'wget -S -O- "http://web:8000/api/internal/validate-domain/?domain=fake.statuswatch.kontentwave.digital" 2>&1 | head -15'

# Expected output:
#   HTTP/1.1 404 Not Found
#   {"domain":"fake.statuswatch.kontentwave.digital","valid":false}
```

### Step 4: Verify HTTPS Still Enforced for Other Endpoints

```bash
# ON EC2

# Regular API endpoints should still redirect to HTTPS
docker compose exec caddy sh -c 'wget -S -O- "http://web:8000/api/ping/" 2>&1 | head -15'

# Expected output:
#   HTTP/1.1 301 Moved Permanently
#   Location: https://web:8000/api/ping/
```

### Step 5: Run Full Test Suite

```bash
# ON EC2
cd /opt/statuswatch
bash django-statuswatch/.github/deployment/test_http_access.sh
```

## Security Notes

✅ **HTTPS still enforced** for all public endpoints
✅ **Only internal endpoints** exempted: `/api/internal/validate-domain/`, `/health/`, `/healthz`
✅ **Middleware ordering critical**: InternalEndpointMiddleware must be FIRST
✅ **No exposure risk**: Internal endpoints only accessible from Docker network

## Troubleshooting

### Still getting 301 redirect

```bash
# Check middleware order
docker compose exec web python manage.py shell -c "
from django.conf import settings
for i, m in enumerate(settings.MIDDLEWARE[:5]):
    print(f'{i}: {m}')
"

# Expected order:
# 0: app.middleware_internal.InternalEndpointMiddleware
# 1: app.middleware_security_custom.CustomSecurityMiddleware
```

### Endpoint returns 400 Bad Request

```bash
# Check ALLOWED_HOSTS includes the internal hostname
docker compose exec web python manage.py shell -c "
from django.conf import settings
print(settings.ALLOWED_HOSTS)
"

# Should include: ['127.0.0.1', 'localhost', 'web', ...]
```

### Verify middleware is loaded

```bash
docker compose exec web python manage.py shell -c "
from app.middleware_internal import InternalEndpointMiddleware
from app.middleware_security_custom import CustomSecurityMiddleware
print('✓ Middleware classes imported successfully')
"
```

## Next Steps

After verification:

1. ✅ HTTP access works for validation endpoint
2. ✅ HTTPS redirect still enforced for public endpoints
3. → Proceed with Caddyfile update for on-demand TLS
4. → Follow `DEPLOYMENT_CHECKLIST.md` to complete on-demand TLS setup
