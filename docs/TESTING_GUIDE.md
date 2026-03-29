# CLM Testing Guide

> Step-by-step guide to test all implemented functionalities.
> **Current state:** 44 routers, ~405 API endpoints, 37 frontend pages.

---

## Table of Contents

1. [Prerequisites & Setup](#1-prerequisites--setup)
2. [Testing Authentication](#2-testing-authentication)
3. [Testing Contract Upload & Processing](#3-testing-contract-upload--processing)
4. [Testing Contract Q&A](#4-testing-contract-qa)
5. [Testing Chat Sessions API](#5-testing-chat-sessions-api)
6. [Testing Obligations](#6-testing-obligations)
7. [Testing SLA Management](#7-testing-sla-management)
8. [Testing Renewals & Vendors](#8-testing-renewals--vendors)
9. [Testing Alerts & Notifications](#9-testing-alerts--notifications)
10. [Testing Scheduler & Master Data](#10-testing-scheduler--master-data)
11. [Testing Connectors & Monitor](#11-testing-connectors--monitor)
12. [Testing Relationship Governance](#12-testing-relationship-governance)
13. [Testing Admin UI](#13-testing-admin-ui)
14. [Testing Business Units](#14-testing-business-units)
15. [Testing External Portal & Contract Sharing](#15-testing-external-portal--contract-sharing)
16. [Testing Notification Rules](#16-testing-notification-rules)
17. [Testing Auto-Link Detection](#17-testing-auto-link-detection)
18. [Testing Governance Bridge](#18-testing-governance-bridge)
19. [Testing ServiceNow Integration](#19-testing-servicenow-integration)
20. [End-to-End Test Scenarios](#20-end-to-end-test-scenarios)

---

## 1. Prerequisites & Setup

### Start All Services

```bash
# Terminal 1: Start Docker services (PostgreSQL, ChromaDB)
docker-compose up -d

# Verify services are running
docker-compose ps
```

```bash
# Terminal 2: Start Backend
cd backend

# Install dependencies (if not done)
uv sync

# Run migrations (if not done)
uv run alembic upgrade head

# Start server
uv run uvicorn app.main:app --reload --port 8000
```

```bash
# Terminal 3: Start Frontend
cd frontend

# Install dependencies (if not done)
npm install

# Start dev server
npm run dev
```

### Seed Data

```bash
cd backend

# Core data: tenants, users, contracts
uv run python -m scripts.seed_data

# Governance data: orgs, relationships, KPIs, scores
uv run python -m scripts.seed_relationship_governance

# Rich governance demo data (KR8 relationship)
uv run python -m scripts.seed_kr8_relationship

# Business unit hierarchy
uv run python -m scripts.seed_business_units

# Compliance rules
uv run python -m scripts.seed_compliance_rules

# Distribute contracts across tenants
uv run python -m scripts.seed_contract_distribution

# ServiceNow integration data
uv run python -m scripts.seed_servicenow
```

### Demo Credentials

| Tenant | Username | Password | Role |
|--------|----------|----------|------|
| Acme Corp | admin | admin123 | Admin |
| Acme Corp | legal | legal123 | Legal |
| TechStart | techstart_admin | admin123 | Admin |
| LegalCo | legalco_admin | admin123 | Admin |
| (System) | superadmin | admin123 | Super Admin |

### Access Points

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/api/docs |
| ReDoc | http://localhost:8000/api/redoc |
| Health Check | http://localhost:8000/api/health |

### Get Authentication Token

```bash
# Login to get JWT token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Save the token for subsequent requests
export TOKEN="<access_token_from_response>"
```

---

## 2. Testing Authentication

### Health Check

```bash
curl http://localhost:8000/api/health
# Expected: {"status": "healthy", "version": "0.1.0", "services": {...}}
```

### Login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### Get Current User

```bash
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### Using Swagger UI (Recommended for Manual Testing)

1. Open http://localhost:8000/api/docs
2. Click "Authorize" button (top right)
3. Enter: `Bearer <your_token>`
4. Now you can test any endpoint interactively

---

## 3. Testing Contract Upload & Processing

### Using Test Contracts

```bash
# Navigate to test contracts
ls backend/data/sample_contracts/test_contracts/

# Convert markdown to PDF (requires pandoc)
pandoc MSA_TechServices_Acme.md -o MSA_TechServices_Acme.pdf
```

### Upload a Single Contract

```bash
curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@backend/data/sample_contracts/test_contracts/MSA_TechServices_Acme.pdf"
```

### Upload Multiple Contracts (Batch)

```bash
curl -X POST http://localhost:8000/api/contracts/upload/batch \
  -H "Authorization: Bearer $TOKEN" \
  -F "files=@contract1.pdf" \
  -F "files=@contract2.pdf"
```

### Upload ZIP Archive

```bash
curl -X POST http://localhost:8000/api/contracts/upload/zip \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@contracts.zip"
```

### Check Processing Status

```bash
curl -X GET http://localhost:8000/api/contracts/<contract_id> \
  -H "Authorization: Bearer $TOKEN"
```

Watch for `status` field: `uploaded` -> `processing` -> `completed`

### Trigger Processing Manually

```bash
curl -X POST http://localhost:8000/api/contracts/<contract_id>/process \
  -H "Authorization: Bearer $TOKEN"
```

### Run Deep Analysis

```bash
curl -X POST http://localhost:8000/api/contracts/<contract_id>/analyze \
  -H "Authorization: Bearer $TOKEN"
```

### List Contracts

```bash
curl -X GET "http://localhost:8000/api/contracts?page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"
```

### Get Filter Options

```bash
curl -X GET http://localhost:8000/api/contracts/filter-options \
  -H "Authorization: Bearer $TOKEN"
```

---

## 4. Testing Contract Q&A

### Ask a Question

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the payment terms in my contracts?"
  }'
```

### Ask About a Specific Contract

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the termination notice period?",
    "contract_id": "<contract_id>"
  }'
```

### Get Query Suggestions

```bash
curl -X GET http://localhost:8000/api/query/suggestions \
  -H "Authorization: Bearer $TOKEN"
```

### Run Specific Analysis

```bash
curl -X POST http://localhost:8000/api/query/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "contract_id": "<contract_id>",
    "analysis_type": "risk"
  }'
```

---

## 5. Testing Chat Sessions API

### Create a Chat Session

```bash
curl -X POST http://localhost:8000/api/chat/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "contract_id": "<contract_id>"
  }'
```

### List Chat Sessions

```bash
# Verify ordering by updated_at desc and tenant isolation
curl -X GET http://localhost:8000/api/chat/sessions \
  -H "Authorization: Bearer $TOKEN"
```

### Get Session with Messages

```bash
# Verify message ordering and JSON fields (sources, follow_ups, visualizations)
curl -X GET http://localhost:8000/api/chat/sessions/<session_id> \
  -H "Authorization: Bearer $TOKEN"
```

### Update Session Title

```bash
curl -X PATCH http://localhost:8000/api/chat/sessions/<session_id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Updated session title"}'
```

### Delete Session

```bash
# Verify cascade deletes all messages
curl -X DELETE http://localhost:8000/api/chat/sessions/<session_id> \
  -H "Authorization: Bearer $TOKEN"
```

### Add Message to Session

```bash
# Verify auto-title: first user message sets title to first 60 chars
curl -X POST http://localhost:8000/api/chat/sessions/<session_id>/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "What are the key SLA terms in this contract?"
  }'
```

### Key Test Scenarios

1. **Multi-tenant isolation:** Login as User A and User B (different tenants), verify each user only sees their own sessions
2. **Session auto-title:** Create a session, send the first user message, verify the session title is set to the first 60 characters of that message
3. **Contract scoping:** Create a session with a `contract_id`, verify the session is linked to the correct contract
4. **Message persistence:** Send a message, retrieve the session, verify `sources`, `follow_ups`, and `visualizations` are stored as JSON
5. **Cascade delete:** Create a session with multiple messages, delete the session, verify all messages are also removed

---

## 6. Testing Obligations

### List Obligations

```bash
curl -X GET "http://localhost:8000/api/obligations/?contract_id=<contract_id>" \
  -H "Authorization: Bearer $TOKEN"
```

### Update Obligation Status

```bash
curl -X PUT http://localhost:8000/api/obligations/<obligation_id>/status \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "completed", "notes": "Verified and completed"}'
```

### Update RAG Status

```bash
curl -X PUT http://localhost:8000/api/obligations/<obligation_id>/rag \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"rag_status": "green", "compliance_notes": "Fully compliant"}'
```

### Get Compliance Rates

```bash
curl -X GET http://localhost:8000/api/obligations/compliance/rates \
  -H "Authorization: Bearer $TOKEN"
```

---

## 7. Testing SLA Management

### List SLAs for a Contract

```bash
curl -X GET http://localhost:8000/api/sla/<contract_id> \
  -H "Authorization: Bearer $TOKEN"
```

### Create a New SLA

```bash
curl -X POST http://localhost:8000/api/sla/<contract_id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sla_name": "System Availability",
    "metric_type": "uptime_percentage",
    "metric_unit": "percentage",
    "target_value": 99.9,
    "target_operator": ">=",
    "severity": "critical",
    "has_penalty": true,
    "penalty_type": "service_credit",
    "penalty_value": 5.0,
    "measurement_period": "monthly"
  }'
```

### Log SLA Performance

```bash
curl -X POST http://localhost:8000/api/sla/<contract_id>/performance/<sla_id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "actual_value": 99.7,
    "notes": "Monthly measurement"
  }'
```

### Get SLA Compliance Summary

```bash
curl -X GET http://localhost:8000/api/sla/compliance/summary \
  -H "Authorization: Bearer $TOKEN"
```

### Get Active Breaches

```bash
curl -X GET http://localhost:8000/api/sla/breaches/active \
  -H "Authorization: Bearer $TOKEN"
```

---

## 8. Testing Renewals & Vendors

### Renewal Calendar

```bash
curl -X GET http://localhost:8000/api/renewals/calendar \
  -H "Authorization: Bearer $TOKEN"
```

### At-Risk Contracts

```bash
curl -X GET http://localhost:8000/api/renewals/at-risk \
  -H "Authorization: Bearer $TOKEN"
```

### AI Renewal Recommendation

```bash
curl -X GET http://localhost:8000/api/renewals/<contract_id>/recommendation \
  -H "Authorization: Bearer $TOKEN"
```

### List Vendors with Scores

```bash
curl -X GET http://localhost:8000/api/vendors \
  -H "Authorization: Bearer $TOKEN"
```

### Vendor Performance Detail

```bash
curl -X GET http://localhost:8000/api/vendors/<vendor_name>/performance \
  -H "Authorization: Bearer $TOKEN"
```

### Compare Vendors

```bash
curl -X GET "http://localhost:8000/api/vendors/compare?vendors=Vendor1&vendors=Vendor2" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 9. Testing Alerts & Notifications

### Alert Dashboard

```bash
curl -X GET http://localhost:8000/api/alerts/dashboard \
  -H "Authorization: Bearer $TOKEN"
```

### List Alerts

```bash
curl -X GET "http://localhost:8000/api/alerts?active_only=true&days=30" \
  -H "Authorization: Bearer $TOKEN"
```

### Get Critical Alerts

```bash
curl -X GET http://localhost:8000/api/alerts/critical \
  -H "Authorization: Bearer $TOKEN"
```

### Acknowledge an Alert

```bash
curl -X POST http://localhost:8000/api/alerts/<alert_id>/acknowledge \
  -H "Authorization: Bearer $TOKEN"
```

### Resolve an Alert

```bash
curl -X POST http://localhost:8000/api/alerts/<alert_id>/resolve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Issue addressed with vendor"}'
```

### Bulk Alert Action

```bash
curl -X POST http://localhost:8000/api/alerts/bulk-action \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_ids": ["id1", "id2"],
    "action": "acknowledge",
    "notes": "Batch acknowledgement"
  }'
```

### List Notifications

```bash
curl -X GET "http://localhost:8000/notifications/?days=7&limit=50" \
  -H "Authorization: Bearer $TOKEN"
```

### Send Test Notification

```bash
curl -X POST "http://localhost:8000/notifications/test?recipient_email=test@example.com" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 10. Testing Scheduler & Master Data

### Scheduler Status

```bash
curl -X GET http://localhost:8000/api/admin/scheduler/status \
  -H "Authorization: Bearer $TOKEN"
```

### List Scheduled Jobs

```bash
curl -X GET http://localhost:8000/api/admin/scheduler/jobs \
  -H "Authorization: Bearer $TOKEN"
```

### Trigger Manual Job Run

```bash
curl -X POST http://localhost:8000/api/admin/scheduler/jobs/sla_comparison/run \
  -H "Authorization: Bearer $TOKEN"
```

### View Job History

```bash
curl -X GET "http://localhost:8000/api/admin/scheduler/jobs/sla_comparison/history?limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

### Update Job Configuration

```bash
curl -X PATCH http://localhost:8000/api/admin/scheduler/jobs/sla_comparison \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"interval_seconds": 1800, "is_enabled": true}'
```

### Seed All Master Data

```bash
curl -X POST http://localhost:8000/api/admin/master-data/seed-all \
  -H "Authorization: Bearer $TOKEN"
```

### List SLA Master Data

```bash
curl -X GET http://localhost:8000/api/admin/master-data/slas \
  -H "Authorization: Bearer $TOKEN"
```

### List Milestone Master Data

```bash
curl -X GET http://localhost:8000/api/admin/master-data/milestones \
  -H "Authorization: Bearer $TOKEN"
```

### Vector Store Stats

```bash
curl -X GET http://localhost:8000/api/admin/master-data/vector-stats \
  -H "Authorization: Bearer $TOKEN"
```

---

## 11. Testing Connectors & Monitor

### Connector Status

```bash
curl -X GET http://localhost:8000/api/connectors/status \
  -H "Authorization: Bearer $TOKEN"
```

### Get SLA Actuals from External System

```bash
curl -X GET "http://localhost:8000/api/connectors/sla-actuals/<contract_id>" \
  -H "Authorization: Bearer $TOKEN"
```

### Get FX Rate

```bash
curl -X GET "http://localhost:8000/api/connectors/fx/rate?base=USD&target=EUR" \
  -H "Authorization: Bearer $TOKEN"
```

### Run SLA Comparison

```bash
curl -X POST http://localhost:8000/api/connectors/compare/<contract_id> \
  -H "Authorization: Bearer $TOKEN"
```

### Run Event Detection Scan

```bash
curl -X POST http://localhost:8000/monitor/scan \
  -H "Authorization: Bearer $TOKEN"
```

### Run Workflow Processing

```bash
curl -X POST http://localhost:8000/monitor/process \
  -H "Authorization: Bearer $TOKEN"
```

### List Detected Events

```bash
curl -X GET "http://localhost:8000/monitor/events?limit=50" \
  -H "Authorization: Bearer $TOKEN"
```

### Run End-to-End Scenario

```bash
curl -X POST "http://localhost:8000/monitor/run-scenario?scenario=sla_breach" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 12. Testing Relationship Governance

### Organizations

```bash
# List organizations
curl -X GET http://localhost:8000/api/organizations \
  -H "Authorization: Bearer $TOKEN"

# Create organization
curl -X POST http://localhost:8000/api/organizations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "org_type": "customer",
    "industry": "Technology",
    "size": "enterprise",
    "region": "North America"
  }'
```

### Business Relationships

```bash
# Create relationship
curl -X POST http://localhost:8000/api/relationships \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "org_a_id": "<org_id_1>",
    "org_b_id": "<org_id_2>",
    "relationship_type": "vendor",
    "governance_tier": "strategic"
  }'

# Add team member
curl -X POST http://localhost:8000/api/relationships/<rel_id>/team \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "<user_id>",
    "role": "account_manager",
    "responsibilities": ["SLA oversight", "Escalation point"]
  }'
```

### KPI & Perception Scoring

```bash
# Create KPI
curl -X POST http://localhost:8000/api/kpis \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "relationship_id": "<rel_id>",
    "name": "Service Quality",
    "measurement_type": "perception",
    "target_value": 8.0,
    "threshold_amber": 6.0,
    "threshold_red": 4.0
  }'

# Submit perception score
curl -X POST http://localhost:8000/api/kpis/perception-scores \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "kpi_id": "<kpi_id>",
    "scorer_org_id": "<org_id>",
    "score": 7.5,
    "period": "2026-Q1",
    "comments": "Good performance overall"
  }'

# Get perception gaps
curl -X GET http://localhost:8000/api/kpis/<kpi_id>/gaps \
  -H "Authorization: Bearer $TOKEN"
```

### Improvements

```bash
# Generate improvements from gaps
curl -X POST http://localhost:8000/api/improvements/generate-from-gaps \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"relationship_id": "<rel_id>"}'

# List improvements
curl -X GET "http://localhost:8000/api/improvements?relationship_id=<rel_id>" \
  -H "Authorization: Bearer $TOKEN"
```

### Surveys

```bash
# Create survey template
curl -X POST http://localhost:8000/api/surveys/templates \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Quarterly Satisfaction Survey",
    "frequency": "quarterly"
  }'

# Create and send survey instance
curl -X POST http://localhost:8000/api/surveys/instances \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "<template_id>",
    "relationship_id": "<rel_id>",
    "period": "2026-Q1"
  }'
```

---

## 13. Testing Admin UI

### Access Admin Pages

| Page | URL | Purpose |
|------|-----|---------|
| Dashboard | http://localhost:5173/dashboard | Main analytics dashboard |
| Contracts | http://localhost:5173/contracts | Contract list and management |
| Upload | http://localhost:5173/upload | Upload new contracts |
| Q&A | http://localhost:5173/query | Ask questions about contracts |
| Post-Signing | http://localhost:5173/post-signing | Post-signing management |
| Renewals | http://localhost:5173/renewals | Renewal management |
| Vendors | http://localhost:5173/vendors | Vendor scorecards |
| Reports | http://localhost:5173/reports | Compliance reports |
| Users | http://localhost:5173/users | User management |
| Organizations | http://localhost:5173/governance/organizations | Organization management |
| Relationships | http://localhost:5173/governance/relationships | Business relationships |
| KPI Scorecard | http://localhost:5173/governance/kpi-scorecard | KPI perception scores |
| Improvements | http://localhost:5173/governance/improvements | Improvement tracking |
| Surveys | http://localhost:5173/governance/surveys | Survey management |
| Service Portfolio | http://localhost:5173/governance/service-portfolio | Service portfolio |
| Business Units | http://localhost:5173/admin/business-units | Business unit hierarchy |
| External Users | http://localhost:5173/admin/external-users | External user management |
| SLA Config | http://localhost:5173/admin/master-data/slas | SLA master data |
| Milestone Config | http://localhost:5173/admin/master-data/milestones | Milestone master data |
| Scheduler | http://localhost:5173/admin/scheduler | Background job management |
| ServiceNow | http://localhost:5173/admin/servicenow | ServiceNow integration |
| Settings | http://localhost:5173/settings | Langfuse and system settings |
| External Portal | http://localhost:5173/external/contracts?token=TOKEN | External user contract view |

---

## 14. Testing Business Units

Business units support hierarchical organization (parent-child) and are tenant-scoped.

### Seed Business Units

```bash
cd backend && uv run python -m scripts.seed_business_units
```

### List Business Units

```bash
curl -X GET "http://localhost:8000/api/business-units?page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"
```

### Get Business Unit Tree (Hierarchy)

```bash
# Returns hierarchical tree structure with parent-child nesting
curl -X GET http://localhost:8000/api/business-units/tree \
  -H "Authorization: Bearer $TOKEN"
```

### Create a Business Unit

```bash
curl -X POST http://localhost:8000/api/business-units \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Engineering",
    "code": "ENG",
    "description": "Engineering department"
  }'
```

### Create a Child Business Unit (Hierarchy)

```bash
# Create a child under an existing parent
curl -X POST http://localhost:8000/api/business-units \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Frontend Team",
    "code": "ENG-FE",
    "description": "Frontend engineering team",
    "parent_id": "<parent_bu_id>"
  }'
```

### Get a Business Unit with Hierarchy Info

```bash
# Returns parent, children, and full_path
curl -X GET http://localhost:8000/api/business-units/<bu_id> \
  -H "Authorization: Bearer $TOKEN"
```

### Update a Business Unit

```bash
curl -X PUT http://localhost:8000/api/business-units/<bu_id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Engineering Division",
    "description": "Updated description"
  }'
```

### Deactivate a Business Unit

```bash
# Soft-deletes (sets is_active=false). Fails if BU has active children.
curl -X DELETE http://localhost:8000/api/business-units/<bu_id> \
  -H "Authorization: Bearer $TOKEN"
```

### List Users in a Business Unit

```bash
curl -X GET http://localhost:8000/api/business-units/<bu_id>/users \
  -H "Authorization: Bearer $TOKEN"
```

### Get Contract Summary for a Business Unit

```bash
curl -X GET http://localhost:8000/api/business-units/<bu_id>/contracts \
  -H "Authorization: Bearer $TOKEN"
```

### Key Test Scenarios

1. **CRUD operations:** Create, read, update, deactivate a business unit
2. **Hierarchy:** Create a parent BU, create children under it, retrieve tree, verify nesting
3. **Circular reference prevention:** Try setting a child as parent of its ancestor, verify 400 error
4. **Deactivation guard:** Try deactivating a BU with active children, verify 400 error
5. **Duplicate code prevention:** Try creating two BUs with the same `code`, verify 400 error
6. **Tenant isolation:** Login as different tenants, verify each only sees their own BUs
7. **Admin role requirement:** Verify that non-admin users cannot create/update/delete BUs

---

## 15. Testing External Portal & Contract Sharing

External sharing allows internal users to share contracts with external parties (counterparties, auditors) via token-based access. No login is required for external users.

### Seed Data

```bash
# Ensure external users exist (created via invite or seed data)
cd backend && uv run python -m scripts.seed_data
```

### Step 1: Create an External User

```bash
curl -X POST http://localhost:8000/api/external-users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "partner@example.com",
    "full_name": "Jane Partner",
    "company_name": "Partner Corp"
  }'
# Note the external_user_id from response
```

### Step 2: Invite and Share Contracts in One Step

```bash
curl -X POST http://localhost:8000/api/external-users/invite \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "vendor@example.com",
    "full_name": "Bob Vendor",
    "company_name": "Vendor Inc",
    "contract_ids": ["<contract_id_1>", "<contract_id_2>"],
    "can_download": true,
    "can_comment": true,
    "expires_in_days": 30,
    "message": "Please review and comment"
  }'
# Response includes access_token and access_url
```

### Step 3: Share a Single Contract with an Existing External User

```bash
curl -X POST http://localhost:8000/api/contracts/<contract_id>/share \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "external_user_id": "<external_user_id>",
    "can_download": true,
    "can_comment": true,
    "expires_in_days": 30,
    "message": "Please review this contract"
  }'
# Response includes access_token
```

### Step 4: Validate External Access Token (No Auth Required)

```bash
# Use the token from the invite/share response
curl -X GET "http://localhost:8000/api/external/validate?token=<access_token>"
# Returns: external_user info, list of accessible contracts, token expiry
```

### Step 5: List Shared Contracts as External User (No Auth Required)

```bash
curl -X GET "http://localhost:8000/api/external/contracts?token=<access_token>"
# Returns: contract list with metadata and permission flags
```

### Step 6: View a Shared Contract (No Auth Required)

```bash
curl -X GET "http://localhost:8000/api/external/contracts/<contract_id>?token=<access_token>"
# Returns: contract details including clauses (up to 20), permissions, and shared message
```

### Step 7: Download a Shared Contract (No Auth Required)

```bash
curl -X GET "http://localhost:8000/api/external/contracts/<contract_id>/download?token=<access_token>" \
  -o contract.pdf
# Only works if can_download=true on the share
```

### Step 8: List and Add Comments (No Auth Required)

```bash
# List comments (internal comments are hidden from external users)
curl -X GET "http://localhost:8000/api/external/contracts/<contract_id>/comments?token=<access_token>"

# Add a comment as external user
curl -X POST "http://localhost:8000/api/external/contracts/<contract_id>/comments?token=<access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "We have a question about Section 4.2",
    "section_reference": "4.2"
  }'
