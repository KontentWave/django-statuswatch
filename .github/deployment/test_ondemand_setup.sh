#!/bin/bash
# Quick test of on-demand TLS setup
# Run from: /opt/statuswatch/

set -e

echo "🔍 Testing On-Demand TLS Setup"
echo ""

echo "1️⃣ Testing validation endpoint from Caddy container..."
docker compose exec caddy sh -c 'wget -qO- "http://web:8000/api/internal/validate-domain/?domain=acme.statuswatch.kontentwave.digital"'
echo ""

echo "2️⃣ Testing with non-existent domain (should fail)..."
docker compose exec caddy sh -c 'wget -qO- "http://web:8000/api/internal/validate-domain/?domain=fake.statuswatch.kontentwave.digital" 2>&1' || echo "✓ Correctly returned 404"
echo ""

echo "3️⃣ Checking Caddyfile for on_demand_tls config..."
if grep -q "on_demand_tls" /opt/statuswatch/caddy/Caddyfile; then
    echo "✓ on_demand_tls found in Caddyfile"
    grep -A3 "on_demand_tls" /opt/statuswatch/caddy/Caddyfile
else
    echo "✗ on_demand_tls NOT found in Caddyfile"
fi
echo ""

echo "4️⃣ Checking Caddyfile for wildcard domain..."
if grep -q '\*\.statuswatch\.kontentwave\.digital' /opt/statuswatch/caddy/Caddyfile; then
    echo "✓ Wildcard domain found in Caddyfile"
else
    echo "✗ Wildcard domain NOT found in Caddyfile"
fi
echo ""

echo "5️⃣ Testing HTTPS access to existing subdomain..."
curl -I https://acme.statuswatch.kontentwave.digital/ 2>&1 | head -1
echo ""

echo "✅ Basic tests complete!"
echo ""
echo "Next steps:"
echo "1. Update Caddyfile with on-demand TLS config"
echo "2. Reload Caddy: docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile"
echo "3. Create new tenant and test automatic cert generation"
