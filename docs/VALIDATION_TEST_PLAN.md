# CLM Platform Validation Test Plan

## Prerequisites
- Backend running on `http://localhost:8000`
- Frontend running on `http://localhost:3002`
- Database seeded with `seed_data` and `seed_relationship_governance`

---

## Flow 1: Authentication & Session Management

### 1.1 Super Admin Login
```bash
# Login as superadmin
curl -s http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"superadmin","password":"admin123"}' | python3 -m json.tool

# Expected: {"access_token":"...", "token_type":"bearer", "user":{...}}
# Save the token:
export SA_TOKEN="<paste_token_here>"
```

### 1.2 Verify Session
```bash
curl -s http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $SA_TOKEN" | python3 -m json.tool

# Expected: user object with role="super_admin", no tenant_id
```

### 1.3 Tenant Admin Login (Acme Corp)
```bash
curl -s http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python3 -m json.tool

# Expected: token + user with role="admin", tenant_id for Acme Corp
export ADMIN_TOKEN="<paste_token_here>"
```

### 1.4 Legal User Login
```bash
curl -s http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"legal","password":"admin123"}' | python3 -m json.tool

export LEGAL_TOKEN="<paste_token_here>"
```

### 1.5 Cross-Tenant Login (TechStart)
```bash
curl -s http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"techstart_admin","password":"admin123"}' | python3 -m json.tool

export TS_TOKEN="<paste_token_here>"
```

---

## Flow 2: Platform Administration (Super Admin)

### 2.1 List All Tenants
```bash
curl -s http://localhost:8000/api/admin/tenants \
  -H "Authorization: Bearer $SA_TOKEN" | python3 -m json.tool

# Expected: Array of tenants (Acme Corp, TechStart, LegalCo, etc.)
```

### 2.2 Create a New Tenant
```bash
curl -s -X POST http://localhost:8000/api/admin/tenants \
  -H "Authorization: Bearer $SA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Corp",
    "slug": "test-corp",
    "settings": {}
  }' | python3 -m json.tool

# Expected: New tenant object with UUID
# Save: export TEST_TENANT_ID="<tenant_id>"
```

### 2.3 List All Users (Global)
```bash
curl -s http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer $SA_TOKEN" | python3 -m json.tool

# Expected: Users across all tenants
```

### 2.4 Create User in New Tenant
```bash
curl -s -X POST http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer $SA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testadmin",
    "email": "testadmin@testcorp.com",
    "password": "admin123",
    "full_name": "Test Admin",
    "role": "admin",
    "tenant_id": "'$TEST_TENANT_ID'"
  }' | python3 -m json.tool

# Expected: New user object with tenant_id matching TEST_TENANT_ID
```

### 2.5 Verify Tenant Isolation
```bash
# Login as the new test admin
curl -s http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testadmin","password":"admin123"}' | python3 -m json.tool

export TEST_TOKEN="<paste_token>"

# List contracts - should be empty (new tenant has no data)
curl -s http://localhost:8000/api/contracts \
  -H "Authorization: Bearer $TEST_TOKEN" | python3 -m json.tool

# Expected: Empty list or {items: [], total: 0}
```

---

## Flow 3: Tenant Setup (Admin)

### 3.1 User Management
```bash
# List users in Acme tenant
curl -s http://localhost:8000/api/users \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Users belonging to Acme Corp only
```

### 3.2 Business Unit Hierarchy
```bash
# List business units
curl -s http://localhost:8000/api/business-units \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Create a business unit
curl -s -X POST http://localhost:8000/api/business-units \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Engineering",
    "code": "ENG",
    "description": "Engineering Department"
  }' | python3 -m json.tool

# Expected: New BU object
```

### 3.3 Custom Fields
```bash
# List custom field definitions
curl -s http://localhost:8000/api/admin/custom-fields \
  -H "Authorization: Bearer $SA_TOKEN" | python3 -m json.tool
```

---

## Flow 4: Contract Lifecycle