# Only works if can_comment=true on the share
```

### Managing External Users (Admin)

```bash
# List all external users
curl -X GET "http://localhost:8000/api/external-users?page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"

# Get external user with share count
curl -X GET http://localhost:8000/api/external-users/<external_user_id> \
  -H "Authorization: Bearer $TOKEN"

# View all shares for an external user
curl -X GET http://localhost:8000/api/external-users/<external_user_id>/shares \
  -H "Authorization: Bearer $TOKEN"

# Resend invite with fresh token
curl -X POST "http://localhost:8000/api/external-users/<external_user_id>/resend-invite?expires_in_days=30" \
  -H "Authorization: Bearer $TOKEN"

# Revoke external user access (deactivates user, revokes all shares and tokens)
curl -X DELETE http://localhost:8000/api/external-users/<external_user_id> \
  -H "Authorization: Bearer $TOKEN"
```

### Key Test Scenarios

1. **Full sharing flow:** Create external user, share contract, validate token, view contract as external user
2. **Permission enforcement:** Share with `can_download=false`, verify download returns 403; share with `can_comment=false`, verify comment returns 403
3. **Token expiry:** Create share with `expires_in_days=1`, advance time or wait, verify token rejected
4. **Revocation:** Revoke external user, verify all shares and tokens are invalidated
5. **Internal comment hiding:** Add internal comment as admin, verify external user cannot see it
6. **Duplicate prevention:** Try sharing same contract with same user twice, verify 400 error
7. **Tenant isolation:** Verify external users cannot access contracts from other tenants

---

## 16. Testing Notification Rules

Notification rules define configurable triggers for events like contract expiration, SLA breaches, and obligation deadlines.

### List Rule Templates

```bash
# Get pre-defined templates for quick rule setup
curl -X GET http://localhost:8000/api/notification-rules/templates \
  -H "Authorization: Bearer $TOKEN"
