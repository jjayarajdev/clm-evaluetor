# AWS Deployment Guide

Deploy CLM Platform to AWS EC2 for prospect demos.

## Prerequisites

- AWS CLI configured (`aws configure`)
- SSH key pair in AWS (or create one below)

## Quick Start (15-20 minutes)

### Step 1: Launch EC2 Instance

```bash
# Set your preferred region
export AWS_REGION=us-east-1

# Create security group
aws ec2 create-security-group \
    --group-name clm-demo-sg \
    --description "CLM Platform Demo" \
    --region $AWS_REGION

# Get security group ID
SG_ID=$(aws ec2 describe-security-groups \
    --group-names clm-demo-sg \
    --query 'SecurityGroups[0].GroupId' \
    --output text \
    --region $AWS_REGION)

# Allow SSH, HTTP, HTTPS
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 22 --cidr 0.0.0.0/0 --region $AWS_REGION
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 80 --cidr 0.0.0.0/0 --region $AWS_REGION
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 443 --cidr 0.0.0.0/0 --region $AWS_REGION

# Create key pair (if you don't have one)
aws ec2 create-key-pair \
    --key-name clm-demo-key \
    --query 'KeyMaterial' \
    --output text \
    --region $AWS_REGION > ~/.ssh/clm-demo-key.pem
chmod 400 ~/.ssh/clm-demo-key.pem

# Launch EC2 instance (Amazon Linux 2023, t3.medium)
# t3.medium: 2 vCPU, 4GB RAM - good for demos
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id resolve:ssm:/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64 \
    --instance-type t3.medium \
    --key-name clm-demo-key \
    --security-group-ids $SG_ID \
    --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=clm-demo}]' \
    --query 'Instances[0].InstanceId' \
    --output text \
    --region $AWS_REGION)

echo "Instance ID: $INSTANCE_ID"

# Wait for instance to be running
aws ec2 wait instance-running --instance-ids $INSTANCE_ID --region $AWS_REGION

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text \
    --region $AWS_REGION)

echo "Public IP: $PUBLIC_IP"
echo "SSH: ssh -i ~/.ssh/clm-demo-key.pem ec2-user@$PUBLIC_IP"
```

### Step 2: Connect and Setup Docker

```bash
# SSH into the instance
ssh -i ~/.ssh/clm-demo-key.pem ec2-user@$PUBLIC_IP

# Install Docker
sudo dnf update -y
sudo dnf install -y docker git
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Log out and back in for docker group to take effect
exit
```

### Step 3: Deploy Application

```bash
# SSH back in
ssh -i ~/.ssh/clm-demo-key.pem ec2-user@$PUBLIC_IP

# Create project directory
mkdir -p ~/clm

# Option A: Clone from GitHub
git clone https://github.com/YOUR_ORG/clm.git ~/clm
cd ~/clm/deploy

# Option B: Copy files via SCP (from local machine)
# scp -i ~/.ssh/clm-demo-key.pem -r /path/to/clm ec2-user@$PUBLIC_IP:~/

# Create .env file
cat > .env << 'EOF'
POSTGRES_USER=clm
POSTGRES_PASSWORD=your-secure-password-here
POSTGRES_DB=clm
OPENAI_API_KEY=your-openai-key-here
SECRET_KEY=$(openssl rand -hex 32)
LOG_LEVEL=INFO
EOF

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be ready (30 seconds)
sleep 30

# Run database migrations
docker-compose -f docker-compose.prod.yml exec -T backend alembic upgrade head

# Seed demo data
docker-compose -f docker-compose.prod.yml exec -T backend python -m scripts.seed_data
```

### Step 4: Access Application

Open in browser: `http://<your-ec2-public-ip>`

## Demo Credentials

After seeding, the following multi-tenant demo users are available:

| Tenant | Username | Password | Role | Contracts |
|--------|----------|----------|------|-----------|
| Acme Corp | admin | admin123 | Admin | 4 contracts |
| Acme Corp | legal | legal123 | Legal | 4 contracts |
| TechStart | techstart_admin | admin123 | Admin | 2 contracts |
| LegalCo | legalco_admin | admin123 | Admin | 2 contracts |
| (System) | superadmin | admin123 | Super Admin | All |

