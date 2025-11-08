#!/bin/bash
# Wildcard SSL Certificate Diagnostic for StatusWatch
# Run from: /opt/statuswatch/caddy/
# Purpose: Diagnose wildcard cert issues and DNS configuration

set -euo pipefail

echo "═══════════════════════════════════════════════════════════════"
echo "  WILDCARD SSL CERTIFICATE DIAGNOSTIC"
echo "  $(date)"
echo "═══════════════════════════════════════════════════════════════"

# ============================================================================
# SECTION 1: DNS VERIFICATION
# ============================================================================
echo ""
echo "━━━ 1. DNS VERIFICATION ━━━"
echo ""

echo "Checking A records for all domains:"
for domain in statuswatch.kontentwave.digital acme.statuswatch.kontentwave.digital; do
    echo "  • $domain:"
    dig +short $domain A || echo "    (dig failed)"
    echo ""
done

echo "Checking DNS propagation from multiple resolvers:"
for resolver in 8.8.8.8 1.1.1.1 9.9.9.9; do
    echo "  • acme.statuswatch.kontentwave.digital via $resolver:"
    dig @$resolver +short acme.statuswatch.kontentwave.digital A || echo "    (failed)"
done

# ============================================================================
# SECTION 2: CURRENT CADDYFILE CONFIGURATION
# ============================================================================
echo ""
echo "━━━ 2. CURRENT CADDYFILE ━━━"
echo ""

if [ -f Caddyfile ]; then
    echo "First 30 lines of Caddyfile:"
    head -n 30 Caddyfile
else
    echo "⚠️  Caddyfile not found in current directory"
fi

# ============================================================================
# SECTION 3: WILDCARD CERTIFICATE REQUIREMENTS
# ============================================================================
echo ""
echo "━━━ 3. WILDCARD CERT DETECTION ━━━"
echo ""

docker compose exec caddy caddy adapt --config /etc/caddy/Caddyfile 2>&1 | \
    grep -o '"host":\["[^]]*"\]' | head -5

echo ""
echo "Checking if wildcard is present:"
docker compose exec caddy caddy adapt --config /etc/caddy/Caddyfile 2>&1 | \
    grep -q '\*\.statuswatch\.kontentwave\.digital' && \
    echo "✓ Wildcard detected in config" || \
    echo "✗ No wildcard in config"

# ============================================================================
# SECTION 4: AVAILABLE TLS ISSUERS & SOLVERS
# ============================================================================
echo ""
echo "━━━ 4. CADDY TLS MODULES ━━━"
echo ""

echo "TLS issuance modules:"
docker compose exec caddy caddy list-modules | grep 'tls.issuance'

echo ""
echo "Note: tls.issuance.acme supports DNS-01 challenge IF configured with DNS provider"

# ============================================================================
# SECTION 5: ACME ERRORS FROM LOGS
# ============================================================================
echo ""
echo "━━━ 5. RECENT ACME/TLS ERRORS ━━━"
echo ""

docker compose logs caddy --tail 100 | grep -E 'error|ERROR' | tail -10

# ============================================================================
# SECTION 6: CURRENT SSL CERTIFICATES
# ============================================================================
echo ""
echo "━━━ 6. EXISTING CERTIFICATES ━━━"
echo ""

echo "Checking /data/caddy/certificates/:"
docker compose exec caddy sh -c 'ls -lah /data/caddy/certificates/ 2>/dev/null || echo "No certificates directory"'

echo ""
echo "Checking ACME directory:"
docker compose exec caddy sh -c 'find /data/caddy/acme -type f 2>/dev/null | head -20 || echo "No ACME data"'

# ============================================================================
# SECTION 7: SOLUTION OPTIONS
# ============================================================================
echo ""
echo "━━━ 7. SOLUTION OPTIONS ━━━"
echo ""

echo "OPTION A: Use explicit subdomains instead of wildcard"
echo "  Replace: *.statuswatch.kontentwave.digital"
echo "  With:    acme.statuswatch.kontentwave.digital, statuswatch.kontentwave.digital"
echo "  Pro:     Works with HTTP-01 challenge (no DNS API needed)"
echo "  Con:     Must add each new tenant subdomain explicitly"
echo ""

echo "OPTION B: Configure DNS-01 challenge with DNS provider"
echo "  Requires:"
echo "    1. DNS provider API credentials (e.g., Cloudflare, Route53)"
echo "    2. Caddy DNS plugin (e.g., caddy-dns/cloudflare)"
echo "    3. Modified Caddyfile with tls directive"
echo "  Pro:     True wildcard support for unlimited subdomains"
echo "  Con:     Requires DNS API access and custom Caddy build"
echo ""

echo "OPTION C: Use on-demand TLS (https://caddyserver.com/docs/automatic-https#on-demand-tls)"
echo "  Configure: on_demand_tls { ... } with ask endpoint"
echo "  Pro:     Auto-generates certs for any subdomain"
echo "  Con:     Requires backend endpoint to validate subdomain requests"
echo ""

# ============================================================================
# SECTION 8: ENVIRONMENT CHECK
# ============================================================================
echo ""
echo "━━━ 8. ENVIRONMENT VARIABLES ━━━"
echo ""

echo "Checking for DNS provider credentials in .env:"
docker compose exec web sh -c 'env | grep -E "CLOUDFLARE|AWS|ROUTE53|DNS" || echo "(none found)"'

# ============================================================================
# SECTION 9: NETWORK CONNECTIVITY
# ============================================================================
echo ""
echo "━━━ 9. ACME SERVER CONNECTIVITY ━━━"
echo ""

echo "Testing connection to Let's Encrypt staging:"
docker compose exec caddy sh -c 'wget -qO- --timeout=5 https://acme-staging-v02.api.letsencrypt.org/directory > /dev/null && echo "✓ Reachable" || echo "✗ Unreachable"'

echo ""
echo "Testing connection to Let's Encrypt production:"
docker compose exec caddy sh -c 'wget -qO- --timeout=5 https://acme-v02.api.letsencrypt.org/directory > /dev/null && echo "✓ Reachable" || echo "✗ Unreachable"'

# ============================================================================
# SECTION 10: RECOMMENDED IMMEDIATE ACTION
# ============================================================================
echo ""
echo "━━━ 10. IMMEDIATE RECOMMENDATION ━━━"
echo ""

echo "Based on diagnostics above:"
echo ""
echo "IF DNS for acme.statuswatch.kontentwave.digital is propagated:"
echo "  → Use OPTION A (explicit subdomains)"
echo "  → Edit Caddyfile to list: acme.statuswatch.kontentwave.digital, statuswatch.kontentwave.digital"
echo "  → Remove the wildcard (*.) pattern"
echo ""
echo "IF you need true wildcard support:"
echo "  → Use OPTION B (DNS-01 challenge)"
echo "  → Requires DNS provider API setup"
echo ""

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  END OF DIAGNOSTIC"
echo "═══════════════════════════════════════════════════════════════"