# Returns: 7 templates (contract_expiration, notice_deadline, obligation_due, sla_breach, etc.)
```

### Create a Rule from Template

```bash
# Create a rule from a template (index 0-6)
curl -X POST http://localhost:8000/api/notification-rules/from-template/0 \
  -H "Authorization: Bearer $TOKEN"
# Creates "Contract Expiration Warning" rule with defaults
```

### Create a Custom Rule

```bash
curl -X POST http://localhost:8000/api/notification-rules/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High-Value Contract Expiration",
    "description": "Alert for contracts over $100K expiring in 60 days",
    "event_type": "contract_expiration",
    "days_before": 60,
    "channels": ["email", "in_app"],
    "notify_contract_owner": true,
    "notify_admin": true,
    "min_contract_value": 100000,
    "priority": "critical",
    "respect_business_hours": true,
    "business_hours_start": "09:00",
    "business_hours_end": "17:00"
  }'
```

### List Notification Rules

```bash
# List all active rules
curl -X GET "http://localhost:8000/api/notification-rules/?active_only=true" \
  -H "Authorization: Bearer $TOKEN"

# Filter by event type
curl -X GET "http://localhost:8000/api/notification-rules/?event_type=sla_breach" \
  -H "Authorization: Bearer $TOKEN"
```

### Get a Rule by ID

```bash
curl -X GET http://localhost:8000/api/notification-rules/<rule_id> \
  -H "Authorization: Bearer $TOKEN"
