#!/usr/bin/env bash
#
# Quick Database Diagnostics
# Check database health, connections, tenant schemas, and recent queries
#
# Usage:
#   ./scripts/db-check.sh                    # Full check
#   ./scripts/db-check.sh --tenants          # List tenants only
#   ./scripts/db-check.sh --connections      # Show connections only
#   ./scripts/db-check.sh --slow-queries     # Show slow queries
#

set -euo pipefail

PRODUCTION_HOST="<your-ec2-ip>"
SSH_USER="ubuntu"
SSH_KEY="${HOME}/.ssh/statuswatch-ec2-key.pem"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

run_sql() {
    ssh -i "$SSH_KEY" "${SSH_USER}@${PRODUCTION_HOST}" \
        "cd /opt/statuswatch && docker compose exec -T db psql -U postgres -d dj01 -c \"$1\""
}

check_db_size() {
    log_info "Database size..."
    run_sql "SELECT pg_size_pretty(pg_database_size('dj01')) AS size;"
}

check_connections() {
    log_info "Active connections..."
    run_sql "SELECT count(*) as total, state FROM pg_stat_activity WHERE datname = 'dj01' GROUP BY state;"
}

check_tenant_schemas() {
    log_info "Tenant schemas..."
    run_sql "SELECT schema_name FROM tenants_client ORDER BY schema_name;"
}

check_tenant_domains() {
    log_info "Tenant domains..."
    run_sql "SELECT c.schema_name, c.name, d.domain, d.is_primary FROM tenants_client c JOIN tenants_domain d ON c.id = d.tenant_id ORDER BY c.schema_name, d.is_primary DESC;"
}

check_slow_queries() {
    log_info "Slowest queries (last 24h)..."
    run_sql "SELECT query, calls, total_exec_time::int, mean_exec_time::int, max_exec_time::int FROM pg_stat_statements WHERE query NOT LIKE '%pg_stat%' ORDER BY mean_exec_time DESC LIMIT 10;"
}

check_table_sizes() {
    log_info "Largest tables..."
    run_sql "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema') ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 10;"
}

check_migrations() {
    log_info "Applied migrations..."
    run_sql "SELECT app, name FROM django_migrations ORDER BY applied DESC LIMIT 20;"
}

main() {
    echo ""
    echo "═══════════════════════════════════════════════════"
    echo "  Database Diagnostics"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "═══════════════════════════════════════════════════"
    echo ""

    case "${1:-all}" in
        --tenants)
            check_tenant_schemas
            check_tenant_domains
            ;;
        --connections)
            check_connections
            ;;
        --slow-queries)
            check_slow_queries
            ;;
        *)
            check_db_size
            echo ""
            check_connections
            echo ""
            check_tenant_schemas
            echo ""
            check_tenant_domains
            echo ""
            check_table_sizes
            echo ""
            check_migrations
            ;;
    esac

    echo ""
    log_success "Database check complete"
}

main "$@"
