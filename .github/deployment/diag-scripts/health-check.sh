#!/usr/bin/env bash
#
# StatusWatch Production Health Check
# Run this at 2AM when everything is on fire 🔥
#
# Usage:
#   ./scripts/health-check.sh                # Full check
#   ./scripts/health-check.sh --quick        # Quick check (no logs)
#   ./scripts/health-check.sh --fix          # Auto-fix common issues
#

set -euo pipefail

# ========================================
# Configuration
# ========================================
PRODUCTION_HOST="<your-ec2-ip>"
PRODUCTION_URL="https://statuswatch.kontentwave.digital"
SSH_USER="ubuntu"
SSH_KEY="${HOME}/.ssh/statuswatch-ec2-key.pem"

# Thresholds
DISK_WARN_THRESHOLD=80
MEMORY_WARN_THRESHOLD=80
RESPONSE_TIME_WARN_MS=2000

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ========================================
# Helper Functions
# ========================================
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

run_ssh() {
    ssh -i "$SSH_KEY" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "${SSH_USER}@${PRODUCTION_HOST}" "$@"
}

# ========================================
# Health Checks
# ========================================
check_ssh_connection() {
    log_info "Checking SSH connection to EC2..."
    if run_ssh "echo 'SSH OK'" &>/dev/null; then
        log_success "SSH connection OK"
        return 0
    else
        log_error "SSH connection FAILED"
        log_info "Troubleshoot: ssh -i $SSH_KEY ${SSH_USER}@${PRODUCTION_HOST}"
        return 1
    fi
}

check_containers() {
    log_info "Checking Docker containers..."

    local containers
    containers=$(run_ssh "cd /opt/statuswatch && docker compose ps --format json" 2>/dev/null || echo "[]")

    local required=("db" "redis" "web" "worker" "beat" "caddy")
    local all_ok=true

    for service in "${required[@]}"; do
        if echo "$containers" | grep -q "\"Service\":\"$service\""; then
            if echo "$containers" | grep "\"Service\":\"$service\"" | grep -q "\"State\":\"running\""; then
                log_success "$service is running"
            else
                log_error "$service is NOT running"
                all_ok=false
            fi
        else
            log_error "$service container NOT FOUND"
            all_ok=false
        fi
    done

    if [ "$all_ok" = true ]; then
        return 0
    else
        return 1
    fi
}

check_backend_health() {
    log_info "Checking backend health endpoint..."

    local response
    local http_code
    local response_time

    # Use domain for SSL, but resolve to IP
    response=$(curl -s -w "\n%{http_code}\n%{time_total}" \
        --resolve "statuswatch.kontentwave.digital:443:${PRODUCTION_HOST}" \
        "https://statuswatch.kontentwave.digital/health/" 2>/dev/null || echo -e "\n000\n0")

    http_code=$(echo "$response" | tail -n 2 | head -n 1)
    response_time=$(echo "$response" | tail -n 1)
    response_time_ms=$(echo "$response_time * 1000" | bc | cut -d. -f1 2>/dev/null || echo "0")

    if [ "$http_code" = "200" ]; then
        log_success "Backend health OK (${response_time_ms}ms)"

        if [ "$response_time_ms" -gt "$RESPONSE_TIME_WARN_MS" ]; then
            log_warn "Response time is slow: ${response_time_ms}ms (threshold: ${RESPONSE_TIME_WARN_MS}ms)"
        fi
        return 0
    else
        log_error "Backend health FAILED (HTTP $http_code)"
        return 1
    fi
}

check_frontend() {
    log_info "Checking frontend..."

    local http_code
    # Use domain with --resolve to force IP resolution
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        --resolve "statuswatch.kontentwave.digital:443:${PRODUCTION_HOST}" \
        "$PRODUCTION_URL" 2>/dev/null || echo "000")

    if [ "$http_code" = "200" ]; then
        log_success "Frontend OK (HTTP $http_code)"
        return 0
    else
        log_error "Frontend FAILED (HTTP $http_code)"
        return 1
    fi
}

check_database() {
    log_info "Checking PostgreSQL connection..."

    local result
    result=$(run_ssh "cd /opt/statuswatch && docker compose exec -T db psql -U postgres -d dj01 -c 'SELECT 1;'" 2>/dev/null || echo "FAILED")

    if echo "$result" | grep -q "1 row"; then
        log_success "Database connection OK"
        return 0
    else
        log_error "Database connection FAILED"
        return 1
    fi
}

check_redis() {
    log_info "Checking Redis connection..."

    local result
    result=$(run_ssh "cd /opt/statuswatch && docker compose exec -T redis redis-cli ping" 2>/dev/null || echo "FAILED")

    if [ "$result" = "PONG" ]; then
        log_success "Redis connection OK"
        return 0
    else
        log_error "Redis connection FAILED"
        return 1
    fi
}