### 4.1 Upload a Contract
```bash
# Upload a sample contract (use an existing PDF)
curl -s -X POST http://localhost:8000/api/contracts/upload \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "file=@backend/data/sample_contracts/MSA_CareerSource_Executed.pdf" | python3 -m json.tool

# Expected: Contract object with status "processing" or "uploaded"
# Save: export CONTRACT_ID="<contract_id>"
```

### 4.2 Check Processing Status
```bash
# Wait ~30 seconds for AI pipeline, then check
curl -s http://localhost:8000/api/contracts/$CONTRACT_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Contract with status "completed", extracted metadata (parties, dates, value)
```

### 4.3 List All Contracts
```bash
curl -s http://localhost:8000/api/contracts \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Paginated list of Acme Corp contracts
```

### 4.4 Search Contracts
```bash
curl -s -X POST http://localhost:8000/api/contracts/search \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "indemnification"}' | python3 -m json.tool

# Expected: Contracts matching the semantic search
```

### 4.5 View Clauses
```bash
curl -s http://localhost:8000/api/contracts/$CONTRACT_ID/clauses \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Array of extracted clauses with types (indemnification, termination, etc.)
```

### 4.6 View Obligations
```bash
curl -s "http://localhost:8000/api/obligations?contract_id=$CONTRACT_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Obligations with deadlines, parties, status
```

### 4.7 View Risks
```bash
curl -s http://localhost:8000/api/contracts/$CONTRACT_ID/risks \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Risk items with severity scores
```

### 4.8 Contract Links
```bash
curl -s http://localhost:8000/api/contracts/$CONTRACT_ID/links \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Established contract relationships (may be empty for new contract)

# Check suggested links
curl -s http://localhost:8000/api/contracts/$CONTRACT_ID/suggested-links \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: AI-detected potential relationships with confidence scores
```

---

## Flow 5: Post-Signing Management

### 5.1 Renewals Dashboard
```bash
curl -s http://localhost:8000/api/renewals \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: List of contracts with renewal information, deadlines
```

### 5.2 Update Renewal Decision
```bash
# Get a renewal ID from the list above
curl -s -X PUT http://localhost:8000/api/renewals/<RENEWAL_ID> \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decision": "renew"}' | python3 -m json.tool
```

### 5.3 Compliance Status
```bash
curl -s http://localhost:8000/api/compliance/status \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Compliance overview with status counts
```

### 5.4 SLA Performance
```bash
curl -s http://localhost:8000/api/sla-performance \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

### 5.5 Vendor Scores
```bash
curl -s http://localhost:8000/api/vendor-scores \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

---

## Flow 6: AI Features

### 6.1 Contract Q&A
```bash
curl -s -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the termination clauses in my contracts?"}' | python3 -m json.tool

# Expected: AI-generated answer with source references
```

### 6.2 Chat Sessions
```bash
# List chat sessions
curl -s http://localhost:8000/api/chat/sessions \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Create new session
curl -s -X POST http://localhost:8000/api/chat/sessions \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Session"}' | python3 -m json.tool
```

### 6.3 Intent Routing (Specific Queries)
```bash
# Renewal query
curl -s -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "Which contracts are up for renewal in the next 90 days?"}' | python3 -m json.tool

# Obligation query
curl -s -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are my overdue obligations?"}' | python3 -m json.tool

# Risk query
curl -s -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me high risk contracts"}' | python3 -m json.tool
```

### 6.4 Schema Extraction
```bash
curl -s -X POST http://localhost:8000/api/contracts/$CONTRACT_ID/extract-schema \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"schema_type": "msa"}' | python3 -m json.tool

# Expected: Structured extraction based on MSA schema fields
```

---

## Flow 7: Relationship Governance

### 7.1 Organizations
```bash
# List organizations
curl -s http://localhost:8000/api/organizations \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Paginated list of organizations (Our Company, Acme Corp, vendors, partners)

# Create organization
curl -s -X POST http://localhost:8000/api/organizations \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New Vendor Inc",
    "code": "NVI",
    "org_type": "vendor",
    "industry": "Technology"
  }' | python3 -m json.tool
```

### 7.2 Relationships
```bash
# List relationships
curl -s http://localhost:8000/api/relationships \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: List of business relationships with org names, health scores

# Get specific relationship
curl -s http://localhost:8000/api/relationships/<RELATIONSHIP_ID> \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Full relationship detail with team members
```

