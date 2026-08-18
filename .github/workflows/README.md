# GitHub Actions Workflows

This directory contains CI/CD workflows for automated testing and deployment.

## Workflows Overview

### 1. **ci.yml** - Continuous Integration
**Trigger**: Every push to `main` or `develop`, all pull requests

**Jobs**:
- Backend Lint (flake8, mypy)
- Frontend Lint (ESLint)
- Backend Unit Tests (pytest with coverage)
- Frontend Unit Tests (vitest/jest with coverage)
- Security Scanning (Trivy vulnerability scanner)

**Duration**: ~10-15 minutes

**Artifacts**:
- Coverage reports (Codecov)
- SARIF security findings

### 2. **deploy.yml** - Build & Deploy
**Trigger**: Push to `main` branch OR manual workflow dispatch

**Jobs**:
1. **build**: Build and push Docker images to GHCR
2. **deploy-staging**: Auto-deploy to staging (if main branch)
3. **approval**: Wait for manual approval (environment protection)
4. **deploy-production**: Deploy to production (requires approval)

**Duration**: ~20-30 minutes (build) + manual approval wait

**Artifacts**:
- Docker images in GitHub Container Registry
- Deployment summary in GitHub deployments

### 3. **integration-test.yml** - Integration Tests
**Trigger**: Pull requests to `main` or `develop`, push to `main`

**Services Started**:
- PostgreSQL (test database)
- Redis (test cache)
- Backend Flask app
- Frontend Vite server

**Tests**:
- Backend integration tests
- Frontend E2E tests
- Docker build validation
- Docker Compose validation

**Duration**: ~20-25 minutes

## Environment Configuration

### GitHub Secrets (Required)

Set these in **Settings → Secrets and variables → Actions**:

```
AWS_ACCESS_KEY_ID              # AWS IAM user key
AWS_SECRET_ACCESS_KEY          # AWS IAM user secret
AWS_REGION                     # AWS region (e.g., us-east-1)
EC2_HOST                       # EC2 instance domain/IP
EC2_USER                       # SSH user (ubuntu, ec2-user, etc.)
EC2_SSH_KEY                    # Private SSH key (PEM format)
SLACK_WEBHOOK                  # Slack webhook for notifications (optional)
```

### GitHub Variables (Public)

Set these in **Settings → Variables → Actions**:

```
REGISTRY                       # Container registry (ghcr.io)
IMAGE_NAME                     # Image name (owner/repo)
```

## Local Testing

### Test CI Locally with act

```bash
# Install act
brew install act

# Run all workflows
act push

# Run specific workflow
act -j backend-lint

# Run with secrets
act -s AWS_ACCESS_KEY_ID=xxx -s AWS_SECRET_ACCESS_KEY=yyy
```

### Docker Build Test

```bash
# Test backend build
docker build -f Dockerfile.backend -t postpilot-backend:test .

# Test frontend build
docker build -f frontend/Dockerfile -t postpilot-frontend:test ./frontend

# Test Docker Compose
docker-compose up -d
docker-compose ps
```

## Deployment Process

### Automatic (main branch)

```
1. Code pushed to main
2. CI jobs run (lint, tests, security)
3. If CI passes:
   - Docker images built
   - Push to GHCR
   - Deploy to staging
   - Run smoke tests
4. Wait for manual approval (GitHub environment)
5. Deploy to production
6. Run health checks and smoke tests
```

### Manual Trigger

Navigate to **Actions → CD - Build & Deploy to Production → Run workflow**

Select:
- Branch: `main`
- Environment: `staging` or `production`

## Monitoring Deployments

### GitHub UI
- **Actions tab**: See workflow runs and logs
- **Deployments**: Track production deployments
- **Environments**: View protection rules and deployment history

### Slack Notifications
Deployment status posts to Slack channel:
- ✅ Successful deployments
- ❌ Failed deployments
- ⏳ Approval needed

### Logs Location
- Build logs: GitHub Actions UI
- Application logs: `docker compose logs`
- Server logs: SSH into EC2

## Debugging Failures

### Workflow Failed

1. Click the failed job in GitHub Actions
2. Expand the step that failed
3. Check logs for error message
4. Common issues:
   - Python/Node version mismatch
   - Missing secrets
   - Database connection timeout
   - Docker build context issues

### Deployment Failed

1. Check AWS credentials in secrets
2. Verify EC2 instance is running
3. Test SSH access manually:
   ```bash
   ssh -i deploy_key.pem ec2-user@api.postpilot.com
   docker-compose ps
   ```
4. Check application logs: `docker compose logs -f`

### Health Check Failed

1. SSH into EC2
2. Check service status:
   ```bash
   docker compose ps
   docker compose logs backend -f
   ```
3. Test endpoints:
   ```bash
   curl http://localhost:5000/health
   curl http://localhost:5173/
   ```

## Best Practices

### Code Quality
- ✅ All tests must pass before merging
- ✅ Code coverage should be >80%
- ✅ No security vulnerabilities
- ✅ Type checking with mypy/TypeScript

### Deployment
- ✅ Always deploy to staging first
- ✅ Review logs before approving production
- ✅ Keep rollback procedure ready
- ✅ Monitor first 30 minutes after deploy

### Secrets Management
- ✅ Never log secrets
- ✅ Use GitHub Secrets for all sensitive data
- ✅ Rotate secrets regularly
- ✅ Different secrets per environment

### Performance
- ✅ Use Docker layer caching
- ✅ Minimize base image size
- ✅ Cache dependencies (pip, npm)
- ✅ Parallel jobs where possible

## Customization

### Add Custom Step

Edit the workflow YAML and add a new step:

```yaml
- name: Custom Step
  run: |
    echo "Custom command"
    npm run custom:command
```

### Add New Environment

1. Create new environment in GitHub: **Settings → Environments**
2. Add protection rules (required reviewers, branches)
3. Add environment-specific secrets
4. Update deployment job to use new environment

### Change Deployment Target

Update `deploy.yml`:
- Change `EC2_HOST` secret to new server
- Or add different deployment job for different provider
- Support multiple cloud providers (AWS, GCP, Azure)

## References

- [GitHub Actions Documentation](https://docs.github.com/actions)
- [Docker Documentation](https://docs.docker.com)
- [act - Run GitHub Actions locally](https://github.com/nektos/act)

## Support

For issues or questions:
1. Check GitHub Actions logs
2. Review this README
3. Check DEPLOYMENT.md for infrastructure details
4. Open an issue in the repository
