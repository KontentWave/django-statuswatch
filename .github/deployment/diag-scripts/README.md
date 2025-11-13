# StatusWatch Production Diagnostic Scripts (Public Templates)

These are **sanitized templates** for demonstration and portfolio purposes.

## 🔒 Security Notice

**These are PUBLIC templates with placeholders!**

- For **production use**, copy these to `/scripts/` directory (which is gitignored)
- Replace `<your-ec2-ip>` with your actual EC2 public IP
- Replace `statuswatch-ec2-key.pem` with your actual SSH key filename
- **Never commit production credentials to version control**

## 📋 Scripts Overview

### 1. `health-check.sh` - Complete Health Monitoring

**10 production health checks:**

- SSH connectivity
- Docker containers (db, redis, web, worker, beat, caddy)
- Backend `/health/` endpoint
- Frontend accessibility
- PostgreSQL connection
- Redis connection
- Disk space (warns at 80%)
- Memory usage (warns at 80%)
- SSL certificate expiry (warns at 30 days)
- Recent error logs

**Usage:**

```bash
./health-check.sh           # Full check (includes log analysis)
./health-check.sh --quick   # Essential checks only (faster)
./health-check.sh --fix     # Auto-remediation attempt
```

**Key Feature:** Uses `curl --resolve` for SSL validation with IP addresses

### 2. `db-check.sh` - Database Diagnostics

**Database health checks:**

- Database size and growth
- Active connections by state
- Tenant schemas list
- Tenant domain mappings
- Largest tables
- Recent migrations
- Slow query detection

**Usage:**

```bash
./db-check.sh                    # Full database report
./db-check.sh --tenants          # List tenants only
./db-check.sh --connections      # Active connections only
./db-check.sh --slow-queries     # Slow query analysis
```

### 3. `emergency-restart.sh` - Safe Restart Automation

**Emergency restart workflow:**

1. Pull latest Docker images
2. Stop containers gracefully
3. Start containers
4. Wait for health checks
5. Verify health endpoint

**Usage:**

```bash
./emergency-restart.sh          # Interactive (asks confirmation)
./emergency-restart.sh --force  # Skip confirmation (CI/CD)
```

**Downtime:** ~30-60 seconds

### 4. `tail-logs.sh` - Live Log Streaming

**Real-time log monitoring:**

- Stream logs from any service combination
- Filter errors only with `--errors` flag
- Uses `grep --line-buffered` for real-time filtering

**Usage:**

```bash
./tail-logs.sh                  # All services
./tail-logs.sh web              # Web service only
./tail-logs.sh web worker       # Multiple services
./tail-logs.sh --errors         # Only errors/exceptions
```

### 5. `deploy.sh` - Deployment Automation

**Safe deployment workflow:**

1. Pull latest code from GitHub
2. Wait for GitHub Actions build
3. Pull new Docker images
4. Restart containers
5. Run database migrations
6. Health check verification

**Usage:**

```bash
./deploy.sh                     # Interactive deployment
./deploy.sh --force             # Skip confirmation
./deploy.sh --no-migrate        # Skip migrations
```

## 🚀 Quick Start (Production Setup)

### 1. Copy templates to your private `/scripts/` directory:

```bash
# From project root
cp -r .github/deployment/diag-scripts/* scripts/
chmod +x scripts/*.sh
```

### 2. Update configuration in **ALL** scripts:

```bash
# Edit these variables in each .sh file:
PRODUCTION_HOST="<your-ec2-ip>"           # Your EC2 public IP
SSH_KEY="${HOME}/.ssh/your-key.pem"       # Your SSH key path
```

**Files to update:**

- `scripts/health-check.sh`
- `scripts/db-check.sh`
- `scripts/emergency-restart.sh`
- `scripts/tail-logs.sh`
- `scripts/deploy.sh`

### 3. Verify SSH access:

```bash
ssh -i ~/.ssh/your-key.pem ubuntu@<your-ec2-ip>
```

### 4. Test health check:

```bash
cd /path/to/statuswatch-project
./scripts/health-check.sh --quick
```

## 📊 Common Scenarios

### 🔥 Site is down

```bash
# 1. Quick health check
./scripts/health-check.sh --quick

# 2. If containers are down, restart
./scripts/emergency-restart.sh

# 3. Monitor recovery
./scripts/tail-logs.sh web
```