### 7.3 Team Management
```bash
# Get team members
curl -s http://localhost:8000/api/relationships/<RELATIONSHIP_ID>/team \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Array of team members with roles and responsibilities
```

### 7.4 KPIs & Perception Scoring
```bash
# List KPIs (optionally filter by relationship)
curl -s "http://localhost:8000/api/kpis?relationship_id=<RELATIONSHIP_ID>" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: KPIs with categories (quality, delivery, satisfaction, etc.)

# Submit perception score
curl -s -X POST http://localhost:8000/api/kpis/perception-scores \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "kpi_id": "<KPI_ID>",
    "scorer_org_id": "<ORG_ID>",
    "score": 4.2,
    "is_internal": true,
    "period_start": "2026-01-01",
    "period_end": "2026-03-31",
    "comments": "Good performance this quarter"
  }' | python3 -m json.tool
```

### 7.5 Gap Analysis
```bash
# Get gaps for a KPI
curl -s http://localhost:8000/api/kpis/<KPI_ID>/gaps \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Perception gaps with severity (aligned/minor/moderate/significant/critical)

# Get gap summary for a relationship
curl -s "http://localhost:8000/api/kpis/gap-summary?relationship_id=<RELATIONSHIP_ID>" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Aggregated gap summary with severity distribution
```

### 7.6 Improvements
```bash
# List improvements
curl -s http://localhost:8000/api/improvements \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Improvement points with status, priority, linked KPIs

# Auto-generate from gaps
curl -s -X POST http://localhost:8000/api/improvements/generate-from-gaps \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"relationship_id": "<RELATIONSHIP_ID>"}' | python3 -m json.tool

# Expected: Generated improvement suggestions based on perception gaps
```

### 7.7 Health Score
```bash
curl -s http://localhost:8000/api/relationships/<RELATIONSHIP_ID>/health \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Health score with breakdown (compliance, SLA, perception, improvement)
```

---

## Flow 8: Surveys

### 8.1 Create Survey Template
```bash
curl -s -X POST http://localhost:8000/api/surveys/templates \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Q1 Satisfaction Survey",
    "description": "Quarterly satisfaction assessment",
    "questions": [
      {
        "text": "How satisfied are you with our service quality?",
        "question_type": "rating",
        "required": true,
        "order_index": 1
      },
      {
        "text": "What areas need improvement?",
        "question_type": "text",
        "required": false,
        "order_index": 2
      }
    ]
  }' | python3 -m json.tool

# Save: export TEMPLATE_ID="<template_id>"
```

### 8.2 List Templates
```bash
curl -s http://localhost:8000/api/surveys/templates \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

### 8.3 Create Survey Instance
```bash
curl -s -X POST http://localhost:8000/api/surveys/instances \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "'$TEMPLATE_ID'",
    "relationship_id": "<RELATIONSHIP_ID>",
    "title": "Q1 2026 Partner Satisfaction",
    "due_date": "2026-04-30"
  }' | python3 -m json.tool

# Save: export INSTANCE_ID="<instance_id>"
```

### 8.4 Send Survey
```bash
curl -s -X POST http://localhost:8000/api/surveys/instances/$INSTANCE_ID/send \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Instance status changes to "sent", respondent tokens generated
```

### 8.5 Complete Survey (External - No Auth)
```bash
# Get external survey (use token from send response)
curl -s http://localhost:8000/api/surveys/external/<TOKEN> | python3 -m json.tool

# Expected: Survey questions without requiring authentication

# Submit responses
curl -s -X POST http://localhost:8000/api/surveys/external/<TOKEN> \
  -H "Content-Type: application/json" \
  -d '{
    "responses": [
      {"question_id": "<Q1_ID>", "rating": 4},
      {"question_id": "<Q2_ID>", "text_response": "Communication could be better"}
    ]
  }' | python3 -m json.tool
```

### 8.6 View Results
```bash
curl -s http://localhost:8000/api/surveys/instances/$INSTANCE_ID/results \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Aggregated responses with averages and breakdowns
```

---

## Flow 9: Reporting & Analytics

### 9.1 Dashboard
```bash
# Overview stats
curl -s http://localhost:8000/api/dashboard/stats \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Contract counts, risk distribution, obligation status

