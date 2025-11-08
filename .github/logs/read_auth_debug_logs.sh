#!/bin/bash
# Show recent auth-related logs from the web container
# Usage: ./read_auth_debug_logs.sh [lines]

LINES=${1:-100}
WEB=${WEB:-web}

echo "======================================================================"
echo "Auth-related logs (last $LINES lines)"
echo "======================================================================"

docker compose exec -T "$WEB" sh -lc '
for f in /app/logs/authentication.log /app/logs/statuswatch.log /app/logs/error.log; do
  if [ -f "$f" ]; then
    echo "--- $f ---"
    tail -n '"$LINES"' "$f"
  fi
done
' || echo "Unable to read logs."
