# AutoAccount Creator (AAC)

**Enterprise-grade automated Discord and Gmail account creation system**

## 🎯 Overview

AAC is a comprehensive automation platform designed for internal teams (QA, Research, Growth Hacking) to create Discord and Gmail accounts at scale without manual OTP verification. Built with FastAPI, Celery, Playwright, and Next.js.

### Key Features

- ✅ **Bulk Account Creation**: 5-10 accounts/minute/worker
- ✅ **Discord Automation**: 60-80% success rate with hCaptcha solving
- ✅ **Gmail Automation**: 10-30% success rate with SMS verification
- ✅ **Proxy Rotation**: Bright Data / Smartproxy integration
- ✅ **Real-time Dashboard**: WebSocket progress monitoring
- ✅ **Enterprise Security**: LDAP/SSO, JWT, Fernet encryption (AES-256)
- ✅ **Cost Tracking**: Budget alerts at 80% and 95% of $50/month
- ✅ **Fingerprint Randomization**: Canvas, WebGL, User-Agent spoofing

### Success Metrics

| Metric | Target |
|--------|--------|
| Discord Success Rate | 60-80% |
| Gmail Success Rate | 10-30% |
| Time per Account | 15-30 seconds |
| Monthly Capacity | 100-1,000 accounts |
| Monthly Budget | < $50 USD |

## 🏗️ Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│  Next.js    │──────│   FastAPI    │──────│  PostgreSQL │
│  Dashboard  │      │   Backend    │      │   Database  │
└─────────────┘      └──────────────┘      └─────────────┘
                            │
                     ┌──────┴──────┐
                     │             │
              ┌──────▼─────┐  ┌───▼────┐
              │   Celery   │  │ Redis  │
              │  Workers   │  │ Broker │
              └────────────┘  └────────┘
                     │
          ┌──────────┼──────────┐
          │          │          │
     ┌────▼───┐ ┌───▼────┐ ┌──▼─────┐
     │Playwright│ │2Captcha│ │ Proxies│
     │ Browser │ │Solver  │ │ Pool   │
     └──────────┘ └────────┘ └────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- PostgreSQL 16 or MySQL 8
- Redis 7

### 1. Clone and Setup

```bash
cd c:/Tools/aac-project
cp backend/.env.example backend/.env
# Edit backend/.env with your credentials
```

### 2. Generate Encryption Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Add to .env as FERNET_KEY
```

### 3. Start Services

```bash
# Using Docker Compose
docker-compose up -d

# Or manually
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload

# Start Celery workers
celery -A app.workers.celery_app worker --loglevel=info -Q high,normal,low -c 4

# Start Celery Beat (scheduler)
celery -A app.workers.celery_app beat --loglevel=info
```

### 4. Access Dashboard

- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/v1/docs
- **Frontend**: http://localhost:3000
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000

## 📋 Configuration

### Environment Variables

See `backend/.env.example` for all configuration options.

**Critical Settings:**

```env
# Database
DATABASE_URL="postgresql://user:pass@localhost:5432/aac_db"

# Encryption (REQUIRED)
FERNET_KEY="your-32-byte-base64-fernet-key"

# Proxy Provider
PROXY_PROVIDER="brightdata"
BRIGHTDATA_USERNAME="your-username"
BRIGHTDATA_PASSWORD="your-password"

# Captcha Solver
TWOCAPTCHA_API_KEY="your-2captcha-key"

# SMS Service (for Gmail)
SIMS_API_KEY="your-5sim-api-key"
```

### LDAP Configuration

```env
LDAP_ENABLED=true
LDAP_SERVER="ldap://your-ldap-server:389"
LDAP_BIND_DN="cn=admin,dc=company,dc=com"
LDAP_ALLOWED_GROUP="cn=aac-users,ou=groups,dc=company,dc=com"
```

## 🔧 Usage

### CLI Usage (MVP)

```bash
# Create 100 Discord accounts
python -m app.cli create --platform discord --count 100 --proxy-provider brightdata

# Create 50 Gmail accounts
python -m app.cli create --platform gmail --count 50 --sms-provider 5sim

