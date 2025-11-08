#!/bin/bash
# Diagnose why acme.statuswatch.kontentwave.digital is not reachable
# Focus: Caddy, SSL, DNS, network routing

set -euo pipefail

echo "======================================================================"
echo "HTTPS/Caddy Diagnostics for acme.statuswatch.kontentwave.digital"
echo "Date: $(date)"
echo "======================================================================"
echo ""

DOMAIN="acme.statuswatch.kontentwave.digital"
PUBLIC_DOMAIN="statuswatch.kontentwave.digital"

echo "1. DNS RESOLUTION (from EC2)"
echo "----------------------------------------------------------------------"
echo "Checking DNS for $DOMAIN:"
dig +short "$DOMAIN" || nslookup "$DOMAIN" || echo "DNS lookup failed"
echo ""
echo "Checking DNS for $PUBLIC_DOMAIN:"
dig +short "$PUBLIC_DOMAIN" || nslookup "$PUBLIC_DOMAIN" || echo "DNS lookup failed"
echo ""

echo "2. CADDY CONTAINER STATUS"
echo "----------------------------------------------------------------------"
docker ps --filter "name=caddy" --format "Name: {{.Names}}\nStatus: {{.Status}}\nPorts: {{.Ports}}\nHealth: {{.Health}}"
echo ""

echo "3. CADDY CONFIGURATION"
echo "----------------------------------------------------------------------"
echo "Checking Caddy config file locations:"
find /opt/statuswatch -name "Caddyfile*" 2>/dev/null || echo "No Caddyfile found"
echo ""
echo "Checking if Caddy has config mounted:"
docker inspect statuswatch-caddy-1 --format '{{json .Mounts}}' | python3 -m json.tool 2>/dev/null || docker inspect statuswatch-caddy-1 --format '{{.Mounts}}'
echo ""

echo "4. CADDY RUNNING CONFIG (from container)"
echo "----------------------------------------------------------------------"
echo "Getting active Caddy config:"
docker exec statuswatch-caddy-1 caddy adapt --config /etc/caddy/Caddyfile 2>&1 || echo "Cannot read Caddyfile"
echo ""

echo "5. CADDY LOGS (Last 50 lines)"
echo "----------------------------------------------------------------------"
docker logs --tail 50 statuswatch-caddy-1 2>&1
echo ""

echo "6. CADDY HEALTH CHECK"
echo "----------------------------------------------------------------------"
docker inspect statuswatch-caddy-1 --format '{{json .State.Health}}' | python3 -m json.tool 2>/dev/null || echo "No health data"
echo ""

echo "7. NETWORK CONNECTIVITY TEST"
echo "----------------------------------------------------------------------"
echo "A) Can we reach Caddy from host (port 443)?"
timeout 3 bash -c "echo > /dev/tcp/127.0.0.1/443" 2>&1 && echo "✓ Port 443 is open" || echo "✗ Port 443 not reachable"
echo ""
echo "B) Can we reach Caddy from host (port 80)?"
timeout 3 bash -c "echo > /dev/tcp/127.0.0.1/80" 2>&1 && echo "✓ Port 80 is open" || echo "✗ Port 80 not reachable"
echo ""
echo "C) What's listening on port 443?"
ss -tlnp | grep ':443' || netstat -tlnp | grep ':443' || echo "Cannot check ports"
echo ""

echo "8. TEST DIRECT TO CADDY (HTTP/80)"
echo "----------------------------------------------------------------------"
echo "Testing HTTP (should redirect to HTTPS):"
curl -v -H "Host: $DOMAIN" http://127.0.0.1/ 2>&1 | head -30
echo ""

echo "9. TEST DIRECT TO CADDY (HTTPS/443)"
echo "----------------------------------------------------------------------"
echo "Testing HTTPS with SNI:"
curl -vk --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/" 2>&1 | head -50
echo ""

echo "10. TEST WEB CONTAINER DIRECTLY (bypass Caddy)"
echo "----------------------------------------------------------------------"
echo "Testing Django directly (via port 8003 or internal):"
docker inspect statuswatch-web-1 --format '{{.NetworkSettings.IPAddress}}'
WEB_IP=$(docker inspect statuswatch-web-1 --format '{{.NetworkSettings.IPAddress}}' 2>/dev/null || echo "")
if [ -n "$WEB_IP" ]; then
    echo "Web container IP: $WEB_IP"
    curl -s -H "Host: $DOMAIN" "http://$WEB_IP:8000/" | head -20 || echo "Cannot reach web container"
else
    echo "Testing via published port 8003:"
    curl -s -H "Host: $DOMAIN" "http://127.0.0.1:8003/" | head -20 || echo "Port 8003 not accessible"
fi
echo ""

echo "11. DOCKER NETWORK INSPECTION"
echo "----------------------------------------------------------------------"
echo "Networks:"
docker network ls
echo ""
echo "Caddy network connections:"
docker inspect statuswatch-caddy-1 --format '{{json .NetworkSettings.Networks}}' | python3 -m json.tool 2>/dev/null || echo "No network info"
echo ""

echo "12. FIREWALL/SECURITY GROUPS (if applicable)"
echo "----------------------------------------------------------------------"
echo "Checking ufw status:"
sudo ufw status 2>/dev/null || echo "ufw not available"
echo ""
echo "Checking iptables rules for 443:"
sudo iptables -L -n | grep -E '443|HTTPS' || echo "No iptables rules for 443"
echo ""

echo "13. SSL CERTIFICATE CHECK"
echo "----------------------------------------------------------------------"
echo "Checking SSL cert for $DOMAIN:"
echo | timeout 3 openssl s_client -connect 127.0.0.1:443 -servername "$DOMAIN" 2>&1 | grep -E '(subject|issuer|Verify return code)' || echo "SSL connection failed"
echo ""

echo "14. COMPOSE FILE CHECK"
echo "----------------------------------------------------------------------"
echo "Caddy service definition in compose files:"
grep -A 20 "caddy:" /opt/statuswatch/docker-compose*.yml 2>/dev/null || echo "Cannot find Caddy config"
echo ""

echo "15. ENVIRONMENT VARIABLES IN CADDY"
echo "----------------------------------------------------------------------"
docker exec statuswatch-caddy-1 env | grep -E '(DOMAIN|ACME|SSL|CERT)' || echo "No SSL/domain related env vars"
echo ""

echo "======================================================================"
echo "DIAGNOSTIC SUMMARY"
echo "======================================================================"
echo ""
echo "Key things to check in output above:"
echo "  1. DNS resolves to correct IP"
echo "  2. Caddy is running and healthy"
echo "  3. Port 443 is open and listening"
echo "  4. Caddy config includes $DOMAIN"
echo "  5. SSL certificate is valid for $DOMAIN"
echo "  6. No firewall blocking 443"
echo ""
echo "======================================================================"
