#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok(){ echo -e "${GREEN}✓${NC} $*"; }
warn(){ echo -e "${YELLOW}⚠${NC} $*"; }
bad(){ echo -e "${RED}✗${NC} $*"; }

WEB=${WEB:-web}; PROXY=${PROXY:-caddy}; DB=${DB:-db}; REDIS=${REDIS:-redis}

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║         StatusWatch EC2 - Preflight (web/caddy/db/redis)            ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"

command -v docker >/dev/null && ok "Docker installed" || { bad "Docker missing"; exit 1; }

docker ps | grep -q "$WEB"   && ok "web container running"   || bad "web NOT running"
docker ps | grep -q "$PROXY" && ok "caddy container running" || warn "caddy not found"
docker ps | grep -q "$DB"    && ok "db container running"    || warn "db not found"
docker ps | grep -q "$REDIS" && ok "redis container running" || warn "redis not found"

echo "Django sanity:"
docker compose exec -T "$WEB" python - <<'PY' || bad "Django check failed"
import django; print("django", django.get_version())
PY
ok "Django reachable in container"

docker compose exec -T "$WEB" sh -lc 'ls -ld /app/logs || true'
ok "Checked logs folder"

echo -e "${GREEN}Ready to run diagnostics.${NC}"
