#!/usr/bin/env bash
#
# Deploy Latest Code to Production
# Pull latest from GitHub and restart services
#
# Usage:
#   ./scripts/deploy.sh                      # Interactive
#   ./scripts/deploy.sh --force              # No confirmation
#   ./scripts/deploy.sh --no-migrate         # Skip migrations
#

set -euo pipefail

PRODUCTION_HOST="<your-ec2-ip>"
SSH_USER="ubuntu"
SSH_KEY="${HOME}/.ssh/statuswatch-ec2-key.pem"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }

run_ssh() {
    ssh -i "$SSH_KEY" "${SSH_USER}@${PRODUCTION_HOST}" "$@"
}

main() {
    local force=false
    local run_migrations=true

    for arg in "$@"; do
        case $arg in
            --force) force=true ;;
            --no-migrate) run_migrations=false ;;
        esac
    done

    echo ""
    echo "═══════════════════════════════════════════════════"
    echo "  Deploy to Production"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "═══════════════════════════════════════════════════"
    echo ""

    if [[ "$force" != true ]]; then
        log_warn "This will deploy the latest code to production"
        read -p "Continue? (yes/no): " -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
            log_info "Aborted"
            exit 0
        fi
    fi

    log_info "Step 1/6: Pulling latest code from GitHub..."
    run_ssh "cd /opt/statuswatch/django-statuswatch && git pull"
    log_success "Code updated"

    echo ""
    log_info "Step 2/6: Waiting for new Docker image to be built..."
    log_info "Checking GitHub Actions... (this may take 3-5 minutes)"
    sleep 10

    echo ""
    log_info "Step 3/6: Pulling latest Docker images..."
    run_ssh "cd /opt/statuswatch && export IMAGE_TAG=edge && docker compose pull"
    log_success "Images pulled"

    echo ""
    log_info "Step 4/6: Restarting containers..."
    run_ssh "cd /opt/statuswatch && docker compose up -d --force-recreate"
    log_success "Containers restarted"

    echo ""
    log_info "Step 5/6: Waiting for services to become healthy..."
    sleep 20

    if [[ "$run_migrations" == true ]]; then
        echo ""
        log_info "Step 6/6: Running database migrations..."
        run_ssh "cd /opt/statuswatch && docker compose exec -T web python manage.py migrate"
        log_success "Migrations applied"
    else
        log_warn "Skipping migrations (--no-migrate flag)"
    fi

    echo ""
    echo "═══════════════════════════════════════════════════"
    log_success "Deployment complete!"
    log_info "Check health: ./scripts/health-check.sh"
    log_info "Monitor logs: ./scripts/tail-logs.sh"
    echo ""
}

main "$@"
