#!/usr/bin/env bash
#
# Live Tail Logs from Production
# Stream logs from specific services or all at once
#
# Usage:
#   ./scripts/tail-logs.sh                   # All services
#   ./scripts/tail-logs.sh web               # Web only
#   ./scripts/tail-logs.sh web worker        # Multiple services
#   ./scripts/tail-logs.sh --errors          # Only errors
#

set -euo pipefail

PRODUCTION_HOST="<your-ec2-ip>"
SSH_USER="ubuntu"
SSH_KEY="${HOME}/.ssh/statuswatch-ec2-key.pem"

BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

main() {
    local services=""
    local errors_only=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--errors" ]]; then
            errors_only=true
            shift
        else
            services="$services $1"
            shift
        fi
    done

    echo ""
    log_info "Tailing logs from production..."
    log_info "Services: ${services:-all}${errors_only:+ (errors only)}"
    log_info "Press Ctrl+C to stop"
    echo ""

    if [[ "$errors_only" == true ]]; then
        ssh -i "$SSH_KEY" -t "${SSH_USER}@${PRODUCTION_HOST}" \
            "cd /opt/statuswatch && docker compose logs -f $services 2>&1 | grep -i --line-buffered 'error\|exception\|traceback\|critical'"
    else
        ssh -i "$SSH_KEY" -t "${SSH_USER}@${PRODUCTION_HOST}" \
            "cd /opt/statuswatch && docker compose logs -f $services"
    fi
}

main "$@"
