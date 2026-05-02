---
name: validate
description: Run comprehensive feature validation across the entire Evaluetor platform
allowed-tools: Bash, Read, Grep
---

# Feature Validation

Systematically validate all platform features by testing API endpoints and checking responses.

## Arguments
- No args: run full validation
- `auth` — authentication flows only
- `contracts` — contract lifecycle only
- `governance` — relationship governance only
- `admin` — super admin features only

## Validation Flow

### 1. Authentication
- Login with each demo user (admin, legal, techstart_admin, superadmin)
- Verify JWT tokens contain correct role and tenant_id
- Verify tenant isolation (Acme user cannot see TechStart data)

### 2. Contract Lifecycle
- List contracts (GET /api/contracts)
- Get contract detail with clauses, obligations, risks
- Search contracts (POST /api/contracts/search)
- Verify contract links and suggested links

### 3. Post-Signing
- Renewals list (GET /api/renewals)
- Compliance status (GET /api/compliance/status)
- SLA performance (GET /api/sla-performance)
- Obligations (GET /api/obligations)

### 4. AI Features
- Contract Q&A (POST /api/query)
- Chat sessions (GET /api/chat/sessions)

### 5. Relationship Governance
- Organizations (GET /api/organizations)
- Relationships with team (GET /api/relationships, GET /api/relationships/{id})
- KPIs and perception scores (GET /api/kpis)
- Gap analysis (GET /api/kpis/gap-summary)
- Improvements (GET /api/improvements)
- Surveys (GET /api/surveys/templates, GET /api/surveys/instances)

### 6. Admin Features
- Dashboard stats (GET /api/dashboard/admin)
- Tenant management (GET /api/tenants)
- Global users (GET /api/users)

## Reporting
For each endpoint, report: endpoint, HTTP status, response validity (has expected fields), and any errors.
Present results as a summary table with pass/fail counts.

Reference: `docs/VALIDATION_TEST_PLAN.md` for detailed test scenarios.