```

### Update a Rule

```bash
curl -X PUT http://localhost:8000/api/notification-rules/<rule_id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "days_before": 45,
    "priority": "high",
    "additional_recipients": ["manager@example.com"]
  }'
```

### Toggle Rule Active/Inactive

```bash
curl -X POST http://localhost:8000/api/notification-rules/<rule_id>/toggle \
  -H "Authorization: Bearer $TOKEN"
# Response: {"success": true, "rule_id": "...", "is_active": false}
```

### Delete a Rule

```bash
curl -X DELETE http://localhost:8000/api/notification-rules/<rule_id> \
  -H "Authorization: Bearer $TOKEN"
```

### Get Rule Statistics

```bash
curl -X GET http://localhost:8000/api/notification-rules/summary/stats \
  -H "Authorization: Bearer $TOKEN"
# Returns: total_rules, active_rules, by_event_type breakdown, total_triggers
```

### Supported Event Types

| Event Type | Description |
|-----------|-------------|
| `contract_expiration` | Contract nearing expiration date |
| `notice_deadline` | Notice period deadline approaching |
| `obligation_due` | Obligation deadline approaching |
| `sla_breach` | SLA threshold breached |
| `sla_warning` | SLA at risk of breach |
| `renewal_reminder` | Auto-renewal date approaching |
| `compliance_overdue` | Compliance requirement overdue |

### Key Test Scenarios

1. **Template creation:** Create rule from each template, verify defaults are applied
2. **Custom rule CRUD:** Create, read, update, delete a custom rule
3. **Toggle active status:** Toggle rule off, verify it does not appear in `active_only=true` list
4. **Filter by event type:** Create rules for different events, verify filtering works
5. **Statistics accuracy:** Create several rules, verify `summary/stats` counts match
6. **Tenant isolation:** Login as different tenants, verify each only sees their own rules
7. **Value filtering:** Create rule with `min_contract_value`, verify it only applies to high-value contracts
8. **Business hours:** Create rule with business hours, verify `respect_business_hours` is stored

---

## 17. Testing Auto-Link Detection

Auto-link detection runs automatically after contract processing. It identifies relationships between contracts (e.g., an addendum referencing its parent MSA) using counterparty matching and AI analysis.

### View Established Contract Links

```bash
# Get approved/established links for a contract
curl -X GET http://localhost:8000/api/contracts/<contract_id>/links \
  -H "Authorization: Bearer $TOKEN"
