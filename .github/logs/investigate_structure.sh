#!/bin/bash
# Quick structure investigation for EC2 setup
# This will reveal the exact compose setup and container names

set -euo pipefail

echo "======================================================================"
echo "StatusWatch EC2 - Structure Investigation"
echo "Date: $(date)"
echo "======================================================================"
echo ""

echo "1. CURRENT DIRECTORY & COMPOSE FILES"
echo "----------------------------------------------------------------------"
echo "Current directory: $(pwd)"
echo ""
echo "Looking for docker-compose files:"
find . -maxdepth 2 -name "*.yml" -o -name "*.yaml" | grep -i compose || echo "No compose files found in current dir"
echo ""
echo "Checking common locations:"
ls -la docker-compose.yml compose.yml compose.yaml 2>/dev/null || echo "No standard compose file in current directory"
echo ""

echo "2. DOCKER COMPOSE PROJECT & SERVICES"
echo "----------------------------------------------------------------------"
echo "Docker compose project name:"
docker compose ls || docker-compose ps --services || echo "Cannot detect compose project"
echo ""
echo "All running containers:"
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
echo ""
echo "Service names from compose:"
docker compose ps --services 2>/dev/null || docker-compose ps --services 2>/dev/null || echo "Cannot list services"
echo ""

echo "3. CONTAINER NAME DETECTION"
echo "----------------------------------------------------------------------"
echo "Searching for web/backend containers:"
docker ps --filter "name=web" --format "{{.Names}}" || true
docker ps --filter "name=backend" --format "{{.Names}}" || true
docker ps --filter "name=django" --format "{{.Names}}" || true
docker ps --filter "name=statuswatch" --format "{{.Names}}" || true
echo ""
echo "Searching for proxy containers:"
docker ps --filter "name=caddy" --format "{{.Names}}" || true
docker ps --filter "name=nginx" --format "{{.Names}}" || true
docker ps --filter "name=proxy" --format "{{.Names}}" || true
echo ""

echo "4. EXACT CONTAINER NAMES FROM DOCKER PS"
echo "----------------------------------------------------------------------"
docker ps --format "{{.Names}}" | while read -r name; do
    image=$(docker inspect "$name" --format "{{.Config.Image}}")
    echo "Container: $name"
    echo "  Image: $image"
    echo "  Labels: $(docker inspect "$name" --format '{{json .Config.Labels}}' | jq -r 'to_entries[] | select(.key | contains("com.docker.compose")) | "\(.key)=\(.value)"' 2>/dev/null || echo "N/A")"
    echo ""
done
echo ""

echo "5. COMPOSE FILE CONTENT (if exists)"
echo "----------------------------------------------------------------------"
if [ -f "compose.yml" ]; then
    echo "Found compose.yml:"
    head -50 compose.yml
elif [ -f "docker-compose.yml" ]; then
    echo "Found docker-compose.yml:"
    head -50 docker-compose.yml
elif [ -f "compose.yaml" ]; then
    echo "Found compose.yaml:"
    head -50 compose.yaml
else
    echo "No compose file found in current directory"
    echo "Checking parent directory:"
    ls -la ../compose.yml ../docker-compose.yml ../compose.yaml 2>/dev/null || echo "Not found in parent either"
fi
echo ""

echo "6. ENVIRONMENT FILE LOCATION"
echo "----------------------------------------------------------------------"
echo "Looking for .env files:"
find . -maxdepth 3 -name ".env" -o -name ".env.*" | grep -v node_modules || echo "No .env files found"
echo ""
echo "Checking specific locations:"
ls -la .env backend/.env django-statuswatch/backend/.env 2>/dev/null || echo "Standard locations not found"
echo ""

