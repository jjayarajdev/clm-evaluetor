---
name: deploy
description: Deploy backend and/or frontend to AWS EC2 production server
disable-model-invocation: true
allowed-tools: Bash
---

# Deploy to AWS

Deploy the application to the EC2 production server at `52.21.204.211`.

**IMPORTANT:** Always confirm with the user before executing deployment commands.

## Arguments
- `backend` — deploy backend only
- `frontend` — deploy frontend only
- `all` or no argument — deploy both

## Backend Deployment
```bash
ssh -i ~/.ssh/clm-demo-key.pem ec2-user@52.21.204.211 "cd ~/clm/deploy && docker-compose -f docker-compose.prod.yml up -d --build backend"
```

## Frontend Deployment
1. Copy updated source files to server
2. Build and deploy:
```bash
ssh -i ~/.ssh/clm-demo-key.pem ec2-user@52.21.204.211 "cd ~/clm/deploy && docker-compose -f docker-compose.prod.yml build --no-cache frontend && docker-compose -f docker-compose.prod.yml up -d frontend"
```

## Post-Deploy Verification
```bash
ssh -i ~/.ssh/clm-demo-key.pem ec2-user@52.21.204.211 "curl -s http://localhost/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"admin123\"}' | python3 -c \"import sys,json; print('OK' if 'access_token' in json.load(sys.stdin) else 'FAIL')\""
```

## Key Rules
- ALWAYS use `-f docker-compose.prod.yml` — plain `docker-compose` uses wrong file
- `docker-compose up -d` does NOT rebuild — use `--build` for backend
- Frontend requires `--no-cache` to pick up source changes
- Run `alembic upgrade head` after model changes