# Returns links with direction (parent/child), link_type, and linked contract details
```

### View AI-Suggested Links

```bash
# Get AI-suggested links for a contract (pending review)
curl -X GET "http://localhost:8000/api/contracts/<contract_id>/suggested-links" \
  -H "Authorization: Bearer $TOKEN"

# Filter by status
curl -X GET "http://localhost:8000/api/contracts/<contract_id>/suggested-links?status_filter=pending" \
  -H "Authorization: Bearer $TOKEN"
```

### View All Pending Suggestions (Across Contracts)

```bash
curl -X GET "http://localhost:8000/api/contracts/pending-suggestions?limit=50" \
  -H "Authorization: Bearer $TOKEN"
# Returns suggestions grouped by contract with total counts
```

### Approve a Suggested Link

```bash
curl -X POST http://localhost:8000/api/contracts/<contract_id>/suggested-links/<suggestion_id>/review \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "approve"
  }'
# Creates an actual ContractLink and marks suggestion as approved
```

### Reject a Suggested Link

```bash
curl -X POST http://localhost:8000/api/contracts/<contract_id>/suggested-links/<suggestion_id>/review \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "reject",
    "notes": "Not related"
  }'
```

### Modify and Approve a Suggested Link

```bash
curl -X POST http://localhost:8000/api/contracts/<contract_id>/suggested-links/<suggestion_id>/review \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "modify",
    "modified_link_type": "sow"
  }'
