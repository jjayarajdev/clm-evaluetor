---
name: smoke-test
description: Quick smoke test to verify all major API endpoints are responding correctly
allowed-tools: Bash
---

# Smoke Test

Hit every major API subsystem and report pass/fail status.

## Steps

1. Login and get token:
```bash
TOKEN=$(curl -s http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

2. Test each endpoint (expect 200 with valid JSON):

| # | Endpoint | Description |
|---|----------|-------------|
| 1 | `GET /api/auth/me` | Auth session |
| 2 | `GET /api/dashboard/stats` | Dashboard stats |
| 3 | `GET /api/contracts` | Contract list |
| 4 | `GET /api/renewals` | Renewals |
| 5 | `GET /api/obligations` | Obligations |
| 6 | `GET /api/organizations` | Organizations |
| 7 | `GET /api/relationships` | Relationships |
| 8 | `GET /api/kpis` | KPIs |
| 9 | `GET /api/improvements` | Improvements |
| 10 | `GET /api/surveys/templates` | Survey templates |

3. For each endpoint, run:
```bash
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ENDPOINT -H "Authorization: Bearer $TOKEN")
```

4. Report results as a table with pass/fail for each endpoint.
