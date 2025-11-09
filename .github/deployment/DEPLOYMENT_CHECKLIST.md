# 🚀 On-Demand TLS Deployment Checklist

## ✅ Pre-Deployment Verification

- [x] Backend validation endpoint created (`validate_domain_for_tls`)
- [x] URL route added (`/api/internal/validate-domain/`)
- [x] New Caddyfile created with on-demand TLS config
- [x] Deployment documentation written

## 📋 Deployment Steps

### Step 1: Deploy Backend Code

```bash
# FROM LOCAL MACHINE
cd /home/marcel/projects/statuswatch-project

# Commit changes
git add backend/api/views.py backend/app/urls_public.py
git commit -m "feat: Add Caddy on-demand TLS domain validation endpoint"
git push origin main
```

### Step 2: Update EC2 Backend

```bash
# SSH TO EC2
ssh ubuntu@YOUR_EC2_IP

# Pull latest code
cd /opt/statuswatch/django-statuswatch
git pull origin main

# Restart Django
cd /opt/statuswatch
docker compose restart web

# Verify endpoint works
docker compose exec web python manage.py shell -c "
from django.test import Client
c = Client()
r = c.get('/api/internal/validate-domain/?domain=acme.statuswatch.kontentwave.digital')
print(f'Status: {r.status_code} - {r.json()}')
"
# ✅ Expected: Status: 200 - {'domain': 'acme.statuswatch.kontentwave.digital', 'valid': True}
```

### Step 3: Backup Current Caddyfile

```bash
# ON EC2
cd /opt/statuswatch/caddy
cp Caddyfile Caddyfile.backup.$(date +%Y%m%d_%H%M%S)
ls -la Caddyfile*
```

### Step 4: Update Caddyfile

```bash
# ON EC2
nano /opt/statuswatch/caddy/Caddyfile
```

**Paste this content:**

```caddyfile
{
    on_demand_tls {
        ask http://web:8000/api/internal/validate-domain
        interval 2m
        burst 5
    }
    # Keep staging during testing
    acme_ca https://acme-staging-v02.api.letsencrypt.org/directory
}

*.statuswatch.kontentwave.digital, statuswatch.kontentwave.digital {
    tls {
        on_demand
    }

    encode gzip
    log {
        output file /var/log/caddy/access.log
        format json
    }

    @api    path /api/*
    @admin  path /admin/*
    @health path /health/*

    handle @api {
        reverse_proxy web:8000
    }
    handle @admin {
        reverse_proxy web:8000
    }
    handle @health {
        reverse_proxy web:8000
    }

    @staticfiles path /static/*
    handle @staticfiles {
        reverse_proxy web:8000
    }

    handle {
        root * /srv/statuswatch-frontend/dist
        @static path / /index.html /assets/* /vite.svg /favicon.ico /manifest.webmanifest /robots.txt
        header @static {
            Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://api.stripe.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
            Referrer-Policy "same-origin"
            Permissions-Policy "geolocation=(), camera=(), microphone=(), payment=(), usb=(), magnetometer=(), accelerometer=(), gyroscope=()"
            Strict-Transport-Security "max-age=3600; includeSubDomains"
            X-Content-Type-Options "nosniff"
            X-Frame-Options "DENY"
        }
        @assets path /assets/*
        header @assets Cache-Control "public, max-age=31536000, immutable"
        try_files {path} /index.html
        file_server
    }
}
```

### Step 5: Validate and Reload Caddy

```bash
# ON EC2
cd /opt/statuswatch

# Format Caddyfile
docker compose exec caddy caddy fmt --overwrite /etc/caddy/Caddyfile

# Validate syntax
docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile

# Reload Caddy
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile

# Check for errors
docker compose logs caddy --tail 20
```

### Step 6: Test Existing Subdomain

```bash
# ON EC2
curl -I https://acme.statuswatch.kontentwave.digital/
# ✅ Expected: HTTP/2 200

# Check logs for cert generation
docker compose logs caddy --tail 50 | grep -i "acme.statuswatch"
```

### Step 7: Test New Tenant (Dynamic Cert Generation)

```bash
# ON EC2
# Create new tenant
docker compose exec web python manage.py shell -c "
from tenants.models import Client, Domain

tenant = Client.objects.create(
    schema_name='demo',
    name='Demo Client',
    paid_until='2025-12-31',
    on_trial=False
)

Domain.objects.create(
    domain='demo.statuswatch.kontentwave.digital',
    tenant=tenant,
    is_primary=True
)

print('✅ Created demo tenant with domain: demo.statuswatch.kontentwave.digital')
"

# IMPORTANT: Create DNS A record for demo.statuswatch.kontentwave.digital
# pointing to your EC2 IP before testing

# Wait for DNS propagation
sleep 30

# Access new subdomain (triggers cert generation)
curl -I https://demo.statuswatch.kontentwave.digital/

# Watch logs for on-demand TLS activity
docker compose logs caddy -f | grep -E "demo|obtaining certificate"
```

### Step 8: Monitor TLS Validation Logs

```bash
# Terminal 1: Watch Django validation logs
docker compose logs web -f | grep validate-domain

# Terminal 2: Watch Caddy cert generation
docker compose logs caddy -f | grep -i "certificate\|tls"
```

## 🎯 Success Criteria

- ✅ Validation endpoint returns 200 for existing domains
- ✅ Validation endpoint returns 404 for non-existent domains
- ✅ Existing subdomains (acme) continue to work
- ✅ New tenant subdomains automatically get SSL certificates
- ✅ No errors in Caddy logs
- ✅ Django logs show TLS validation requests

## 🔄 Switch to Production Certs (After Testing)

```bash
# Edit Caddyfile
nano /opt/statuswatch/caddy/Caddyfile

# Remove or comment out:
# acme_ca https://acme-staging-v02.api.letsencrypt.org/directory

# Delete staging certs
docker compose exec caddy sh -c 'rm -rf /data/caddy/certificates/acme-staging*'

# Reload
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile

# Verify real cert
curl -vI https://acme.statuswatch.kontentwave.digital/ 2>&1 | grep "issuer:"
# ✅ Should show: issuer: C=US; O=Let's Encrypt; CN=R3
```

## 🚨 Rollback Plan

```bash
# Restore old Caddyfile
cp /opt/statuswatch/caddy/Caddyfile.backup.YYYYMMDD_HHMMSS /opt/statuswatch/caddy/Caddyfile

# Reload
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

## 📊 Monitoring

- Check cert count: `docker compose exec caddy sh -c 'ls -la /data/caddy/certificates/'`
- Monitor rate limits: https://crt.sh/?q=%.statuswatch.kontentwave.digital
- Django logs: `/app/logs/django.log` (TLS validation events)
- Caddy logs: `docker compose logs caddy -f`
