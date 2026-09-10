# AAC Deployment Guide

Complete guide for deploying AutoAccount Creator to production.

## 📋 Prerequisites

### System Requirements
- **OS**: Ubuntu 22.04 LTS (recommended) or Windows Server
- **CPU**: 4+ vCPU cores
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 100GB SSD minimum
- **Network**: 100 Mbps minimum

### Software Requirements
- Docker 24.0+
- Docker Compose 2.0+
- Git 2.0+
- (Optional) kubectl for Kubernetes deployment

## 🚀 Quick Deployment (Docker Compose)

### 1. Clone Repository

```bash
cd /opt
git clone https://github.com/your-org/aac-project.git
cd aac-project
```

### 2. Generate Secrets

```bash
# Generate Fernet encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Save output as FERNET_KEY

# Generate JWT secret
openssl rand -base64 32
# Save output as JWT_SECRET_KEY
```

### 3. Configure Environment

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

**Critical settings to configure:**

```env
# Database
DATABASE_URL=postgresql://aac_user:CHANGE_THIS_PASSWORD@postgres:5432/aac_db

# Encryption (REQUIRED)
FERNET_KEY=<output-from-step-2>
JWT_SECRET_KEY=<output-from-step-2>

# Proxy Provider (REQUIRED)
PROXY_PROVIDER=brightdata
BRIGHTDATA_USERNAME=your-brightdata-username
BRIGHTDATA_PASSWORD=your-brightdata-password

# Captcha Solver (REQUIRED)
TWOCAPTCHA_API_KEY=your-2captcha-api-key

# SMS Service (for Gmail only)
SIMS_API_KEY=your-5sim-api-key

# LDAP (Optional - set LDAP_ENABLED=false if not using)
LDAP_ENABLED=true
LDAP_SERVER=ldap://your-ldap-server:389
LDAP_BIND_DN=cn=admin,dc=company,dc=com
LDAP_BIND_PASSWORD=ldap-password
LDAP_ALLOWED_GROUP=cn=aac-users,ou=groups,dc=company,dc=com
```

### 4. Start Services

```bash
# Build and start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f backend worker
```

### 5. Initialize Database

```bash
# Run migrations
docker-compose exec backend alembic upgrade head

# Or use CLI
docker-compose exec backend python -m app.cli init-db
```

### 6. Verify Deployment

```bash
# Health check
curl http://localhost:8000/health

# API docs
open http://localhost:8000/api/v1/docs

# Frontend
open http://localhost:3000

# Flower (Celery monitoring)
open http://localhost:5555

# Grafana (monitoring)
open http://localhost:3001
```

## 🔒 Production Security Hardening

### 1. SSL/TLS Configuration

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d aac.example.com

# Auto-renewal
sudo certbot renew --dry-run
```

### 2. Firewall Rules

```bash
# Allow SSH, HTTP, HTTPS only
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Block direct access to backend ports
sudo ufw deny 8000/tcp
sudo ufw deny 5432/tcp
sudo ufw deny 6379/tcp
```

### 3. Change Default Passwords

```bash
# PostgreSQL
docker-compose exec postgres psql -U postgres
ALTER USER aac_user WITH PASSWORD 'new-strong-password';

# Update in .env file
sed -i 's/old-password/new-strong-password/g' backend/.env

# Restart services
docker-compose restart
```

### 4. Enable LDAP Authentication

Configure LDAP in `.env`:

```env
LDAP_ENABLED=true
LDAP_SERVER=ldap://ldap.company.com:389
LDAP_BIND_DN=cn=admin,dc=company,dc=com
LDAP_BIND_PASSWORD=secure-ldap-password
LDAP_USER_SEARCH_BASE=ou=users,dc=company,dc=com
LDAP_ALLOWED_GROUP=cn=aac-users,ou=groups,dc=company,dc=com
```

### 5. Setup Monitoring Alerts

Configure Prometheus alert rules in `monitoring/prometheus/rules.yml`:

```yaml
groups:
  - name: aac_alerts
    rules:
      - alert: HighFailureRate
        expr: rate(account_creation_failed_total[5m]) > 0.5
        for: 10m
        annotations:
          summary: "High account creation failure rate"
      
      - alert: WorkersDown
        expr: celery_workers_active < 2
        for: 5m
        annotations:
          summary: "Celery workers below minimum"
      
      - alert: BudgetAlert
        expr: sum(account_cost_total) > 40
        annotations:
          summary: "Monthly budget exceeded $40"
