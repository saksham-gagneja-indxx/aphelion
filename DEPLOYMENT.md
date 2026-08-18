# Production Deployment Guide

Complete guide for deploying the Social Media Manager to production with GitHub Actions CI/CD.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [GitHub Actions Setup](#github-actions-setup)
4. [Environment Configuration](#environment-configuration)
5. [Deployment Workflows](#deployment-workflows)
6. [Infrastructure Setup](#infrastructure-setup)
7. [Monitoring & Rollback](#monitoring--rollback)
8. [Security Best Practices](#security-best-practices)

## Overview

The deployment system includes:
- **CI Pipeline**: Linting, type checking, unit tests on every push
- **CD Pipeline**: Automated build, test, and deployment to staging/production
- **Docker**: Containerized backend and frontend for consistency
- **GitHub Container Registry**: Private image storage with automatic cleanup
- **AWS EC2**: Production hosting with health monitoring
- **Nginx**: Reverse proxy with SSL/TLS, rate limiting, and security headers

## Prerequisites

### Local Development
- Docker & Docker Compose
- Python 3.12+
- Node.js 18+
- Git

### Production Infrastructure
- AWS Account with EC2 instance (t3.small minimum)
- Domain name registered & DNS configured
- GitHub repository with Actions enabled
- Slack workspace (optional, for notifications)

### Required Secrets (GitHub)
```
AWS_ACCESS_KEY_ID          # AWS IAM user credentials
AWS_SECRET_ACCESS_KEY
AWS_REGION                 # e.g., us-east-1
EC2_HOST                   # Public IP or domain of EC2 instance
EC2_USER                   # SSH user (e.g., ec2-user, ubuntu)
EC2_SSH_KEY                # Private SSH key for EC2 access
SLACK_WEBHOOK              # Slack webhook for notifications (optional)
GITHUB_TOKEN               # Auto-provided by GitHub Actions
```

## GitHub Actions Setup

### 1. Add Repository Secrets

Navigate to **Settings → Secrets and variables → Actions** and add:

```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=wJ8k...
AWS_REGION=us-east-1

# EC2 Configuration
EC2_HOST=api.postpilot.com
EC2_USER=ec2-user
EC2_SSH_KEY=-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----

# Slack (optional)
SLACK_WEBHOOK=https://hooks.slack.com/services/...
```

### 2. Configure GitHub Variables

Add public variables in **Settings → Variables → Actions**:

```bash
REGISTRY=ghcr.io
IMAGE_NAME=your-org/postpilot
```

### 3. Enable Branch Protection Rules

In **Settings → Branches → main**:
- ✅ Require a pull request before merging
- ✅ Require status checks to pass (CI, Integration Tests)
- ✅ Require code reviews before merging
- ✅ Require branches to be up to date before merging

## Environment Configuration

### .env.production

```bash
# Flask
FLASK_ENV=production
FLASK_PORT=5000
SECRET_KEY=<generate-with-secrets.token_urlsafe(32)>
DEBUG=false

# API
API_ACCESS_KEY=<generate-with-secrets.token_urlsafe(32)>
CORS_ORIGINS=https://postpilot.com

# Database (PostgreSQL)
DATABASE_URL=postgresql://user:password@db.internal:5432/postpilot

# Redis
REDIS_URL=redis://cache.internal:6379/0

# Authentication
CLERK_SECRET_KEY=sk_live_...
ENCRYPTION_KEY=<Fernet key from cryptography.fernet.Fernet.generate_key()>

# LinkedIn OAuth
LINKEDIN_CLIENT_ID=<from LinkedIn Developer Dashboard>
LINKEDIN_CLIENT_SECRET=<from LinkedIn Developer Dashboard>

# AI/ML
NVIDIA_API_KEY=nvapi-...
CLAUDE_API_KEY=sk-ant-...

# Monitoring
SENTRY_DSN=https://key@sentry.io/project
LOG_LEVEL=INFO

# Scheduler
SCHEDULER_ENABLED=true
SCHEDULER_CHECK_INTERVAL=60
```

### Generate Secrets

```python
# Generate Flask SECRET_KEY and API_ACCESS_KEY
import secrets
print(secrets.token_urlsafe(32))

# Generate Fernet encryption key
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

## Deployment Workflows

### Workflow 1: Continuous Integration (ci.yml)

Runs on every push and pull request:

```
1. Backend Lint (flake8, mypy)
2. Frontend Lint (ESLint)
3. Backend Unit Tests
4. Frontend Unit Tests
5. Security Scan (Trivy)
```

**Triggers**: Push to main/develop, All PRs

### Workflow 2: Docker Build (deploy.yml)

On merge to main:

```
1. Build backend Docker image
   - Multi-stage build (builder → runtime)
   - Push to GitHub Container Registry
   - Tag with commit SHA and "latest"

2. Build frontend Docker image
   - Vite production build
   - Serve with Node.js
   - Push to GitHub Container Registry

3. Create deployment artifacts
   - Image tags for tracking
   - Build logs for debugging
```

### Workflow 3: Deploy to Staging

```
1. Pull new Docker images
2. Run health checks
3. Execute smoke tests
4. Notify Slack on success/failure
```

### Workflow 4: Deploy to Production (Manual Approval)

Requires manual approval via GitHub Environment:

```
1. AWS authentication (STS)
2. SSH into EC2 instance
3. Pull and restart Docker containers
4. Run health checks (30 attempts, 10s intervals)
5. Execute smoke tests
6. Notify Slack on completion
```

## Infrastructure Setup

### AWS EC2 Instance

#### Launch Configuration
```bash
# AMI: Ubuntu 22.04 LTS
# Instance Type: t3.small (adjustable)
# Storage: 50GB (EBS gp3)
# Security Group: 
#   - Allow port 22 (SSH) from CI/CD IP
#   - Allow port 80 (HTTP) from anywhere
#   - Allow port 443 (HTTPS) from anywhere
```

#### Initial Setup Script
```bash
#!/bin/bash
set -e

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create app directory
mkdir -p /app
cd /app

# Create .env.production from template
# (SSH in and create securely)

# Create SSL directory
mkdir -p ssl

# Start services
docker-compose up -d
```

### RDS Database Setup

```bash
# Create PostgreSQL RDS instance
aws rds create-db-instance \
  --db-instance-identifier postpilot-prod \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username admin \
  --master-user-password <strong-password> \
  --allocated-storage 20 \
  --backup-retention-period 7 \
  --multi-az
```

### ElastiCache Redis

```bash
# Create Redis cluster for caching
aws elasticache create-cache-cluster \
  --cache-cluster-id postpilot-redis \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --num-cache-nodes 1
```

### SSL/TLS Certificate

```bash
# Using Let's Encrypt with certbot
sudo apt install certbot python3-certbot-nginx
sudo certbot certonly --standalone -d postpilot.com -d api.postpilot.com
sudo cp /etc/letsencrypt/live/postpilot.com/fullchain.pem /app/ssl/cert.pem
sudo cp /etc/letsencrypt/live/postpilot.com/privkey.pem /app/ssl/key.pem
sudo chown $USER:$USER /app/ssl/*
```

## Monitoring & Rollback

### CloudWatch Monitoring

```bash
# Monitor CPU and memory
aws cloudwatch put-metric-alarm \
  --alarm-name postpilot-high-cpu \
  --alarm-description "Alert when CPU exceeds 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/EC2 \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold
```

### Health Checks

Each service has healthcheck endpoints:
- **Backend**: `GET /health` (database connectivity)
- **Frontend**: `GET /` (HTTP 200)
- **Nginx**: `GET /health` (proxied to backend)

### Rollback Procedure

```bash
# SSH into EC2
ssh -i deploy_key.pem ec2-user@api.postpilot.com

# View deployment history
docker compose logs -n 50

# Rollback to previous version
docker pull ghcr.io/your-org/postpilot/backend:sha-<previous-sha>
docker pull ghcr.io/your-org/postpilot/frontend:sha-<previous-sha>

# Update docker-compose.yml with previous SHA
# Restart services
docker compose up -d

# Verify health
curl -f https://postpilot.com/health
```

## Security Best Practices

### 1. Environment Variables
- **Never commit secrets to Git**
- Use GitHub Secrets for all sensitive data
- Rotate secrets regularly
- Use separate secrets per environment

### 2. Docker Images
- **Scan images for vulnerabilities**
  ```bash
  docker scan ghcr.io/your-org/postpilot/backend:latest
  ```
- Use minimal base images (alpine/slim)
- Keep dependencies updated
- Don't run containers as root

### 3. Network Security
- **SSL/TLS required** (nginx enforces HTTPS)
- **HSTS headers** (Strict-Transport-Security)
- **Rate limiting** on API endpoints
- **CORS properly configured** per environment
- **Security headers** (X-Frame-Options, CSP, etc.)

### 4. Database Security
- **Use RDS with encryption at rest**
- **Enable automated backups** (7-30 day retention)
- **Use VPC for database access** (not public)
- **Strong password policy**
- **Regular backup testing**

### 5. Access Control
- **SSH keys** (no password auth)
- **GitHub branch protection** rules
- **Require pull request reviews**
- **Status checks must pass**
- **Audit logs** for all deployments

### 6. Monitoring & Alerts
- **CloudWatch dashboards**
- **Slack/email alerts** on deployment failures
- **Error tracking** (Sentry integration)
- **Uptime monitoring** (external service)
- **Log aggregation** (CloudWatch Logs)

## Troubleshooting

### Deployment Fails
1. Check GitHub Actions logs
2. Review AWS credentials and permissions
3. Verify EC2 instance is running and accessible
4. Check security group rules allow SSH access

### Health Check Fails
1. SSH into EC2 and check container logs
   ```bash
   docker compose logs backend -f
   docker compose logs frontend -f
   ```
2. Verify database connectivity
   ```bash
   docker compose exec backend python -c "from backend.utils.database import init_db; init_db()"
   ```
3. Check environment variables are set correctly

### Slow Deployments
1. Review Docker build caching
2. Check GitHub Actions runner availability
3. Consider using smaller base images
4. Enable parallel builds where possible

### Database Connection Issues
1. Verify DATABASE_URL is correct
2. Check RDS security group allows EC2 access
3. Test connection locally:
   ```bash
   psql $DATABASE_URL
   ```
4. Check database migrations are applied

## Useful Commands

```bash
# View deployment logs
docker compose logs -f

# Check service status
docker compose ps

# Restart services
docker compose restart

# View resource usage
docker stats

# Database backup
pg_dump $DATABASE_URL > backup.sql

# Database restore
psql $DATABASE_URL < backup.sql

# View Redis cache
redis-cli -h redis.internal KEYS '*'
redis-cli -h redis.internal FLUSHDB  # Clear cache

# Deploy specific version
# Edit docker-compose.yml with specific image SHA
# Run: docker compose up -d
```

## Support & Resources

- [GitHub Actions Documentation](https://docs.github.com/actions)
- [Docker Documentation](https://docs.docker.com)
- [AWS EC2 User Guide](https://docs.aws.amazon.com/ec2)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt](https://letsencrypt.org)

## Next Steps

1. ✅ Set up GitHub repository
2. ✅ Configure GitHub Secrets
3. ✅ Launch AWS infrastructure
4. ✅ Configure domain DNS
5. ✅ Set up SSL certificate
6. ✅ Create `.env.production`
7. ✅ Push code and trigger initial deployment
8. ✅ Monitor logs and health checks
9. ✅ Set up monitoring dashboards
10. ✅ Document runbooks for team