# Changes the link type and then approves
```

### Batch Review Suggestions

```bash
curl -X POST http://localhost:8000/api/contracts/<contract_id>/suggested-links/batch-review \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "suggestion_ids": ["<id1>", "<id2>", "<id3>"],
    "action": "approve"
  }'
# Returns: processed count, succeeded count, failed count
```

### Key Test Scenarios

1. **Auto-detection trigger:** Upload an MSA, then upload an addendum with the same counterparty. After processing completes, verify a suggested_link entry appears with a confidence score.
2. **Approve flow:** Review and approve a suggestion, verify a ContractLink is created and the suggestion status changes to `approved`.
3. **Reject flow:** Reject a suggestion, verify status is `rejected` and no link is created.
4. **Modify flow:** Modify a suggestion's link type, verify the created link uses the modified type.
5. **Duplicate prevention:** Approve a suggestion, then try to approve it again. Verify 400 error ("Suggestion already approved").
6. **Batch review:** Select multiple pending suggestions, batch approve, verify counts.
7. **Pending suggestions view:** Verify the cross-contract pending suggestions endpoint returns grouped counts.

---

## 18. Testing Governance Bridge

The Governance Bridge automatically creates governance entities (organizations, relationships, KPIs, improvement points) from contract data during deep analysis. This bridges the gap between contract intelligence and relationship governance.

### Trigger Governance Bridge

The bridge runs automatically during deep analysis:

```bash
# 1. Upload a contract with identifiable counterparty and SLAs
curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@backend/data/sample_contracts/MSA_CareerSource_Executed.pdf"

# 2. Wait for processing to complete, then trigger deep analysis
curl -X POST http://localhost:8000/api/contracts/<contract_id>/analyze \
  -H "Authorization: Bearer $TOKEN"
```

### Verify Organization Auto-Created

```bash
# After deep analysis, verify the counterparty has been created as an organization
curl -X GET http://localhost:8000/api/organizations \
  -H "Authorization: Bearer $TOKEN"
# Look for the counterparty name from the uploaded contract
```

### Verify Relationship Auto-Created

```bash
# Verify a business relationship was created between your org and the counterparty
curl -X GET http://localhost:8000/api/relationships \
  -H "Authorization: Bearer $TOKEN"
# Look for a relationship linking your organization to the counterparty org
```

### Verify KPIs from SLAs

```bash
# If the contract had SLA terms, verify KPIs were created
curl -X GET "http://localhost:8000/api/kpis?relationship_id=<rel_id>" \
  -H "Authorization: Bearer $TOKEN"
# SLA metrics should appear as perception-type KPIs
```

### Verify Improvements from High-Risk Clauses

```bash
# If the contract had high-risk clauses, verify improvement points were generated
curl -X GET "http://localhost:8000/api/improvements?relationship_id=<rel_id>" \
  -H "Authorization: Bearer $TOKEN"
```

### Seed Rich Governance Demo Data

```bash
cd backend && uv run python -m scripts.seed_kr8_relationship
```

### Key Test Scenarios (E2E Governance Bridge)

1. **Upload-to-org flow:** Upload a PDF with a clear counterparty name. After deep analysis, verify an organization was created with matching name.
2. **Upload-to-relationship flow:** Upload contract, verify a business relationship was created between your tenant's org and the counterparty org.
3. **SLA-to-KPI flow:** Upload a contract containing SLA terms (uptime, response time). After analysis, verify KPIs were created from those SLAs.
4. **Risk-to-improvement flow:** Upload a contract with high-risk clauses. After analysis, verify improvement points were generated.
5. **Health score:** After governance entities are created, verify the relationship has a health score calculated from KPI data.
6. **Idempotency:** Run deep analysis twice on the same contract. Verify no duplicate organizations or relationships are created.

---

## 19. Testing ServiceNow Integration

ServiceNow integration provides SLA definition sync, mapping management, and health monitoring. It uses stub endpoints (no live ServiceNow instance required for testing).

### Seed ServiceNow Data

```bash
cd backend && uv run python -m scripts.seed_servicenow
```

### Get ServiceNow Configuration

```bash
curl -X GET http://localhost:8000/api/integrations/servicenow/config \
  -H "Authorization: Bearer $TOKEN"
```

### Create or Update ServiceNow Configuration

```bash
curl -X POST http://localhost:8000/api/integrations/servicenow/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production ServiceNow",
    "base_url": "https://dev12345.service-now.com",
    "auth_type": "basic",
    "credentials": {
      "username": "api_user",
      "password": "api_password"
    },
    "config": {
      "assignment_group": "IT Operations",
      "api_version": "v2"
    }
  }'
```

### Test ServiceNow Connection

```bash
curl -X POST http://localhost:8000/api/integrations/servicenow/config/test \
  -H "Authorization: Bearer $TOKEN"
# Returns: {"healthy": true/false, "message": "..."}
```

### Trigger SLA Definition Sync

```bash
curl -X POST http://localhost:8000/api/integrations/servicenow/sync \
  -H "Authorization: Bearer $TOKEN"
# Returns: {"fetched": N, "created": N, "updated": N, "errors": N}
```

### List SLA Mappings

```bash
curl -X GET http://localhost:8000/api/integrations/servicenow/mappings \
  -H "Authorization: Bearer $TOKEN"
