# CLM Testing Guide

> Step-by-step guide to test all implemented functionalities.

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
14. [End-to-End Test Scenarios](#14-end-to-end-test-scenarios)

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
  -d '{"username": "admin", "password": "admin123!"}'

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
  -d '{"username": "admin", "password": "admin123!"}'
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
| SLA Config | http://localhost:5173/admin/master-data/slas | SLA master data |
| Milestone Config | http://localhost:5173/admin/master-data/milestones | Milestone master data |
| Scheduler | http://localhost:5173/admin/scheduler | Background job management |
| Settings | http://localhost:5173/settings | Langfuse and system settings |

---

## 14. End-to-End Test Scenarios

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
# (See Section 11 for detailed commands)
```

---

## Quick Test Script

```bash
#!/bin/bash

BASE_URL="http://localhost:8000"
USERNAME="admin"
PASSWORD="admin123!"

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
  -d '{"username": "admin", "password": "admin123!"}'
```

---

*Last updated: 2026-02-16*
