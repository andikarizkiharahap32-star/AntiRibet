# AAC Quick Start Guide

Get up and running with AutoAccount Creator in 5 minutes.

## ⚡ Prerequisites

- Docker & Docker Compose installed
- API keys for: Bright Data (proxy), 2Captcha (captcha solver)
- Optional: 5sim API key (for Gmail only)

## 🚀 5-Minute Setup

### Step 1: Clone & Navigate

```bash
cd c:/Tools/aac-project
```

### Step 2: Generate Encryption Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Copy the output** - you'll need it in the next step.

### Step 3: Configure Environment

```bash
cd backend
copy .env.example .env
notepad .env
```

**Edit these critical values in .env:**

```env
# REQUIRED: Paste encryption key from Step 2
FERNET_KEY=<paste-key-here>

# REQUIRED: Your proxy credentials
BRIGHTDATA_USERNAME=your-brightdata-username
BRIGHTDATA_PASSWORD=your-brightdata-password

# REQUIRED: Your captcha solver key
TWOCAPTCHA_API_KEY=your-2captcha-api-key

# OPTIONAL: For Gmail accounts only
SIMS_API_KEY=your-5sim-api-key

# OPTIONAL: Disable LDAP if not using
LDAP_ENABLED=false
```

Save and close the file.

### Step 4: Start Services

```bash
cd ..
docker-compose up -d
```

Wait ~30 seconds for services to start.

### Step 5: Initialize Database

```bash
docker-compose exec backend python -m app.cli init-db
```

## ✅ Verify Installation

```bash
# Check all services are running
docker-compose ps

# Test API
curl http://localhost:8000/health

# Should return: {"status":"healthy","version":"1.0.0"}
```

## 🎯 Create Your First Accounts

### Discord Accounts (Recommended to Start)

```bash
# Create 10 Discord accounts
docker-compose exec backend python -m app.cli create --platform discord --count 10

# This will output a Job ID like:
# Job created: 550e8400-e29b-41d4-a716-446655440000
```

### Check Progress

```bash
# Check job status (replace with your Job ID)
docker-compose exec backend python -m app.cli status --job-id 550e8400-e29b-41d4-a716-446655440000

# Or list all jobs
docker-compose exec backend python -m app.cli list-jobs
```

### Export Results

```bash
# Export to CSV (replace with your Job ID)
docker-compose exec backend python -m app.cli export \
  --job-id 550e8400-e29b-41d4-a716-446655440000 \
  --format csv \
  --output accounts.csv

# Copy file from container to host
docker cp backend:/app/accounts.csv ./discord_accounts.csv
```

## 📊 Monitor Your Jobs

### Option 1: CLI

```bash
# View statistics
docker-compose exec backend python -m app.cli stats

# List all jobs
docker-compose exec backend python -m app.cli list-jobs
```

### Option 2: Flower (Celery Monitor)

Open browser: http://localhost:5555

- View active tasks
- Monitor worker status
- See task success/failure rates

### Option 3: Grafana (Advanced Monitoring)

Open browser: http://localhost:3001
- Login: admin/admin
- View real-time metrics and charts

## 🔧 Common Tasks

### Create Gmail Accounts

```bash
docker-compose exec backend python -m app.cli create \
  --platform gmail \
  --count 5 \
  --sms-provider 5sim
```

**Note**: Gmail has lower success rate (10-30%) due to phone verification.

### Cancel a Running Job

```bash
docker-compose exec backend python -m app.cli cancel --job-id <job-id>
```

### Export All Discord Accounts

```bash
docker-compose exec backend python -m app.cli export \
  --platform discord \
  --format csv \
  --output all_discord.csv
```

### View Logs

```bash
# Backend logs
docker-compose logs -f backend

# Worker logs
docker-compose logs -f worker

# All services
docker-compose logs -f
```

## 🐛 Troubleshooting

### Workers Not Processing Tasks

```bash
# Restart workers
docker-compose restart worker

# Check Redis connection
docker-compose exec backend redis-cli -h redis ping
# Should return: PONG
```

### Database Connection Errors

```bash
# Restart PostgreSQL
docker-compose restart postgres

# Check status
docker-compose exec postgres pg_isready
```

### Low Success Rate

**Discord**:
- Verify 2Captcha API key has balance
- Check proxy is working: `docker-compose logs worker`
- Use residential proxies (not datacenter)

**Gmail**:
- Verify 5sim API key has balance
- Gmail success rate is naturally lower (10-30%)
- Consider increasing retry count

### View Detailed Logs

```bash
# Backend application logs
docker-compose exec backend tail -f /app/logs/app.log

# Database logs
docker-compose logs postgres

# Worker task logs
docker-compose logs worker | grep "Job"
```

## 📚 Next Steps

### Learn More

- **Full Documentation**: See `README.md`
- **API Reference**: http://localhost:8000/api/v1/docs
- **Deployment Guide**: See `DEPLOYMENT.md`
- **Project Summary**: See `PROJECT_SUMMARY.md`

### Scale Up

```bash
# Increase workers to 10
docker-compose up -d --scale worker=10

# Create 100 accounts
docker-compose exec backend python -m app.cli create --platform discord --count 100
```

### Production Deployment

Follow the comprehensive guide in `DEPLOYMENT.md` for:
- SSL/TLS configuration
- Firewall setup
- Security hardening
- LDAP integration
- Monitoring alerts
- Backup procedures

## 🆘 Need Help?

### Check API Documentation

Open browser: http://localhost:8000/api/v1/docs

Interactive Swagger UI with:
- All available endpoints
- Request/response examples
- Try it out functionality

### View System Status

```bash
# Overall statistics
docker-compose exec backend python -m app.cli stats

# Service health
docker-compose ps

# Resource usage
docker stats
```

### Common Issues & Solutions

**Issue**: "FERNET_KEY not set"
**Solution**: Make sure you added the encryption key to `.env`

**Issue**: "Captcha solving failed"
**Solution**: Check 2Captcha API key and balance at https://2captcha.com

**Issue**: "No proxies available"
**Solution**: Verify Bright Data credentials in `.env`

**Issue**: "Database connection refused"
**Solution**: Wait 30 seconds after `docker-compose up` for PostgreSQL to initialize

## 🎉 Success Criteria

You're ready to go when:
- ✅ All services show "healthy" in `docker-compose ps`
- ✅ Health check returns `{"status":"healthy"}`
- ✅ You can create a test job successfully
- ✅ Workers are processing tasks (check Flower)
- ✅ You can export account data

## 💡 Tips for Best Results

1. **Start Small**: Test with 10 accounts first
2. **Monitor Progress**: Use Flower to watch tasks in real-time
3. **Check Costs**: View `docker-compose exec backend python -m app.cli stats`
4. **Use Residential Proxies**: Much better success rate than datacenter
5. **Discord First**: Easier than Gmail, higher success rate (60-80%)
6. **Keep API Keys Funded**: Check balances regularly

## 📞 Support

- **Documentation**: `/docs` in this repository
- **API Errors**: Check `docker-compose logs backend`
- **Task Failures**: Check `docker-compose logs worker`
- **System Issues**: See `DEPLOYMENT.md#troubleshooting`

---

**Ready to create accounts at scale!** 🚀

Start with: `docker-compose exec backend python -m app.cli create --platform discord --count 10`