# Recent contracts
curl -s http://localhost:8000/api/dashboard/recent \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Risk summary
curl -s http://localhost:8000/api/dashboard/risks \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

### 9.2 Audit Trail
```bash
curl -s http://localhost:8000/api/audit \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Expected: Chronological log of user actions
```

---

## Flow 10: Frontend UI Validation

Open browser to `http://localhost:3002` and verify each page:

### 10.1 Login Page
- [ ] Login form renders
- [ ] Login with admin/admin123 succeeds
- [ ] Redirects to dashboard

### 10.2 Dashboard
- [ ] Stats cards show (total contracts, active, expiring soon, high risk)
- [ ] Recent contracts list displays
- [ ] Risk summary chart renders

### 10.3 Contracts
- [ ] Contract list page loads with table
- [ ] Search/filter works
- [ ] Click contract opens detail view
- [ ] Detail shows metadata, clauses, obligations tabs
- [ ] Upload button opens upload modal
- [ ] File upload triggers processing

### 10.4 Contract Detail
- [ ] Metadata tab shows extracted info (parties, dates, value)
- [ ] Clauses tab shows extracted clauses with types
- [ ] Obligations tab shows obligations with status
- [ ] Risk indicators display
- [ ] Contract links section works

### 10.5 AI Chat
- [ ] Chat page loads
- [ ] Can create new session
- [ ] Can ask questions about contracts
- [ ] Responses include source references
- [ ] Chat history persists

### 10.6 Renewals
- [ ] Renewals page shows upcoming renewals
- [ ] Can update renewal decisions
- [ ] Timeline/calendar view works

### 10.7 Obligations
- [ ] Obligations page shows all obligations
- [ ] Can filter by status (pending, fulfilled, breached)
- [ ] Can update obligation status

### 10.8 Governance - Organizations
- [ ] Organizations page lists orgs
- [ ] Can create new organization
- [ ] Filter/search works

### 10.9 Governance - Relationships
- [ ] Relationships page lists all relationships
- [ ] Click opens detail page
- [ ] Detail shows team, KPIs, health score
- [ ] Can add team members

### 10.10 Governance - KPI Scorecard
- [ ] KPI page loads
- [ ] Relationship selector works
- [ ] KPI table shows with perception scores
- [ ] Gap severity indicators display

### 10.11 Governance - Improvements
- [ ] Improvements page lists items
- [ ] Can filter by status/priority
- [ ] Can create new improvement
- [ ] Auto-generate from gaps works

### 10.12 Governance - Surveys
- [ ] Templates tab lists templates
- [ ] Can create new template
- [ ] Instances tab lists instances
- [ ] Can create and send survey

### 10.13 Admin - Settings
- [ ] Settings page loads
- [ ] Business units management works
- [ ] External users section works
- [ ] Workflow configuration accessible

### 10.14 Multi-Tenant Isolation
- [ ] Logout, login as techstart_admin
- [ ] Dashboard shows TechStart data only (no Acme contracts)
- [ ] Cannot access Acme Corp resources

---

## Quick Smoke Test (5-Minute Version)

Run these in sequence for a fast validation:

```bash
# 1. Login
TOKEN=$(curl -s http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Dashboard
curl -s http://localhost:8000/api/dashboard/stats -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 3. Contracts
curl -s http://localhost:8000/api/contracts -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 4. Renewals
curl -s http://localhost:8000/api/renewals -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 5. AI Query
curl -s -X POST http://localhost:8000/api/query -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"query":"summarize my contracts"}' | python3 -m json.tool

# 6. Organizations
curl -s http://localhost:8000/api/organizations -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 7. Relationships
curl -s http://localhost:8000/api/relationships -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 8. KPIs
curl -s http://localhost:8000/api/kpis -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 9. Improvements
curl -s http://localhost:8000/api/improvements -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 10. Survey Templates
curl -s http://localhost:8000/api/surveys/templates -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

If all 10 return valid JSON with data, core platform is working.