echo "7. WEB/DJANGO CONTAINER INSPECTION"
echo "----------------------------------------------------------------------"
WEB_CONTAINER=$(docker ps --format "{{.Names}}" | grep -E "(web|django|backend|statuswatch.*web)" | head -1)
if [ -n "$WEB_CONTAINER" ]; then
    echo "Detected web container: $WEB_CONTAINER"
    echo ""
    echo "Container command:"
    docker inspect "$WEB_CONTAINER" --format 'CMD: {{json .Config.Cmd}}' | jq -r '.' 2>/dev/null || docker inspect "$WEB_CONTAINER" --format 'CMD: {{.Config.Cmd}}'
    echo ""
    echo "Working directory:"
    docker inspect "$WEB_CONTAINER" --format 'WorkingDir: {{.Config.WorkingDir}}'
    echo ""
    echo "Environment variables (filtered):"
    docker inspect "$WEB_CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -E '(DJANGO|DATABASE|REDIS|PYTHON|PATH|APP)' | head -20
    echo ""
    echo "Directory structure inside container:"
    docker exec "$WEB_CONTAINER" ls -la / 2>/dev/null | head -20 || echo "Cannot list root"
    docker exec "$WEB_CONTAINER" ls -la /app 2>/dev/null | head -20 || echo "Cannot list /app"
    echo ""
    echo "Django check:"
    docker exec "$WEB_CONTAINER" python -c "import django; print('Django version:', django.get_version())" 2>/dev/null || echo "Django not accessible"
    echo ""
else
    echo "ERROR: Cannot detect web/django container"
    echo "Manual check needed - paste container name"
fi
echo ""

echo "8. DATABASE CONNECTION TEST"
echo "----------------------------------------------------------------------"
if [ -n "$WEB_CONTAINER" ]; then
    echo "Testing database connection from Django:"
    docker exec "$WEB_CONTAINER" python -c "
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT version()')
        print('Database:', cursor.fetchone()[0])
except Exception as e:
    print('DB Error:', e)
" 2>/dev/null || echo "Cannot test DB connection"
else
    echo "Skipped - no web container detected"
fi
echo ""

echo "9. TENANT & DOMAIN CHECK"
echo "----------------------------------------------------------------------"
if [ -n "$WEB_CONTAINER" ]; then
    echo "Checking tenants and domains:"
    docker exec "$WEB_CONTAINER" python -c "
from tenants.models import Client, Domain
print('Tenants:')
for c in Client.objects.all():
    print(f'  {c.schema_name} | {c.name}')
print('Domains:')
for d in Domain.objects.all():
    print(f'  {d.domain} -> {d.tenant.schema_name} (primary={d.is_primary})')
" 2>/dev/null || echo "Cannot query tenants"
else
    echo "Skipped - no web container detected"
fi
echo ""

echo "10. DOCKER COMPOSE COMMAND DETECTION"
echo "----------------------------------------------------------------------"
echo "Testing compose commands:"
if docker compose version &>/dev/null; then
    echo "✓ 'docker compose' (plugin) works"
    COMPOSE_CMD="docker compose"
elif docker-compose --version &>/dev/null; then
    echo "✓ 'docker-compose' (standalone) works"
    COMPOSE_CMD="docker-compose"
else
    echo "✗ Neither 'docker compose' nor 'docker-compose' work"
    COMPOSE_CMD="unknown"
fi
echo "Recommended command: $COMPOSE_CMD"
echo ""

echo "======================================================================"
echo "SUMMARY & RECOMMENDATIONS"
echo "======================================================================"
echo ""

if [ -n "$WEB_CONTAINER" ]; then
    echo "✓ Web container detected: $WEB_CONTAINER"
else
    echo "✗ Web container NOT detected - manual intervention needed"
fi

PROXY_CONTAINER=$(docker ps --format "{{.Names}}" | grep -E "(caddy|nginx|proxy)" | head -1)
if [ -n "$PROXY_CONTAINER" ]; then
    echo "✓ Proxy container detected: $PROXY_CONTAINER"
else
    echo "✗ Proxy container NOT detected"
fi

echo ""
echo "For diagnostic scripts to work, export these variables:"
echo ""
if [ -n "$WEB_CONTAINER" ]; then
    SERVICE_NAME=$(echo "$WEB_CONTAINER" | sed 's/statuswatch-//; s/-1$//')
    echo "  export WEB=$SERVICE_NAME"
fi
if [ -n "$PROXY_CONTAINER" ]; then
    PROXY_SERVICE=$(echo "$PROXY_CONTAINER" | sed 's/statuswatch-//; s/-1$//')
    echo "  export PROXY=$PROXY_SERVICE"
fi
echo "  export COMPOSE_CMD='$COMPOSE_CMD'"
echo ""
echo "Then re-run diagnostics with these variables set."
echo ""
echo "======================================================================"
