#!/bin/bash
# Test HTTP access to internal endpoints after middleware fix
# Run from: /opt/statuswatch/

set -e

echo "🧪 Testing HTTP Access to Internal Endpoints"
echo ""

echo "1️⃣ Testing validation endpoint (should return 200, no redirect)..."
docker compose exec caddy sh -c 'wget -S -O- "http://web:8000/api/internal/validate-domain/?domain=acme.statuswatch.kontentwave.digital" 2>&1' | head -20
echo ""

echo "2️⃣ Testing with non-existent domain (should return 404, no redirect)..."
docker compose exec caddy sh -c 'wget -S -O- "http://web:8000/api/internal/validate-domain/?domain=fake.statuswatch.kontentwave.digital" 2>&1 | head -15' || echo "(Expected 404)"
echo ""

echo "3️⃣ Testing health endpoint (should return 200, no redirect)..."
docker compose exec caddy sh -c 'wget -S -O- "http://web:8000/health/" 2>&1 | head -15'
echo ""

echo "4️⃣ Testing regular endpoint (should still redirect to HTTPS)..."
docker compose exec caddy sh -c 'wget -S -O- "http://web:8000/api/ping/" 2>&1 | head -15' || echo "(Expected 301 redirect)"
echo ""

echo "✅ Tests complete!"
echo ""
echo "Expected results:"
echo "  • /api/internal/validate-domain/ → 200 OK (JSON response)"
echo "  • /health/ → 200 OK (JSON response)"
echo "  • /api/ping/ → 301 Redirect to HTTPS (security still enforced)"