```

### Update an SLA Mapping

```bash
# Map a ServiceNow SLA to a platform SLA
curl -X PUT http://localhost:8000/api/integrations/servicenow/mappings/<mapping_id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "platform_sla_id": "<platform_sla_uuid>",
    "status": "mapped"
  }'

# Ignore a ServiceNow SLA
curl -X PUT http://localhost:8000/api/integrations/servicenow/mappings/<mapping_id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "ignored"
  }'
```

### Super Admin: Overview of All Tenant Configs

```bash
# Login as superadmin first
curl -X GET http://localhost:8000/api/integrations/servicenow/admin/overview \
  -H "Authorization: Bearer $SUPERADMIN_TOKEN"
# Returns: all SNOW configs across tenants with health status and mapping counts
```

### Super Admin: View Integration Logs

```bash
curl -X GET "http://localhost:8000/api/integrations/servicenow/admin/logs?limit=50" \
  -H "Authorization: Bearer $SUPERADMIN_TOKEN"
```

### Key Test Scenarios

1. **Config CRUD:** Create a config, retrieve it, update it, verify changes persist
2. **Connection test:** Run test connection, verify response format
3. **SLA sync:** Trigger sync, verify mappings are created
4. **Mapping workflow:** After sync, list mappings, map one to a platform SLA, ignore another
5. **Super admin oversight:** Login as superadmin, verify overview shows all tenant configs
6. **Log visibility:** Trigger operations, verify logs appear in admin logs endpoint
7. **Tenant isolation:** Verify tenant A cannot see tenant B's ServiceNow config

---

## 20. End-to-End Test Scenarios

### Scenario 1: Full Contract Intelligence Flow

```bash
# 1. Upload contract
curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@contract.pdf"

# 2. Wait for processing or trigger manually
curl -X POST http://localhost:8000/api/contracts/<id>/process \
  -H "Authorization: Bearer $TOKEN"

# 3. View extracted metadata
curl -X GET http://localhost:8000/api/contracts/<id> \
  -H "Authorization: Bearer $TOKEN"

# 4. View obligations
curl -X GET "http://localhost:8000/api/obligations/?contract_id=<id>" \
  -H "Authorization: Bearer $TOKEN"

# 5. View SLAs
curl -X GET http://localhost:8000/api/sla/<id> \
  -H "Authorization: Bearer $TOKEN"

# 6. Ask questions
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the key risks?", "contract_id": "<id>"}'

# 7. View contract intelligence
curl -X GET http://localhost:8000/api/dashboard/intelligence/<id> \
  -H "Authorization: Bearer $TOKEN"
```

### Scenario 2: Full SLA Monitoring Flow

```bash
# 1. Seed master data
curl -X POST http://localhost:8000/api/admin/master-data/seed-all \
  -H "Authorization: Bearer $TOKEN"

# 2. Upload a contract with SLAs
curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sla_contract.pdf"

# 3. Wait for processing, then add SLAs if needed
curl -X POST http://localhost:8000/api/sla/<contract_id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sla_name": "System Availability",
    "metric_type": "uptime_percentage",
    "metric_unit": "percentage",
    "target_value": 99.9,
    "severity": "critical"
  }'

# 4. Run SLA comparison
curl -X POST http://localhost:8000/api/connectors/compare/<contract_id> \
  -H "Authorization: Bearer $TOKEN"

# 5. Check alerts
curl -X GET http://localhost:8000/api/alerts/dashboard \
  -H "Authorization: Bearer $TOKEN"

# 6. Run a complete scenario
curl -X POST "http://localhost:8000/monitor/run-scenario?scenario=sla_breach" \
  -H "Authorization: Bearer $TOKEN"
```

### Scenario 3: Relationship Governance Flow

```bash
# 1. Create organizations
# 2. Create business relationship
# 3. Add team members
# 4. Define KPIs
# 5. Submit internal perception scores
# 6. Send external survey
# 7. Calculate perception gaps
# 8. Generate improvements from gaps
# (See Section 12 for detailed commands)
```

### Scenario 4: Governance Bridge E2E

```bash
# 1. Upload a PDF contract with clear counterparty and SLA terms
curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@backend/data/sample_contracts/MSA_CareerSource_Executed.pdf"

# 2. Wait for processing, then trigger deep analysis
curl -X POST http://localhost:8000/api/contracts/<id>/analyze \
  -H "Authorization: Bearer $TOKEN"

# 3. Verify organization auto-created from counterparty
curl -X GET http://localhost:8000/api/organizations \
  -H "Authorization: Bearer $TOKEN"

# 4. Verify business relationship auto-created
curl -X GET http://localhost:8000/api/relationships \
  -H "Authorization: Bearer $TOKEN"

# 5. Verify KPIs auto-created from SLA terms
curl -X GET "http://localhost:8000/api/kpis?relationship_id=<rel_id>" \
  -H "Authorization: Bearer $TOKEN"

# 6. Verify improvements auto-created from high-risk clauses
curl -X GET "http://localhost:8000/api/improvements?relationship_id=<rel_id>" \
  -H "Authorization: Bearer $TOKEN"

# 7. Check relationship health score
curl -X GET http://localhost:8000/api/relationships/<rel_id> \
  -H "Authorization: Bearer $TOKEN"
```

### Scenario 5: Auto-Link Detection E2E

```bash
# 1. Upload an MSA (Master Services Agreement)
curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@MSA_TechServices_Acme.pdf"
# Note the MSA contract_id

# 2. Wait for processing to complete

# 3. Upload an addendum/SOW that references the same counterparty
curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@SOW_TechServices_Acme.pdf"
# Note the SOW contract_id

# 4. Wait for processing, then check for suggested links
curl -X GET "http://localhost:8000/api/contracts/<sow_contract_id>/suggested-links" \
  -H "Authorization: Bearer $TOKEN"
# Expected: suggestion linking SOW to MSA with confidence score

# 5. Approve the suggested link
curl -X POST "http://localhost:8000/api/contracts/<sow_contract_id>/suggested-links/<suggestion_id>/review" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "approve"}'

# 6. Verify the established link
curl -X GET http://localhost:8000/api/contracts/<sow_contract_id>/links \
  -H "Authorization: Bearer $TOKEN"