# Export accounts
python -m app.cli export --platform discord --format csv --output accounts.csv
```

### API Usage

**Create Job:**

```bash
curl -X POST "http://localhost:8000/api/v1/jobs" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "discord",
    "total_count": 100,
    "proxy_provider": "brightdata",
    "captcha_provider": "2captcha"
  }'
```

**Monitor Progress:**

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/jobs/JOB_ID/stream');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`Progress: ${data.percentage}%`);
};
```

**Export Accounts:**

```bash
curl -X GET "http://localhost:8000/api/v1/accounts/export?format=csv&platform=discord" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -o accounts.csv
```

## 🔐 Security

### Authentication

- **LDAP/SSO**: Internal authentication with group-based access control
- **JWT Tokens**: 15-minute access tokens, 8-hour refresh tokens
- **Role-Based Access**: Admin, Operator, Viewer roles

### Encryption

- **Fernet (AES-256)**: All passwords encrypted before database storage
- **Key Rotation**: Supports dual-key setup for zero-downtime rotation
- **No Plaintext**: Zero plaintext credentials in database or logs

### Audit Logging

All actions logged with:
- User ID
- Action type
- IP address
- User agent
- Timestamp
- 30-day retention

## 📊 Monitoring

### Prometheus Metrics

- `http_requests_total`: Total HTTP requests
- `http_request_duration_seconds`: Request duration
- `celery_tasks_total`: Total Celery tasks
- `account_creation_success_rate`: Success rate by platform
- `proxy_health_status`: Proxy availability

### Grafana Dashboards

1. **Job Overview**: Success rate, throughput, queue length
2. **Proxy Performance**: Response time, success rate by provider
3. **Cost Tracking**: Daily/monthly spend vs budget
4. **Worker Health**: Active workers, task distribution

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Integration tests only
pytest tests/integration/

# Unit tests only
pytest tests/unit/
```

## 🐳 Docker Deployment

```bash
# Build images
docker-compose build

# Start all services
docker-compose up -d

# Scale workers
docker-compose up -d --scale worker=10

# View logs
docker-compose logs -f backend worker

# Stop all
docker-compose down
```

## 📈 Performance Optimization

### Throughput Tuning

```env
# Increase workers
MAX_WORKERS=50
CELERY_WORKER_MAX_TASKS_PER_CHILD=100

# Connection pooling
DATABASE_POOL_SIZE=50
DATABASE_MAX_OVERFLOW=20
```

### Success Rate Optimization

1. **Use residential proxies** (not datacenter)
2. **Rotate proxies** after each account
3. **Use premium captcha solvers** (2Captcha Pro)
4. **Add delays** between actions (random 0.5-2s)
5. **Randomize fingerprints** (User-Agent, Canvas, WebGL)

## 🚨 Troubleshooting

### Common Issues

**Low Success Rate (<40%)**
- Check proxy quality (residential > datacenter)
- Verify captcha solver balance
- Review logs for specific error patterns

**Workers Not Processing**
- Check Redis connection: `redis-cli ping`
- Verify Celery workers running: `celery -A app.workers.celery_app inspect active`
- Check queue length: `celery -A app.workers.celery_app inspect reserved`

**Database Connection Errors**
- Verify DATABASE_URL in .env
- Check PostgreSQL is running: `pg_isready`
- Increase connection pool: `DATABASE_POOL_SIZE=50`

## 📝 API Documentation

Full API documentation available at:
- **Swagger UI**: http://localhost:8000/api/v1/docs
- **ReDoc**: http://localhost:8000/api/v1/redoc

## 🤝 Contributing

This is an internal tool. For contributions:

1. Create feature branch
2. Run tests: `pytest`
3. Format code: `black app/`
4. Create pull request

## 📄 License

Proprietary - Internal Use Only

## ⚠️ Legal Disclaimer

This tool is for **internal testing and research purposes only**. Users must:

- Comply with platform Terms of Service
- Not use for spam, fraud, or illegal activities
- Respect rate limits and anti-automation measures
- Ensure proper authorization for testing activities

## 🆘 Support

- **Documentation**: See `/docs` folder
- **Issues**: Internal issue tracker
- **Slack**: #aac-support channel

---

**Version**: 1.0.0  
**Last Updated**: 2024-01-15  
**Maintainer**: DevOps Team