```

## 📊 Monitoring Setup

### Grafana Dashboard

1. Access Grafana: http://localhost:3001
2. Login (default: admin/admin)
3. Import dashboard: `monitoring/grafana/dashboards/aac-dashboard.json`
4. Configure Prometheus data source: http://prometheus:9090

### Prometheus Metrics

Custom metrics exposed:
- `account_creation_total` - Total accounts created
- `account_creation_success_total` - Successful accounts
- `account_creation_duration_seconds` - Creation time
- `proxy_health_status` - Proxy availability
- `celery_workers_active` - Active workers
- `celery_queue_length` - Pending tasks

## 🔧 Scaling

### Horizontal Scaling (Workers)

```bash
# Scale to 10 workers
docker-compose up -d --scale worker=10

# Check worker status
docker-compose exec backend celery -A app.workers.celery_app inspect active
```

### Vertical Scaling (Resources)

Edit `docker-compose.yml`:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

### Database Scaling

```bash
# Enable PostgreSQL connection pooling
# In .env:
DATABASE_POOL_SIZE=50
DATABASE_MAX_OVERFLOW=20

# Or use PgBouncer
docker run -d \
  --name pgbouncer \
  -e DATABASE_URL=postgres://user:pass@postgres:5432/db \
  -p 6432:6432 \
  edoburu/pgbouncer
```

## 🔄 Maintenance

### Backup Database

```bash
# Automated daily backup
docker-compose exec postgres pg_dump -U aac_user aac_db > backup_$(date +%Y%m%d).sql

# Restore from backup
docker-compose exec -T postgres psql -U aac_user aac_db < backup_20240115.sql
```

### Log Rotation

```bash
# Configure Docker log rotation
cat > /etc/docker/daemon.json <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

sudo systemctl restart docker
```

### Update Deployment

```bash
# Pull latest changes
cd /opt/aac-project
git pull origin main

# Rebuild and restart
docker-compose build
docker-compose up -d

# Run database migrations
docker-compose exec backend alembic upgrade head

# Verify
docker-compose ps
docker-compose logs -f backend | grep "Application startup"
```

## 🐛 Troubleshooting

### Issue: Workers not processing tasks

```bash
# Check Celery workers
docker-compose logs worker

# Restart workers
docker-compose restart worker

# Check Redis connection
docker-compose exec backend redis-cli -h redis ping
```

### Issue: High memory usage

```bash
# Check container stats
docker stats

# Reduce worker concurrency
# In docker-compose.yml:
command: celery -A app.workers.celery_app worker -c 2

# Or set memory limits
docker-compose exec backend celery -A app.workers.celery_app control pool_shrink 2
```

### Issue: Database connection errors

```bash
# Check PostgreSQL status
docker-compose exec postgres pg_isready

# Restart PostgreSQL
docker-compose restart postgres

# Check connections
docker-compose exec postgres psql -U aac_user -d aac_db -c "SELECT count(*) FROM pg_stat_activity;"
```

### Issue: Proxy failures

```bash
# Test proxy connectivity
docker-compose exec backend python -c "
import httpx
proxy_url = 'http://user:pass@proxy:port'
client = httpx.Client(proxies=proxy_url, timeout=10)
print(client.get('http://httpbin.org/ip').text)
"

# Check proxy health
docker-compose exec backend python -m app.cli list-proxies
```

## 📞 Support

- **Documentation**: `/docs` folder
- **API Docs**: http://localhost:8000/api/v1/docs
- **Monitoring**: http://localhost:3001 (Grafana)
- **Issues**: Internal issue tracker

## 🔐 Security Checklist

- [ ] Change all default passwords
- [ ] Enable SSL/TLS with valid certificates
- [ ] Configure firewall rules
- [ ] Enable LDAP authentication
- [ ] Set up automated backups
- [ ] Configure monitoring alerts
- [ ] Rotate encryption keys quarterly
- [ ] Review audit logs weekly
- [ ] Update dependencies monthly
- [ ] Perform security scans

## 📝 License

Proprietary - Internal Use Only

---

**Last Updated**: 2024-01-15  
**Version**: 1.0.0  
**Maintainer**: DevOps Team
