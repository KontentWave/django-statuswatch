#!/bin/bash
set -euo pipefail
TS=$(date +%Y%m%d_%H%M%S)
OUT=".github/logs/diagnostics_${TS}"
mkdir -p "$OUT"

echo "Running preflight…"
.github/logs/preflight_check.sh || true

echo "Comprehensive diagnostics…"
.github/logs/ec2_auth_diagnostics.sh > "$OUT/full.txt" 2>&1 || true

echo "Quick auth test…"
.github/logs/test_auth.sh > "$OUT/auth_test.txt" 2>&1 || true

echo "Container logs…"
docker compose logs --tail 300 web   > "$OUT/web_logs.txt" 2>&1 || true
docker compose logs --tail 300 caddy > "$OUT/caddy_logs.txt" 2>&1 || true

echo "Compressing…"
( cd .github/logs && tar -czf "diagnostics_${TS}.tar.gz" "diagnostics_${TS}" )
echo "Saved: $OUT and .github/logs/diagnostics_${TS}.tar.gz"
