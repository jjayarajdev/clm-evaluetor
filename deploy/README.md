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

## Files

- `docker-compose.prod.yml` - Production Docker Compose configuration
- `AWS_DEPLOYMENT.md` - Full AWS EC2 deployment guide
- `.env.example` - Environment variable template

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
