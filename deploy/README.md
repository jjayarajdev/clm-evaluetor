# CLM Deployment

This directory contains deployment configurations for the CLM platform.

## Quick Start

### Local Docker Deployment

```bash
# From project root
cd /path/to/clm

# Set OpenAI API key
export OPENAI_API_KEY=your-key

# Start services
docker-compose up -d

# Run migrations (first time)
docker-compose --profile setup up migrations

# Seed demo data
docker-compose exec backend python -m scripts.seed_data

# Access
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
```

### Production Deployment (AWS)

```bash
# On EC2 instance
cd ~/clm/deploy

# Create .env
cat > .env << EOF
POSTGRES_USER=clm
POSTGRES_PASSWORD=secure-password
POSTGRES_DB=clm
OPENAI_API_KEY=your-key
SECRET_KEY=$(openssl rand -hex 32)
EOF

# Deploy
docker-compose -f docker-compose.prod.yml up -d

# Migrate & seed
docker-compose -f docker-compose.prod.yml exec -T backend alembic upgrade head
docker-compose -f docker-compose.prod.yml exec -T backend python -m scripts.seed_data

# Access: http://your-ec2-ip
```

## Demo Credentials

| Tenant | Username | Password |
|--------|----------|----------|
| Acme Corp | admin | admin123 |
| Acme Corp | legal | legal123 |
| TechStart | techstart_admin | admin123 |
| LegalCo | legalco_admin | admin123 |
| System | superadmin | admin123 |

## Multi-environment deploys (staging + prod)

Use `env-deploy.sh` to target staging and prod safely from the same laptop.
The wrapper reads `environments.env` (gitignored — copy from
`environments.env.example`) and refuses to run if the target env is missing.
Prod deploys require typing `DEPLOY PROD` to confirm; staging deploys go
through unprompted.

```bash
# One-time setup
cp deploy/environments.env.example deploy/environments.env
# fill in STAGING_IP (and PROD_IP if not already there)
chmod 400 ~/.ssh/clm-staging-key.pem

# Daily flow
./deploy/env-deploy.sh staging            # deploy current branch to staging
./deploy/env-deploy.sh staging --status   # check what's running
./deploy/env-deploy.sh staging --logs     # tail backend logs

# Before deploying to prod, always:
./deploy/env-deploy.sh prod --dump        # snapshot the prod DB
./deploy/env-deploy.sh prod               # then deploy (requires confirmation)
```

**Recommended flow when shipping a feature branch:**

1. Merge feature → dev locally
2. `./deploy/env-deploy.sh staging` — deploy dev to staging
3. Smoke-test on staging
4. Merge dev → release locally
5. `./deploy/env-deploy.sh prod --dump` — fresh DB snapshot
6. `./deploy/env-deploy.sh prod` — deploy release to prod

See `../docs/ROLLBACK.md` for what to do if a prod deploy goes sideways.

## Files

- `docker-compose.prod.yml` — production Docker Compose configuration
- `AWS_DEPLOYMENT.md` — full AWS EC2 provisioning guide (one-time)
- `.env.example` — environment variable template for the box's `.env`
- `environments.env.example` — multi-env target config template (for `env-deploy.sh`)
- `env-deploy.sh` — multi-env deploy wrapper
- `push-to-aws.sh` — low-level "rsync + deploy" called by `env-deploy.sh`
- `deploy.sh` — runs on the EC2 box itself (called over SSH)

## Common Commands

```bash
# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Restart services
docker-compose -f docker-compose.prod.yml restart

# Stop services
docker-compose -f docker-compose.prod.yml down

# Check status
docker-compose -f docker-compose.prod.yml ps
```

## Troubleshooting

See `AWS_DEPLOYMENT.md` for detailed troubleshooting steps.