# Expected: link to MSA with parent/child relationship
```

### Scenario 6: External Sharing E2E

```bash
# 1. Login as admin
export TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# 2. Invite external user and share contracts
INVITE=$(curl -s -X POST http://localhost:8000/api/external-users/invite \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "reviewer@partner.com",
    "full_name": "External Reviewer",
    "company_name": "Partner Corp",
    "contract_ids": ["<contract_id>"],
    "can_download": true,
    "can_comment": true,
    "expires_in_days": 30,
    "message": "Please review this agreement"
  }')
EXT_TOKEN=$(echo $INVITE | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# 3. Validate external token (no auth required)
curl -s "http://localhost:8000/api/external/validate?token=$EXT_TOKEN"

# 4. View shared contracts as external user
curl -s "http://localhost:8000/api/external/contracts?token=$EXT_TOKEN"

# 5. View specific contract details
curl -s "http://localhost:8000/api/external/contracts/<contract_id>?token=$EXT_TOKEN"

# 6. Add a comment as external user
curl -s -X POST "http://localhost:8000/api/external/contracts/<contract_id>/comments?token=$EXT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "We propose amending clause 3.2"}'

# 7. Download the contract
curl -s "http://localhost:8000/api/external/contracts/<contract_id>/download?token=$EXT_TOKEN" \
  -o downloaded_contract.pdf
```

### Scenario 7: Perception Scoring Flow

```bash
# 1. Create a KPI
curl -X POST http://localhost:8000/api/kpis \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "relationship_id": "<rel_id>",
    "name": "Service Quality",
    "measurement_type": "perception",
    "target_value": 8.0,
    "threshold_amber": 6.0,
    "threshold_red": 4.0
  }'
# Note kpi_id

# 2. Submit internal perception score (your organization's view)
curl -X POST http://localhost:8000/api/kpis/perception-scores \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "kpi_id": "<kpi_id>",
    "scorer_org_id": "<your_org_id>",
    "score": 7.5,
    "period": "2026-Q1",
    "comments": "Good performance overall"
  }'

# 3. Submit external perception score (counterparty's view)
curl -X POST http://localhost:8000/api/kpis/perception-scores \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "kpi_id": "<kpi_id>",
    "scorer_org_id": "<counterparty_org_id>",
    "score": 5.5,
    "period": "2026-Q1",
    "comments": "Room for improvement"
  }'

# 4. Verify gap calculation (internal 7.5 vs external 5.5 = gap of 2.0)
curl -X GET http://localhost:8000/api/kpis/<kpi_id>/gaps \
  -H "Authorization: Bearer $TOKEN"
# Expected: gap showing perception difference between internal and external scores

# 5. Generate improvements from the gap
curl -X POST http://localhost:8000/api/improvements/generate-from-gaps \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"relationship_id": "<rel_id>"}'
```

---

## Quick Test Script

```bash
#!/bin/bash

BASE_URL="http://localhost:8000"
USERNAME="admin"
PASSWORD="admin123"

echo "=== CLM API Testing Script ==="

# 1. Login
echo -e "\n[1] Logging in..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"$USERNAME\", \"password\": \"$PASSWORD\"}")

TOKEN=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")

if [ -z "$TOKEN" ]; then
  echo "Login failed!"
  exit 1
fi
echo "Login successful!"

# 2. Health check
echo -e "\n[2] Health check..."
curl -s "$BASE_URL/api/health" | python3 -m json.tool

# 3. Scheduler status
echo -e "\n[3] Scheduler status..."
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/admin/scheduler/status" | python3 -m json.tool

# 4. Seed master data
echo -e "\n[4] Seeding master data..."
curl -s -X POST -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/admin/master-data/seed-all" | python3 -m json.tool

# 5. List contracts
echo -e "\n[5] Contracts..."
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/contracts?page_size=5" | python3 -m json.tool

# 6. Dashboard summary
echo -e "\n[6] Dashboard summary..."
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/dashboard/contracts-summary" | python3 -m json.tool

# 7. Compliance rates
echo -e "\n[7] Obligation compliance..."
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/obligations/compliance/rates" | python3 -m json.tool

# 8. Alert dashboard
echo -e "\n[8] Alert dashboard..."
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/alerts/dashboard" | python3 -m json.tool

# 9. Business units
echo -e "\n[9] Business units..."
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/business-units?page_size=5" | python3 -m json.tool

# 10. Notification rules
echo -e "\n[10] Notification rules..."
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/notification-rules/?active_only=false" | python3 -m json.tool

# 11. External users
echo -e "\n[11] External users..."
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/external-users?page_size=5" | python3 -m json.tool

# 12. Pending suggested links
echo -e "\n[12] Pending suggested links..."
curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/contracts/pending-suggestions" | python3 -m json.tool

echo -e "\n=== Testing Complete ==="
```

---

## Troubleshooting

### Backend Won't Start
```bash
# Check if port is in use
lsof -i :8000

# Check database connection
uv run python -c "from app.database import engine; print('DB OK')"
```

### Scheduler Not Running
```bash
# Start scheduler manually
curl -X POST http://localhost:8000/api/admin/scheduler/start \
  -H "Authorization: Bearer $TOKEN"
```

### Migration Errors
```bash
# Check current migration
uv run alembic current

# Re-run migrations
uv run alembic upgrade head
```

### Token Expired
```bash
# Get new token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### External Token Issues
```bash
# Validate a token to check expiry/revocation
curl -X GET "http://localhost:8000/api/external/validate?token=<token>"

# Resend invite with fresh token
curl -X POST "http://localhost:8000/api/external-users/<id>/resend-invite?expires_in_days=30" \
  -H "Authorization: Bearer $TOKEN"
```

### ServiceNow Sync Errors
```bash
# Check connection health
curl -X POST http://localhost:8000/api/integrations/servicenow/config/test \
  -H "Authorization: Bearer $TOKEN"

# View recent logs (superadmin)
curl -X GET "http://localhost:8000/api/integrations/servicenow/admin/logs?limit=10" \
  -H "Authorization: Bearer $SUPERADMIN_TOKEN"
```

---

*Last updated: 2026-03-29*
