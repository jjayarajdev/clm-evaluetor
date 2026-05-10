---
name: seed-data
description: Seed the database with demo data for local development and testing
allowed-tools: Bash
---

# Seed Database

Run all seed scripts in order to populate the database with demo data.

## Steps

1. Seed core data (tenants, users, contracts with AI processing):
```bash
cd backend && uv run python -m scripts.seed_data
```

2. Seed relationship governance data (organizations, relationships, KPIs, perception scores, improvements):
```bash
cd backend && uv run python -m scripts.seed_relationship_governance
```

3. Verify seeding by checking login works:
```bash
curl -s http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Login OK: {d[\"user\"][\"username\"]} ({d[\"user\"][\"role\"]})')"
```

4. Report what was seeded: tenant count, user count, contract count.
