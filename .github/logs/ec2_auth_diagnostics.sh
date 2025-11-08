#!/bin/bash
# Comprehensive diagnostics for EC2 (service names aligned with compose)

set -euo pipefail
WEB=${WEB:-web}
PROXY=${PROXY:-caddy}
TS=$(date +%Y%m%d_%H%M%S)

section(){ echo -e "\n======================================================================\n$1\n======================================================================\n"; }

section "1. Containers"
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"

section "2. Gunicorn entrypoint + Django"
docker inspect "$(docker compose ps -q "$WEB")" --format 'Cmd: {{json .Config.Cmd}}  WorkDir: {{.Config.WorkingDir}}'
docker compose exec -T "$WEB" python - <<'PY' || true
import django, os
from django.conf import settings
print("django", django.get_version())
print("DJANGO_ENV", os.getenv("DJANGO_ENV"))
print("ALLOWED_HOSTS", settings.ALLOWED_HOSTS)
print("DATABASE_URL", os.getenv("DATABASE_URL"))
PY

section "3. Tenants & domains"
docker compose exec -T "$WEB" python - <<'PY'
from tenants.models import Client, Domain
for c in Client.objects.all():
    print(f"Tenant: {c.schema_name} | {c.name} | subscription={c.subscription_status}")
    for d in Domain.objects.filter(tenant=c):
        print(f"  - {d.domain} (primary={d.is_primary})")
PY

section "4. User in schemas (jwt@example.com)"
docker compose exec -T "$WEB" python - <<'PY'
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
User=get_user_model()
email="jwt@example.com"; pw="TestPass123!"
for s in ("public","acme"):
    try:
        with schema_context(s):
            try:
                u=User.objects.get(email=email)
                print(f"[{s}] exists=True active={u.is_active} pwd_ok={u.check_password(pw)} hash_prefix={u.password[:12]}")
            except User.DoesNotExist:
                print(f"[{s}] exists=False")
    except Exception as e:
        print(f"[{s}] ERROR: {e}")
PY

section "5. API auth tests"
# Detect primary acme/public domains
DOMS=$(docker compose exec -T "$WEB" python - <<'PY'
from tenants.models import Client, Domain
pub = Domain.objects.filter(is_primary=True, tenant__schema_name='public').values_list('domain', flat=True).first() or ""
try:
    ac = Client.objects.get(schema_name='acme')
    acd = Domain.objects.filter(tenant=ac, is_primary=True).values_list('domain', flat=True).first() or ""
except:
    acd = ""
print(pub + "|" + acd)
PY
)
IFS='|' read -r PUBD ACMD <<<"$DOMS"
for H in "$PUBD" "$ACMD"; do
  [ -n "$H" ] || continue
  echo "-- External via Caddy: https://$H"
  curl -k -sS -X POST "https://$H/api/auth/token/" \
    -H "Content-Type: application/json" \
    --data '{"username":"jwt@example.com","password":"TestPass123!"}' -i | head -n 20 || true
  echo "-- Internal to gunicorn with Host: $H"
  docker compose exec -T "$WEB" sh -lc "
    curl -sS -X POST http://127.0.0.1:8000/api/auth/token/ \
      -H 'Content-Type: application/json' -H 'Host: $H' \
      --data '{\"username\":\"jwt@example.com\",\"password\":\"TestPass123!\"}' -i | head -n 20" || true
done

section "6. Recent logs (web)"
docker compose logs --tail 300 "$WEB" || true
echo
echo "--- Files in /app/logs ---"
docker compose exec -T "$WEB" sh -lc 'ls -lah /app/logs || true'
echo
for f in authentication.log statuswatch.log error.log; do
  echo "--- tail /app/logs/$f ---"
  docker compose exec -T "$WEB" sh -lc "[ -f /app/logs/$f ] && tail -n 80 /app/logs/$f || true"
  echo
done

section "7. Reverse proxy (caddy)"
docker compose logs --tail 200 "$PROXY" || true

section "Done"
echo "Diagnostics finished at: $(date)  (TS=$TS)"
