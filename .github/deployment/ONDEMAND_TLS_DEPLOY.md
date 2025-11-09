# On-Demand TLS Deployment for StatusWatch

## What This Does

Enables Caddy to automatically generate SSL certificates for new tenant subdomains without manual configuration.

## Files Modified

1. `backend/api/views.py` - Added `validate_domain_for_tls()` endpoint
2. `backend/app/urls_public.py` - Added route `/api/internal/validate-domain/`
3. `.github/deployment/Caddyfile.ondemand` - New Caddyfile with on-demand TLS

## Deployment Steps

### 1. Deploy Backend Changes (from local)

```bash
# Commit and push changes
cd /home/marcel/projects/statuswatch-project
git add backend/api/views.py backend/app/urls_public.py
git commit -m "feat: Add Caddy on-demand TLS domain validation endpoint"
git push origin main
```

### 2. Pull and Restart Backend on EC2

```bash
# SSH to EC2
ssh ubuntu@ec2-13-62-178-108.eu-north-1.compute.amazonaws.com

# Navigate to git repo
cd /opt/statuswatch/django-statuswatch
git pull origin main

# Restart Django
cd /opt/statuswatch
docker compose restart web

# Wait 5 seconds
sleep 5

# Verify endpoint works
docker compose exec web python manage.py shell -c "
from django.test import Client
c = Client()
response = c.get('/api/internal/validate-domain/?domain=acme.statuswatch.kontentwave.digital')
print(f'Status: {response.status_code}')
print(f'Response: {response.json()}')
"
# Expected: Status: 200, Response: {'domain': 'acme.statuswatch.kontentwave.digital', 'valid': True}
```

### 3. Test Validation Endpoint from Caddy

```bash
# From EC2
cd /opt/statuswatch

# Test with existing domain (should return 200)
docker compose exec caddy sh -c 'wget -qO- "http://web:8000/api/internal/validate-domain/?domain=acme.statuswatch.kontentwave.digital"'
# Expected: {"domain":"acme.statuswatch.kontentwave.digital","valid":true}

# Test with non-existent domain (should return 404)
docker compose exec caddy sh -c 'wget -qO- "http://web:8000/api/internal/validate-domain/?domain=fake.statuswatch.kontentwave.digital" 2>&1 || echo "404 as expected"'
# Expected: 404 error
```

### 4. Update Caddyfile on EC2

```bash
# Backup current Caddyfile
cp /opt/statuswatch/caddy/Caddyfile /opt/statuswatch/caddy/Caddyfile.backup.$(date +%Y%m%d_%H%M%S)

# Copy new Caddyfile from your local repo
# (You'll need to SCP or manually copy the content)
```

**OPTION A: Manual copy (recommended)**

```bash
# On EC2, edit Caddyfile
nano /opt/statuswatch/caddy/Caddyfile

# Paste the content from .github/deployment/Caddyfile.ondemand
# Save with Ctrl+X, Y, Enter
```

**OPTION B: SCP from local**

```bash
# From your local machine
scp /home/marcel/projects/statuswatch-project/.github/deployment/Caddyfile.ondemand \
    ubuntu@ec2-13-62-178-108.eu-north-1.compute.amazonaws.com:/tmp/Caddyfile.new

# Then on EC2
sudo mv /tmp/Caddyfile.new /opt/statuswatch/caddy/Caddyfile
```

### 5. Validate and Reload Caddy

```bash
# On EC2
cd /opt/statuswatch

# Validate new Caddyfile syntax
docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile

# Format the Caddyfile (fixes warnings)
docker compose exec caddy caddy fmt --overwrite /etc/caddy/Caddyfile

# Reload Caddy configuration
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

### 6. Test On-Demand TLS

#### Test 1: Access existing tenant subdomain

```bash
# Should work immediately (cert already exists or gets generated)
curl -I https://acme.statuswatch.kontentwave.digital/
# Expected: HTTP/2 200
```

#### Test 2: Create new tenant and test automatic cert

```bash
# Create new tenant via Django admin or shell
docker compose exec web python manage.py shell -c "
from tenants.models import Client, Domain

# Create new tenant
tenant = Client.objects.create(
    schema_name='testclient',
    name='Test Client',
    paid_until='2025-12-31',
    on_trial=False
)

# Create domain for new tenant
Domain.objects.create(
    domain='testclient.statuswatch.kontentwave.digital',
    tenant=tenant,
    is_primary=True
)

print(f'Created tenant: {tenant.schema_name}')
print(f'Domain: testclient.statuswatch.kontentwave.digital')
"

# Wait 10 seconds for DNS (if A record exists)
sleep 10

# Access new subdomain - should trigger on-demand cert generation
curl -I https://testclient.statuswatch.kontentwave.digital/

# Check Caddy logs for cert generation
docker compose logs caddy --tail 50 | grep -i "testclient\|certificate"
```

### 7. Monitor On-Demand TLS Activity

```bash
# Watch for domain validation requests
docker compose logs web -f | grep validate-domain

# Watch for certificate generation
docker compose logs caddy -f | grep -E "obtaining certificate|certificate obtained"

# Check Django logs for TLS validation
docker compose exec web tail -f /app/logs/django.log | grep TLS
```

### 8. Switch to Production Certificates (when ready)

```bash
# Edit Caddyfile
nano /opt/statuswatch/caddy/Caddyfile

# Comment out or remove this line:
# acme_ca https://acme-staging-v02.api.letsencrypt.org/directory

# Delete staging certificates
docker compose exec caddy sh -c 'rm -rf /data/caddy/certificates/acme-staging*'

# Reload Caddy
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile

# Test - should get real Let's Encrypt cert
curl -vI https://acme.statuswatch.kontentwave.digital/ 2>&1 | grep "issuer:"
# Expected: issuer: C=US; O=Let's Encrypt; CN=R3 (not Staging)
```

## Security Notes

1. **Rate Limiting**: Configured with `interval 2m` and `burst 5`

   - Max 5 cert requests in 2 minutes
   - Protects against abuse

2. **Domain Validation**: Only domains in `tenants.models.Domain` get certificates

   - Prevents random subdomains from getting certs

3. **Let's Encrypt Limits**:

   - **50 certificates per week** per registered domain
   - Use staging during testing!
   - Monitor your usage: https://crt.sh/?q=%.statuswatch.kontentwave.digital

4. **Logging**: All validation requests are logged in Django logs
   - Success: INFO level
   - Rejected: WARNING level

## Troubleshooting

### Certificate generation fails

```bash
# Check Caddy logs
docker compose logs caddy --tail 100 | grep -i error

# Common issues:
# 1. DNS not pointing to server
# 2. Port 80/443 blocked
# 3. Let's Encrypt rate limit hit
```

### Domain validation returns 404

```bash
# Verify domain exists in database
docker compose exec web python manage.py shell -c "
from tenants.models import Domain
print(Domain.objects.filter(domain='YOURDOMAIN.statuswatch.kontentwave.digital').exists())
"
```

### Too many certificate requests

```bash
# Increase interval in Caddyfile global options
on_demand_tls {
    interval 5m  # Increase from 2m to 5m
    burst 3      # Decrease from 5 to 3
}
```

## Rollback

```bash
# Restore backup Caddyfile
cp /opt/statuswatch/caddy/Caddyfile.backup.YYYYMMDD_HHMMSS /opt/statuswatch/caddy/Caddyfile

# Reload
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```
