#!/bin/bash
# Quick authentication test for the EC2 stack (web+caddy)
# Usage: ./test_auth.sh [email] [password] [host]

set -euo pipefail

EMAIL="${1:-jwt@example.com}"
PASSWORD="${2:-TestPass123!}"
HOST_ARG="${3:-}"

WEB=${WEB:-web}

bold(){ printf "\033[1m%s\033[0m\n" "$*"; }

bold "======================================================================"
bold "Testing Authentication (EC2)"
echo "Email: $EMAIL"
echo "Time:  $(date)"
echo ""

# Discover domains from inside Django
discover_domains() {
  docker compose exec -T "$WEB" python - <<'PY'
from tenants.models import Client, Domain
from django_tenants.utils import schema_context
try:
    acme = Client.objects.get(schema_name='acme')
    acme_domain = Domain.objects.filter(tenant=acme, is_primary=True).values_list('domain', flat=True).first()
except Client.DoesNotExist:
    acme_domain = None
public = Domain.objects.filter(is_primary=True, tenant__schema_name='public').values_list('domain', flat=True).first()
print((public or "") + "|" + (acme_domain or ""))
PY
}

IFS='|' read -r PUBLIC_DOMAIN ACME_DOMAIN <<<"$(discover_domains)"
HOST="${HOST_ARG:-${ACME_DOMAIN:-${PUBLIC_DOMAIN:-statuswatch.kontentwave.digital}}}"

echo "Detected domains:"
echo "  public: ${PUBLIC_DOMAIN:-<none>}"
echo "  acme:   ${ACME_DOMAIN:-<none>}"
echo "Using host for tests: $HOST"
echo ""

bold "1) External test (via Caddy/HTTPS)"
curl -k -sS -X POST "https://${HOST}/api/auth/token/" \
  -H "Content-Type: application/json" \
  --data "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}" \
  -D /tmp/auth_headers.out \
  -o /tmp/auth_body.out || true
echo "Status line: $(head -n1 /tmp/auth_headers.out)"
echo "Body:"
cat /tmp/auth_body.out; echo
echo ""

bold "2) Internal test (inside web → gunicorn, with Host header)"
docker compose exec -T "$WEB" sh -lc "
curl -sS -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H 'Content-Type: application/json' \
  -H 'Host: ${HOST}' \
  --data '{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}' -i" || true
echo ""

bold "3) ORM check of user in schemas"
docker compose exec -T "$WEB" python - <<PY
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
User = get_user_model()
email = "${EMAIL}"
pw = "${PASSWORD}"
for schema in ("public","acme"):
    try:
        with schema_context(schema):
            try:
                u = User.objects.get(email=email)
                print(f"[{schema}] exists=True active={u.is_active} pwd_ok={u.check_password(pw)}")
            except User.DoesNotExist:
                print(f"[{schema}] exists=False")
    except Exception as e:
        print(f"[{schema}] ERROR: {e}")
PY
echo ""

bold "Done."
