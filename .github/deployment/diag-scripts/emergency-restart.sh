#!/usr/bin/env bash
#
# Emergency Restart Script
# Use when everything is broken at 2AM
#
# Usage:
#   ./scripts/emergency-restart.sh           # Interactive (asks for confirmation)
#   ./scripts/emergency-restart.sh --force   # No confirmation (YOLO mode)
#

set -euo pipefail

PRODUCTION_HOST="<your-ec2-ip>"
SSH_USER="ubuntu"
SSH_KEY="${HOME}/.ssh/statuswatch-ec2-key.pem"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

run_ssh() {
    ssh -i "$SSH_KEY" "${SSH_USER}@${PRODUCTION_HOST}" "$@"
}

main() {
    echo ""
    echo "═══════════════════════════════════════════════════"
    echo "  🚨 EMERGENCY RESTART 🚨"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "═══════════════════════════════════════════════════"
    echo ""

    log_warn "This will restart ALL production containers"
    log_warn "Estimated downtime: 30-60 seconds"
    echo ""

    if [[ "${1:-}" != "--force" ]]; then
        read -p "Are you sure? (yes/no): " -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
            log_info "Aborted"
            exit 0
        fi
    fi

    log_info "Step 1/5: Pulling latest images..."
    run_ssh "cd /opt/statuswatch && docker compose pull" || {
        log_error "Failed to pull images"
        exit 1
    }
    log_success "Images pulled"

    echo ""
    log_info "Step 2/5: Stopping containers gracefully..."
    run_ssh "cd /opt/statuswatch && docker compose down" || {
        log_warn "Graceful stop failed, forcing..."
        run_ssh "cd /opt/statuswatch && docker compose down --remove-orphans"
    }
    log_success "Containers stopped"

    echo ""
    log_info "Step 3/5: Starting containers..."
    run_ssh "cd /opt/statuswatch && docker compose up -d" || {
        log_error "Failed to start containers!"
        log_info "Check logs: ssh $SSH_USER@$PRODUCTION_HOST 'cd /opt/statuswatch && docker compose logs'"
        exit 1
    }
    log_success "Containers started"

    echo ""
    log_info "Step 4/5: Waiting for services to become healthy (30s)..."
    sleep 30

    echo ""
    log_info "Step 5/5: Verifying health..."

    local web_healthy
    web_healthy=$(run_ssh "cd /opt/statuswatch && docker compose ps web --format json | grep -o '\"Health\":\"[^\"]*\"' | cut -d'\"' -f4" || echo "unhealthy")

    if [[ "$web_healthy" == "healthy" ]]; then
        log_success "Web container is healthy"
    else
        log_warn "Web container is $web_healthy (may still be starting)"
    fi

    # Quick health check
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "https://statuswatch.kontentwave.digital/health/" || echo "000")

    if [[ "$http_code" == "200" ]]; then
        log_success "Health endpoint responding (HTTP $http_code)"
    else
        log_warn "Health endpoint not ready (HTTP $http_code)"
    fi

    echo ""
    echo "═══════════════════════════════════════════════════"
    log_success "Restart complete!"
    log_info "Monitor: ssh $SSH_USER@$PRODUCTION_HOST 'cd /opt/statuswatch && docker compose logs -f'"
    echo ""
}

main "$@"