### 🐌 Site is slow

```bash
# 1. Check resource usage
./scripts/health-check.sh

# 2. Check slow queries
./scripts/db-check.sh --slow-queries

# 3. Monitor errors
./scripts/tail-logs.sh --errors
```

### 🔒 SSL certificate expiring

```bash
# 1. Check expiry date
./scripts/health-check.sh | grep SSL

# 2. Restart Caddy (auto-renews)
ssh ubuntu@<your-ec2-ip> 'cd /opt/statuswatch && docker compose restart caddy'

# 3. Verify renewal
./scripts/tail-logs.sh caddy
```

### 👤 Tenant issues

```bash
# 1. List all tenants
./scripts/db-check.sh --tenants

# 2. Check specific tenant logs
./scripts/tail-logs.sh web | grep tenant-name

# 3. Verify domain mapping
./scripts/db-check.sh --tenants | grep domain.com
```

## 🛠️ Customization

### Adjust thresholds in `health-check.sh`:

```bash
DISK_WARN_THRESHOLD=80          # Disk space warning at 80%
MEMORY_WARN_THRESHOLD=80        # Memory warning at 80%
RESPONSE_TIME_WARN_MS=2000      # Response time warning at 2s
```

### Add custom checks:

```bash
check_custom_service() {
    log_info "Checking custom service..."
    # Your check logic here
    return 0  # or 1 for failure
}

# Add to main() function:
check_custom_service || ((failed_checks++))
```

## 🔐 Security Best Practices

1. ✅ **Never commit** `/scripts/` with real credentials (already gitignored)
2. ✅ **Keep SSH keys secure:** `chmod 400 ~/.ssh/your-key.pem`
3. ✅ **Use SSH config** for cleaner script configuration
4. ✅ **Rotate SSH keys** regularly
5. ✅ **Monitor script execution** with audit logs

### Optional: Use SSH config instead of hardcoded values

Create `~/.ssh/config`:

```
Host statuswatch-prod
    HostName <your-ec2-ip>
    User ubuntu
    IdentityFile ~/.ssh/your-key.pem
    StrictHostKeyChecking no
```

Then update scripts:

```bash
# Instead of:
ssh -i "$SSH_KEY" "${SSH_USER}@${PRODUCTION_HOST}" "command"

# Use:
ssh statuswatch-prod "command"
```

## 📈 Monitoring Integration

### Cron job for automated health checks:

```bash
# Add to your local crontab (not on EC2!)
# Check every 5 minutes, send email on failure
*/5 * * * * /path/to/scripts/health-check.sh --quick || echo "ALERT: Health check failed" | mail -s "StatusWatch Alert" you@email.com
```

### Integration with monitoring tools:

```bash
# Export metrics for Prometheus/Grafana
./scripts/health-check.sh --quick > /var/log/statuswatch/health.log
```

## 🎯 Architecture

**Multi-tenant SaaS Platform:**

- Django 5.1 + DRF (multi-tenant with django-tenants)
- PostgreSQL 16 (tenant schemas)
- Redis 7 (Celery broker)
- Celery Beat + Worker (endpoint monitoring)
- Caddy 2 (on-demand TLS for wildcard subdomains)
- Docker Compose (6 containers)

**Production Stack:**

- EC2 instance (Ubuntu 22.04 LTS)
- Docker Compose production override pattern
- GitHub Actions (auto-builds to GHCR)
- Let's Encrypt SSL (via Caddy on-demand TLS)

## 📚 Related Documentation

- [EC2 Deployment Guide](../EC2_DEPLOYMENT_GUIDE.md)
- [Production ADR](../../docs/ADRs/Phase%202/08-deployment.md)
- [Project Documentation](../../docs/StatusWatch_project_sheet.md)

## 🤝 Contributing

These scripts are part of the StatusWatch open-source project. For production-specific improvements:

1. Test changes in staging environment first
2. Never commit sensitive information
3. Follow the placeholder pattern for public templates
4. Document new checks in this README

## 📝 License

MIT License - See main repository for details

---

**Maintained by:** StatusWatch Development Team  
**Last Updated:** November 13, 2025  
**Version:** 1.0.0