check_disk_space() {
    log_info "Checking disk space..."

    local usage
    usage=$(run_ssh "df -h / | tail -1 | awk '{print \$5}' | sed 's/%//'")

    if [ "$usage" -lt "$DISK_WARN_THRESHOLD" ]; then
        log_success "Disk usage: ${usage}% (threshold: ${DISK_WARN_THRESHOLD}%)"
        return 0
    else
        log_warn "Disk usage HIGH: ${usage}% (threshold: ${DISK_WARN_THRESHOLD}%)"
        return 1
    fi
}

check_memory() {
    log_info "Checking memory usage..."

    local usage
    usage=$(run_ssh "free | grep Mem | awk '{print int(\$3/\$2 * 100)}'")

    if [ "$usage" -lt "$MEMORY_WARN_THRESHOLD" ]; then
        log_success "Memory usage: ${usage}% (threshold: ${MEMORY_WARN_THRESHOLD}%)"
        return 0
    else
        log_warn "Memory usage HIGH: ${usage}% (threshold: ${MEMORY_WARN_THRESHOLD}%)"
        return 1
    fi
}

check_ssl_cert() {
    log_info "Checking SSL certificate expiry..."

    local expiry_date
    # Connect to IP but use SNI for correct domain
    expiry_date=$(echo | openssl s_client -servername "statuswatch.kontentwave.digital" \
        -connect "${PRODUCTION_HOST}:443" 2>/dev/null | \
        openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)

    if [ -n "$expiry_date" ]; then
        local expiry_epoch
        expiry_epoch=$(date -d "$expiry_date" +%s)
        local now_epoch
        now_epoch=$(date +%s)
        local days_left=$(( (expiry_epoch - now_epoch) / 86400 ))

        if [ "$days_left" -gt 30 ]; then
            log_success "SSL cert expires in $days_left days"
            return 0
        elif [ "$days_left" -gt 7 ]; then
            log_warn "SSL cert expires in $days_left days (renew soon!)"
            return 0
        else
            log_error "SSL cert expires in $days_left days (URGENT!)"
            return 1
        fi
    else
        log_error "Could not check SSL certificate"
        return 1
    fi
}

check_recent_errors() {
    log_info "Checking recent errors in logs..."

    local errors
    errors=$(run_ssh "cd /opt/statuswatch && docker compose logs --tail=100 web worker beat 2>/dev/null | grep -i 'error\|exception\|traceback' | wc -l" || echo "0")

    if [ "$errors" -eq 0 ]; then
        log_success "No recent errors in logs"
        return 0
    else
        log_warn "Found $errors error lines in recent logs"
        log_info "Run: ssh $SSH_USER@$PRODUCTION_HOST 'cd /opt/statuswatch && docker compose logs --tail=50 web'"
        return 1
    fi
}

# ========================================
# Auto-fix Functions
# ========================================
auto_fix_containers() {
    log_info "Attempting to restart unhealthy containers..."

    run_ssh "cd /opt/statuswatch && docker compose restart"
    sleep 10

    log_success "Containers restarted"
}

auto_fix_pull_latest() {
    log_info "Pulling latest images..."

    run_ssh "cd /opt/statuswatch && docker compose pull && docker compose up -d"
    sleep 15

    log_success "Images updated and containers restarted"
}

# ========================================
# Main
# ========================================
main() {
    echo ""
    echo "═══════════════════════════════════════════════════"
    echo "  StatusWatch Production Health Check"
    echo "  $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "═══════════════════════════════════════════════════"
    echo ""

    local quick=false
    local fix=false

    # Parse arguments
    for arg in "$@"; do
        case $arg in
            --quick) quick=true ;;
            --fix) fix=true ;;
        esac
    done

    local failed_checks=0

    # Critical checks
    check_ssh_connection || ((failed_checks++))
    check_containers || ((failed_checks++))
    check_backend_health || ((failed_checks++))
    check_frontend || ((failed_checks++))

    # Database checks
    check_database || ((failed_checks++))
    check_redis || ((failed_checks++))

    # Resource checks
    check_disk_space || ((failed_checks++))
    check_memory || ((failed_checks++))

    # Security checks
    check_ssl_cert || ((failed_checks++))

    # Log checks (skip in quick mode)
    if [ "$quick" = false ]; then
        check_recent_errors || ((failed_checks++))
    fi

    echo ""
    echo "═══════════════════════════════════════════════════"

    if [ "$failed_checks" -eq 0 ]; then
        log_success "All checks passed! 🎉"
        exit 0
    else
        log_error "$failed_checks check(s) failed"

        if [ "$fix" = true ]; then
            echo ""
            log_info "Attempting auto-fix..."
            auto_fix_containers
            echo ""
            log_info "Re-running health checks..."
            sleep 5
            exec "$0" --quick  # Re-run in quick mode
        else
            echo ""
            log_info "Run with --fix to attempt automatic fixes"
            log_info "Or check logs: ssh $SSH_USER@$PRODUCTION_HOST 'cd /opt/statuswatch && docker compose logs -f'"
        fi

        exit 1
    fi
}

main "$@"