Each tenant sees only their own contracts, demonstrating multi-tenancy isolation.

## Alternative: Copy Files via SCP

If your repo isn't on GitHub, copy files directly:

```bash
# From your local machine
cd /Users/jjayaraj/workspaces/studios/clm

# Copy entire project
scp -i ~/.ssh/clm-demo-key.pem -r . ec2-user@$PUBLIC_IP:~/clm/

# Or just the essential files
scp -i ~/.ssh/clm-demo-key.pem -r backend frontend deploy ec2-user@$PUBLIC_IP:~/clm/
```

## Management Commands

```bash
# View logs
./deploy.sh logs

# View specific service logs
./deploy.sh logs backend
./deploy.sh logs frontend

# Restart services
./deploy.sh restart

# Stop services
./deploy.sh stop

# Check status
./deploy.sh status
```

## Adding HTTPS (Optional)

For production, add SSL with Let's Encrypt:

```bash
# Install certbot
sudo dnf install -y certbot

# Get certificate (replace with your domain)
sudo certbot certonly --standalone -d demo.yourcompany.com

# Copy certs to deploy folder
sudo cp /etc/letsencrypt/live/demo.yourcompany.com/fullchain.pem ~/clm/deploy/nginx/ssl/
sudo cp /etc/letsencrypt/live/demo.yourcompany.com/privkey.pem ~/clm/deploy/nginx/ssl/

# Update nginx config and restart
./deploy.sh restart
```

## Cost Estimate

| Resource | Type | Monthly Cost |
|----------|------|--------------|
| EC2 | t3.medium | ~$30 |
| EBS | 30GB gp3 | ~$3 |
| Data Transfer | ~10GB | ~$1 |
| **Total** | | **~$35-50/month** |

## Cleanup

To delete everything:

```bash
# Stop and remove containers
./deploy.sh stop

# Terminate EC2 instance
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $AWS_REGION

# Delete security group (after instance is terminated)
aws ec2 delete-security-group --group-id $SG_ID --region $AWS_REGION

# Delete key pair (optional)
aws ec2 delete-key-pair --key-name clm-demo-key --region $AWS_REGION
rm ~/.ssh/clm-demo-key.pem
```

## Troubleshooting

### Services not starting
```bash
# Check logs
./deploy.sh logs

# Check Docker status
docker ps -a

# Check disk space
df -h
```

### Database connection issues
```bash
# Check if postgres is running
docker compose -f docker-compose.prod.yml ps postgres

# Check postgres logs
docker compose -f docker-compose.prod.yml logs postgres
```

### Frontend shows blank page
```bash
# Check nginx logs
docker compose -f docker-compose.prod.yml logs frontend

# Verify API is accessible
curl http://localhost/api/health
```

### "Invalid input value for enum" errors
This happens when Python enum values don't match PostgreSQL enum values.

```bash
# Check which values are missing
docker compose -f docker-compose.prod.yml exec -T backend python -c "
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings

async def check():
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        result = await conn.execute(text(\"SELECT unnest(enum_range(NULL::clausetype))\"))
        print('clausetype values:', [r[0] for r in result.fetchall()])
    await engine.dispose()

asyncio.run(check())
"

# Add missing enum value (example: adding 'other' to clausetype)
docker compose -f docker-compose.prod.yml exec -T backend python -c "
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings

async def fix():
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.execute(text(\"ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'other'\"))
        print('Added missing enum value')
    await engine.dispose()

asyncio.run(fix())
"
```

### Re-seeding database
```bash
# Clear existing data and re-seed
docker compose -f docker-compose.prod.yml exec -T backend python -c "
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings

async def clear():
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.execute(text('TRUNCATE clauses, contracts, users, tenants CASCADE'))
        print('Tables cleared')
    await engine.dispose()

asyncio.run(clear())
"

# Re-seed
docker compose -f docker-compose.prod.yml exec -T backend python -m scripts.seed_data
```

### Verifying deployment
```bash
# Test login
curl -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Should return access_token and user info
```
