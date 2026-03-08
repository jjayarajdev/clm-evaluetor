# Evaluetor API Documentation

**Base URL:** `http://localhost:8000/api`
**Version:** 0.1.0
**OpenAPI Docs:** `/api/docs` (Swagger UI) | `/api/redoc` (ReDoc)
**OpenAPI Schema:** `/api/openapi.json`

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Tenants](#2-tenants)
3. [Users](#3-users)
4. [Audit Logs](#4-audit-logs)
5. [Clients](#5-clients)
6. [Contracts](#6-contracts)
7. [Amendments & Versioning](#7-amendments--versioning)
8. [Schemas & Extraction](#8-schemas--extraction)
9. [Obligations](#9-obligations)
10. [SLA Tracking](#10-sla-tracking)
11. [Renewals](#11-renewals)
12. [Vendors](#12-vendors)
13. [Dashboards](#13-dashboards)
14. [Query & AI](#14-query--ai)
15. [Chat Sessions](#15-chat-sessions)
16. [Reports](#16-reports)
17. [Metrics & Trends](#17-metrics--trends)
18. [Alerts](#18-alerts)
19. [Monitor & Events](#19-monitor--events)
20. [Notifications](#20-notifications)
21. [Notification Rules](#21-notification-rules)
22. [Workflow Admin](#22-workflow-admin)
23. [Compliance](#23-compliance)
24. [Connectors](#24-connectors)
25. [Post-Signing Dashboard](#25-post-signing-dashboard)
26. [Milestones](#26-milestones)
27. [Knowledge Graph](#27-knowledge-graph)
28. [Contract Links & Suggested Links](#28-contract-links--suggested-links)
29. [Master Data Admin](#29-master-data-admin)
30. [Scheduler Admin](#30-scheduler-admin)
31. [Settings (Langfuse)](#31-settings-langfuse)
32. [Custom Fields](#32-custom-fields)
33. [Organizations](#33-organizations)
34. [Relationships](#34-relationships)
35. [KPIs & Perception](#35-kpis--perception)
36. [Improvements](#36-improvements)
37. [Surveys](#37-surveys)
38. [Business Units](#38-business-units)
39. [External Users](#39-external-users)
40. [External Portal](#40-external-portal)
41. [Health & System](#41-health--system)
42. [Endpoint Summary](#endpoint-summary)
43. [Error Responses](#error-responses)
44. [Common Patterns](#common-patterns)

---

## General Information

### Authentication

All protected endpoints require a **Bearer token** in the `Authorization` header:

```
Authorization: Bearer <jwt_token>
```

Obtain a token via `POST /api/auth/login`. Tokens expire after 24 hours (configurable).

### Roles

| Role | Description |
|------|-------------|
| `super_admin` | Cross-tenant access, tenant management |
| `admin` | Full access within tenant (user management, settings) |
| `legal` | Contract analysis, risk assessment, compliance |
| `procurement` | Vendor management, SLA tracking, spend analysis |

### Multi-Tenancy

All data is automatically isolated by tenant. The tenant is derived from the authenticated user's JWT token. Super admins can access cross-tenant data.

### Pagination

List endpoints support standard pagination:

```
GET /api/contracts?page=1&page_size=20
```

**Response:**
```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "pages": 8
}
```

---

## 1. Authentication

**Prefix:** `/api/auth`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/login` | Public | Login with username/password |
| GET | `/api/auth/me` | Any | Get current authenticated user |
| POST | `/api/auth/logout` | Any | Logout (stateless, logs for audit) |

### POST `/api/auth/login`

**Request:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": "uuid",
    "username": "admin",
    "email": "admin@acme.com",
    "full_name": "Admin User",
    "role": "admin",
    "tenant_id": "uuid",
    "tenant_name": "Acme Corp"
  }
}
```

---

## 2. Tenants

**Prefix:** `/api/tenants`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/tenants` | Super Admin | List all tenants |
| POST | `/api/tenants` | Super Admin | Create tenant |
| GET | `/api/tenants/current` | Any | Get current user's tenant |
| GET | `/api/tenants/current/stats` | Admin | Current tenant statistics |
| GET | `/api/tenants/{tenant_id}` | Super Admin | Get tenant by ID |
| GET | `/api/tenants/{tenant_id}/stats` | Super Admin | Tenant statistics |
| PATCH | `/api/tenants/{tenant_id}` | Super Admin | Update tenant |
| DELETE | `/api/tenants/{tenant_id}` | Super Admin | Deactivate tenant (soft delete, 204) |

### POST `/api/tenants`

**Request:**
```json
{
  "name": "Acme Corp",
  "slug": "acme-corp",
  "plan": "professional",
  "contact_email": "admin@acme.com",
  "contact_name": "John Doe"
}
```

**Plans:** `starter` (100 contracts), `professional` (500), `enterprise` (2000)

---

## 3. Users

**Prefix:** `/api/users`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/users` | Admin | List users (paginated, filterable) |
| POST | `/api/users` | Admin | Create user |
| GET | `/api/users/me` | Any | Current user details |
| GET | `/api/users/{user_id}` | Admin/Self | Get user by ID |
| PUT | `/api/users/{user_id}` | Admin | Update user |
| PUT | `/api/users/{user_id}/password` | Admin | Update password |
| DELETE | `/api/users/{user_id}` | Admin | Deactivate user (soft delete) |
| POST | `/api/users/{user_id}/activate` | Admin | Reactivate user |

**Query Params (list):** `role`, `is_active`, `search`, `page` (default 1), `page_size` (default 20, max 100)

---

## 4. Audit Logs

**Prefix:** `/api/audit`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/audit` | Admin | List audit logs (paginated, filterable) |
| GET | `/api/audit/stats` | Admin | Action count stats over N days |
| GET | `/api/audit/resource/{resource_type}/{resource_id}` | Admin | Audit history for specific resource |

**Query Params (list):** `user_id`, `action`, `resource_type`, `resource_id`, `start_date`, `end_date`, `page`, `page_size` (max 100)

**Log Fields:** `id`, `user_id`, `username`, `action`, `resource_type`, `resource_id`, `details`, `ip_address`, `user_agent`, `created_at`

---

## 5. Clients

**Prefix:** `/api/clients`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/clients` | Any | Create client (201) |
| GET | `/api/clients` | Any | List clients (paginated, searchable) |
| GET | `/api/clients/summary` | Any | Brief list for dropdowns (includes contract counts) |
| GET | `/api/clients/{client_id}` | Any | Get client details |
| PUT | `/api/clients/{client_id}` | Any | Update client |
| DELETE | `/api/clients/{client_id}` | Any | Delete client (`force=true` unlinks contracts first) |

**Client Fields:** `name`, `code` (unique per tenant), `industry`, `website`, `address`, `city`, `country`, `contact_name`, `contact_email`, `contact_phone`, `contact_title`, `notes`

---

## 6. Contracts

**Prefix:** `/api/contracts`

### Upload & Processing

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/contracts/upload` | Any | Upload single contract (PDF/DOCX, multipart) |
| POST | `/api/contracts/upload/batch` | Any | Upload multiple files (max 50) |
| POST | `/api/contracts/upload/zip` | Any | Upload and extract ZIP archive |
| GET | `/api/contracts/upload-status/{batch_id}` | Any | Batch upload processing status |
| POST | `/api/contracts/process` | Any | Trigger processing for multiple contracts |
| POST | `/api/contracts/{contract_id}/process` | Any | Trigger processing for single contract |
| POST | `/api/contracts/{contract_id}/analyze` | Any | Run AI analysis (clauses, obligations, risk) |
| GET | `/api/contracts/{contract_id}/processing-status` | Any | Get processing status |
| GET | `/api/contracts/{contract_id}/processing-status/current` | Any | Real-time processing status with stage/progress |

### CRUD & Search

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/contracts` | Any | List contracts (paginated, filterable, sortable) |
| GET | `/api/contracts/filter-options` | Any | Available filter values (types, risks, statuses) |
| GET | `/api/contracts/search?query=...` | Any | Semantic search across contracts |
| GET | `/api/contracts/{contract_id}` | Any | Full contract with metadata, clauses, obligations, SLAs |
| PATCH | `/api/contracts/{contract_id}` | Any | Update contract metadata |
| DELETE | `/api/contracts/{contract_id}` | Any | Delete contract and all associated data |
| POST | `/api/contracts/batch-delete` | Any | Delete multiple contracts |
| POST | `/api/contracts/admin/reindex-all` | Admin | Reindex all contracts in vector store |

**Query Params (list):** `page`, `page_size`, `contract_type`, `counterparty`, `risk_level`, `status_filter`, `search`, `client_id`, `sort_by` (default `created_at`), `sort_desc` (default `true`)

### Files

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/contracts/{contract_id}/files` | Any | List associated files |
| POST | `/api/contracts/{contract_id}/files` | Any | Upload additional files |

### Custom Fields

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| PUT | `/api/contracts/{contract_id}/custom-fields` | Any | Update custom fields (validated against tenant schema) |
| POST | `/api/contracts/{contract_id}/extract-custom-fields` | Any | AI-extract custom fields from contract |
| POST | `/api/contracts/batch/extract-custom-fields` | Any | Batch extract custom fields |

### Sharing & Comments

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/contracts/{contract_id}/share` | Any | Share with external user |
| GET | `/api/contracts/{contract_id}/shares` | Any | List shares for contract |
| DELETE | `/api/contracts/{contract_id}/shares/{share_id}` | Any | Revoke share (204) |
| GET | `/api/contracts/{contract_id}/comments` | Any | List comments |
| POST | `/api/contracts/{contract_id}/comments` | Any | Add comment |
| POST | `/api/contracts/{contract_id}/comments/{comment_id}/resolve` | Any | Resolve comment (204) |
| DELETE | `/api/contracts/{contract_id}/comments/{comment_id}` | Any | Delete comment (204) |

---

## 7. Amendments & Versioning

**Prefix:** `/api/contracts` | **Tag:** `amendments`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/contracts/{id}/amendments` | Any | Link amendment to parent contract |
| GET | `/api/contracts/{id}/amendments` | Any | List all amendments |
| GET | `/api/contracts/{id}/versions` | Any | Full version history (original + amendments) |
| GET | `/api/contracts/{id}/diff/{compare_id}` | Any | Compare two contract versions |
| POST | `/api/contracts/{id}/supersede` | Any | Mark contract as superseded |
| GET | `/api/contracts/{id}/audit-trail` | Any | Audit trail for contract + amendments |
| GET | `/api/contracts/{id}/amendment-summary/{amendment_id}` | Any | Detailed amendment summary with impact |

---

## 8. Schemas & Extraction

**Prefix:** `/api/schemas`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/schemas` | Any | List all extraction schemas |
| GET | `/api/schemas/{schema_id}` | Any | Schema details with JSON template |
| GET | `/api/schemas/{schema_id}/template` | Any | JSON template only |
| GET | `/api/schemas/{schema_id}/prompt` | Any | Extraction prompt text |
| POST | `/api/schemas/extract` | Any | Extract from raw contract text |
| POST | `/api/schemas/extract/{contract_id}` | Any | Extract from existing contract |
| GET | `/api/schemas/by-type/{contract_type}` | Any | Get schema by contract type |

**Supported Types:** MSA, SOW, NDA, Amendment, Vendor Agreement, Employment Contract

---

## 9. Obligations

**Prefix:** `/api/obligations`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/obligations` | Any | List obligations (filterable, paginated) |
| GET | `/api/obligations/{obligation_id}` | Any | Get obligation details |
| PUT | `/api/obligations/{obligation_id}/status` | Any | Update status |
| PUT | `/api/obligations/{obligation_id}/rag` | Any | Update RAG status with compliance tracking |
| PUT | `/api/obligations/{obligation_id}/owner` | Any | Assign owner and priority |
| POST | `/api/obligations/{obligation_id}/evidence` | Any | Upload compliance evidence (multipart) |
| GET | `/api/obligations/compliance/rates` | Any | Compliance rates across portfolio |

**Query Params (list):** `contract_id`, `status`, `rag_status`, `owner_type`, `category`, `is_critical`, `limit` (default 50), `offset`

**Statuses:** `pending`, `in_progress`, `completed`, `overdue`

**RAG Status:** `green` (on track), `amber` (at risk), `red` (non-compliant), `not_assessed`

**Owner Types:** `provider`, `client`, `mutual`, `third_party`

**Categories:** 34 categories including `service_provision`, `payment`, `data_protection`, `regulatory_compliance`, `confidentiality`, `reporting`, etc.

---

## 10. SLA Tracking

**Prefix:** `/api/sla`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/sla` | Any | List all SLAs (filterable) |
| GET | `/api/sla/{contract_id}` | Any | SLAs for contract with performance history and trends |
| POST | `/api/sla/{contract_id}` | Any | Create SLA |
| POST | `/api/sla/{contract_id}/performance/{sla_id}` | Any | Log performance measurement (auto-detects breaches) |
| GET | `/api/sla/compliance/summary` | Any | Aggregated compliance summary |
| GET | `/api/sla/breaches/active` | Any | Active breaches grouped by severity |
| PUT | `/api/sla/{contract_id}/{sla_id}` | Admin/Legal | Update SLA definition |
| DELETE | `/api/sla/{contract_id}/{sla_id}` | Admin/Legal | Delete SLA |

**Breach Severity:** `minor` (<5% deviation), `moderate` (<15%), `major` (<30%), `critical` (>=30%)

**Compliance Trend:** `improving`, `declining`, `stable` (calculated from last 3-6 measurements)

---

## 11. Renewals

**Prefix:** `/api/renewals`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/renewals/calendar` | Any | Contracts grouped by renewal window |
| GET | `/api/renewals/at-risk` | Any | Contracts past notice deadline |
| GET | `/api/renewals/summary` | Any | Renewal dashboard statistics |
| PUT | `/api/renewals/{contract_id}/status` | Any | Update renewal decision |
| GET | `/api/renewals/{contract_id}/recommendation` | Any | AI renewal recommendation with factors |
| GET | `/api/renewals/export/calendar.ics` | Any | Export ICS calendar file |

**Renewal Windows:** `expired` (past expiration), `critical` (past notice deadline), `within_30_days`, `within_60_days`, `within_90_days`

**Renewal Statuses:** `pending_review`, `approved`, `declined`, `auto_renewed`, `expired`, `renegotiating`

**Recommendation Actions:** `renew`, `renegotiate`, `terminate`, `review_terms` (with confidence score 0.6-0.85)

**ICS Export Params:** `include_expirations`, `include_notice_deadlines`, `include_obligations`, `include_key_dates`, `days_ahead` (30-730)

---

## 12. Vendors

**Prefix:** `/api/vendors`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/vendors` | Any | List vendors with performance scores |
| GET | `/api/vendors/at-risk` | Any | Vendors with score < 60 |
| GET | `/api/vendors/compare?vendors=Acme,TechCorp` | Any | Side-by-side comparison (2-5 vendors) |
| GET | `/api/vendors/scorecard?limit=10` | Any | Simplified scorecards for top vendors |
| GET | `/api/vendors/{vendor_name}/performance` | Any | Detailed vendor performance profile |

**Scoring Weights:** Obligation (40%) + SLA (30%) + Responsiveness (20%) + Issue Rate (10%)

**Risk Thresholds:** At-Risk (<60), High (40-60), Critical (<40)

**Sort Options:** `score`, `name`, `exposure`, `contracts`

---

## 13. Dashboards

**Prefix:** `/api/dashboard`

### Role-Based Dashboards

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/dashboard/contracts-summary` | Any | Contract summary cards (by status, risk, expiring) |
| GET | `/api/dashboard/admin` | Admin | Admin dashboard (stats, activity, ingestion) |
| GET | `/api/dashboard/legal` | Admin/Legal | Risk overview, expirations, high-risk clauses |
| GET | `/api/dashboard/procurement` | Admin/Procurement | Spend, obligations, auto-renewal risks |
| GET | `/api/dashboard/portfolio` | Any | Portfolio analytics (value, risk, exposure) |

### Contract Intelligence

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/dashboard/intelligence/{contract_id}` | Any | Key terms, clause breakdown, obligations matrix, risk |
| GET | `/api/dashboard/cockpit/{contract_id}` | Any | Comprehensive cockpit (all contract dimensions) |
| GET | `/api/dashboard/financials/{contract_id}` | Any | Financial terms, fees, penalties |

### Obligations & Compliance

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/dashboard/obligations-summary` | Any | Obligations grouped by type/status/party |
| GET | `/api/dashboard/obligations-compliance` | Any | Portfolio-wide RAG status, compliance calendar |
| GET | `/api/dashboard/obligations/by-type/{type}` | Any | Drill-down by obligation type |
| GET | `/api/dashboard/obligations/{obligation_id}` | Any | Full obligation detail with clause linkage |

### Clauses

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/dashboard/clauses-summary` | Any | Clauses grouped by type, high-risk count |
| GET | `/api/dashboard/clauses/by-type/{clause_type}` | Any | Drill-down by clause type |
| GET | `/api/dashboard/clauses/{clause_id}` | Any | Full clause with related clauses |

### Definitions

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/dashboard/definitions/{contract_id}` | Any | Definitions extracted from contract |
| GET | `/api/dashboard/definitions-summary` | Any | Definitions summary (top 20 terms) |
| GET | `/api/dashboard/definitions/search/{term}` | Any | Search definitions across contracts |
| GET | `/api/dashboard/definitions/compare/{term}` | Any | Compare term definitions across contracts |
| GET | `/api/dashboard/definitions/all-terms` | Any | All unique defined terms with frequency |

---

## 14. Query & AI

**Prefix:** `/api/query`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/query` | Any | Ask question about contracts (RAG pipeline) |
| GET | `/api/query/suggestions` | Any | Suggested questions |
| POST | `/api/query/analyze` | Any | Full AI analysis (all agents) |

### POST `/api/query`

**Request:**
```json
{
  "question": "What are the termination rights in the Acme contract?",
  "contract_id": "uuid (optional - scope to single contract)",
  "session_id": "uuid (optional - continue conversation)"
}
```

**Response (200):**
```json
{
  "answer": "The Acme contract provides either party the right to terminate...",
  "confidence": 0.87,
  "sources": [
    {
      "contract_id": "uuid",
      "contract_name": "Acme_MSA.pdf",
      "clause_text": "Either party may terminate this Agreement...",
      "section_reference": "Section 12.1",
      "page_number": 8,
      "relevance_score": 0.92
    }
  ],
  "follow_up_questions": ["What notice period is required for termination?"],
  "session_id": "uuid"
}
```

### POST `/api/query/analyze`

**Query Params:** `contract_id` (required), `analysis_type` (`full`, `metadata`, `risk`, `renewal`)

Runs multiple AI agents: metadata extraction, clause extraction, obligation tracking, risk detection, renewal monitoring.

---

## 15. Chat Sessions

**Prefix:** `/api/chat`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/chat/sessions` | Any | List all chat sessions for current user (newest first) |
| POST | `/api/chat/sessions` | Any | Create a new chat session |
| GET | `/api/chat/sessions/{session_id}` | Any | Get session with all messages |
| PATCH | `/api/chat/sessions/{session_id}` | Any | Update session title |
| DELETE | `/api/chat/sessions/{session_id}` | Any | Delete session and all messages |
| POST | `/api/chat/sessions/{session_id}/messages` | Any | Add a message to a session |

Sessions are scoped to tenant + user (multi-tenant isolated). First user message auto-titles the session. Sessions can optionally be scoped to a specific contract via `contract_id`.

### POST `/api/chat/sessions`

**Request:**
```json
{
  "title": "New Chat",
  "contract_id": null
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "title": "New Chat",
  "contract_id": null,
  "message_count": 0,
  "created_at": "2026-03-07T12:00:00Z",
  "updated_at": "2026-03-07T12:00:00Z"
}
```

### GET `/api/chat/sessions/{session_id}`

**Response (200):**
```json
{
  "id": "uuid",
  "title": "string",
  "contract_id": "uuid|null",
  "message_count": 0,
  "created_at": "2026-03-07T12:00:00Z",
  "updated_at": "2026-03-07T12:00:00Z",
  "messages": [
    {
      "id": "uuid",
      "role": "user",
      "content": "string",
      "sources": [],
      "follow_ups": [],
      "visualizations": [],
      "created_at": "2026-03-07T12:00:00Z"
    }
  ]
}
```

### PATCH `/api/chat/sessions/{session_id}`

**Request:**
```json
{
  "title": "Updated Title"
}
```

### POST `/api/chat/sessions/{session_id}/messages`

**Request:**
```json
{
  "role": "user",
  "content": "What are the termination clauses?",
  "sources": [],
  "follow_ups": [],
  "visualizations": []
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "role": "user",
  "content": "What are the termination clauses?",
  "sources": [],
  "follow_ups": [],
  "visualizations": [],
  "created_at": "2026-03-07T12:00:00Z"
}
```

---

## 16. Reports

**Prefix:** `/api/reports`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/reports/compliance` | Any | Compliance report for date range |
| GET | `/api/reports/compliance/trend` | Any | Compliance trend over time |
| GET | `/api/reports/compliance/export` | Any | Export to CSV (Excel planned) |
| GET | `/api/reports/summary` | Any | Quick current-month summary |

**Query Params (compliance):** `start_date` (required), `end_date` (required)

**Query Params (trend):** `period` (`weekly`/`monthly`), `lookback` (1-12 periods)

**Query Params (export):** `start_date`, `end_date`, `format` (`csv`/`excel`)

---

## 17. Metrics & Trends

**Prefix:** `/api/metrics`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/metrics/trends/{metric}` | Any | Trend data for specific metric (7-90 days) |
| GET | `/api/metrics/dashboard-trends` | Any | All trends for dashboard sparklines |
| GET | `/api/metrics/history` | Public | Full metric history (1-365 days) |
| POST | `/api/metrics/capture` | Public | Manually capture today's snapshot |
| POST | `/api/metrics/backfill` | Public | Backfill with simulated data (demo only) |

**Available Metrics:** `total_contracts`, `contracts_at_risk`, `compliance_rate`, `total_contract_value`, `obligations_overdue`, `sla_compliance_rate`, `slas_breached`

---

## 18. Alerts

**Prefix:** `/api/alerts`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/alerts/dashboard` | Any | Alert dashboard summary (counts by status/priority) |
| GET | `/api/alerts` | Any | List alerts (filterable by status/priority/category) |
| GET | `/api/alerts/critical` | Any | Critical and high-priority active alerts |
| GET | `/api/alerts/{alert_id}` | Any | Alert details |
| POST | `/api/alerts/{alert_id}/acknowledge` | Any | Acknowledge alert |
| POST | `/api/alerts/{alert_id}/resolve` | Any | Resolve alert (requires resolution_notes) |
| POST | `/api/alerts/{alert_id}/escalate` | Any | Escalate alert |
| POST | `/api/alerts/{alert_id}/dismiss` | Any | Dismiss alert |
| POST | `/api/alerts/{alert_id}/notify` | Any | Send notification for alert |
| POST | `/api/alerts/bulk-action` | Any | Bulk acknowledge/resolve/dismiss |
| GET | `/api/alerts/by-contract/{contract_id}` | Any | Alerts for specific contract |
| GET | `/api/alerts/stats/trends` | Any | Alert trends over time (1-90 days) |

**Priorities:** `critical`, `high`, `medium`, `low`

**Statuses:** `active`, `acknowledged`, `resolved`, `dismissed`, `escalated`

**Categories:** `sla_breach`, `obligation_overdue`, `renewal_approaching`, `compliance_gap`

---

## 19. Monitor & Events

**Prefix:** `/monitor`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/monitor/scan` | Public | Run on-demand event detection scan |
| POST | `/monitor/process` | Public | Process pending events through workflows |
| GET | `/monitor/stats` | Public | Monitoring statistics (event counts by status) |
| GET | `/monitor/events` | Public | List events (filterable by status/type) |
| GET | `/monitor/events/{event_id}` | Public | Event details |
| GET | `/monitor/approvals` | Public | List approval requests |
| POST | `/monitor/approvals/{approval_id}/decide` | Public | Approve or reject |
| GET | `/monitor/workflows` | Public | List workflow definitions |
| POST | `/monitor/test-data` | Public | Generate synthetic test data |
| POST | `/monitor/run-scenario` | Public | Run end-to-end scenario |

**Event Types:** `sla_breach`, `obligation_overdue`, `renewal_approaching`, `milestone_at_risk`

---

## 20. Notifications

**Prefix:** `/notifications`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/notifications` | Public | List notifications (filterable) |
| GET | `/notifications/stats` | Public | Notification statistics |
| GET | `/notifications/{notification_id}` | Public | Notification details |
| POST | `/notifications/{notification_id}/retry` | Public | Retry failed notification |
| POST | `/notifications/retry-failed` | Public | Retry all failed (max_retries param) |
| GET | `/notifications/by-event/{event_id}` | Public | Notifications for specific event |
| POST | `/notifications/test` | Public | Send test notification |

---

## 21. Notification Rules

**Prefix:** `/api/notification-rules`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/notification-rules` | Any | List rules for tenant |
| GET | `/api/notification-rules/templates` | Public | 7 pre-defined rule templates |
| POST | `/api/notification-rules` | Any | Create rule |
| POST | `/api/notification-rules/from-template/{index}` | Any | Create from template |
| GET | `/api/notification-rules/{rule_id}` | Any | Get rule details |
| PUT | `/api/notification-rules/{rule_id}` | Any | Update rule |
| DELETE | `/api/notification-rules/{rule_id}` | Any | Delete rule |
| POST | `/api/notification-rules/{rule_id}/toggle` | Any | Toggle active status |
| GET | `/api/notification-rules/summary/stats` | Any | Rule statistics |

**Rule Fields:** `event_type`, `days_before`, `repeat_interval_days`, `max_repeats`, `channels` (email/teams/slack), `notify_contract_owner`, `notify_admin`, `additional_recipients`, `contract_types` (filter), `min_contract_value`, `risk_levels` (filter), `priority`, `respect_business_hours`

---

## 22. Workflow Admin

**Prefix:** `/admin`

### Workflows

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/admin/workflows` | Public | List workflow definitions |
| GET | `/admin/workflows/{workflow_id}` | Public | Get workflow with steps |
| POST | `/admin/workflows` | Public | Create workflow |
| PATCH | `/admin/workflows/{workflow_id}` | Public | Update workflow |
| POST | `/admin/workflows/{workflow_id}/steps` | Public | Add step to workflow |
| DELETE | `/admin/workflows/{workflow_id}/steps/{step_id}` | Public | Delete step |

### Notification Templates

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/admin/templates` | Public | List templates |
| GET | `/admin/templates/{template_id}` | Public | Template details (full body, variables) |
| POST | `/admin/templates` | Public | Create template |
| PATCH | `/admin/templates/{template_id}` | Public | Update template |
| POST | `/admin/templates/{template_id}/preview` | Public | Preview with sample context |

### Integrations

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/admin/integrations` | Public | List integrations |
| GET | `/admin/integrations/{id}` | Public | Integration details (credentials redacted) |
| POST | `/admin/integrations` | Public | Create integration |
| PATCH | `/admin/integrations/{id}` | Public | Update integration |
| POST | `/admin/integrations/{id}/test` | Public | Test connection health |
| POST | `/admin/integrations/{id}/teams/test-notification` | Public | Send test Teams notification |

### Approvers

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/admin/approvers` | Public | List approvers |
| POST | `/admin/approvers` | Public | Add approver to workflow |
| DELETE | `/admin/approvers/{approver_id}` | Public | Remove approver |

---

## 23. Compliance

**Prefix:** `/api/compliance`

### Rules

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/compliance/rules` | Any | List rules (filterable by industry, contract_type) |
| GET | `/api/compliance/rules/{rule_id}` | Any | Rule details |
| POST | `/api/compliance/rules` | Any | Create rule |
| PATCH | `/api/compliance/rules/{rule_id}` | Any | Update rule |
| DELETE | `/api/compliance/rules/{rule_id}` | Any | Delete rule (204) |

### Gaps

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/compliance/gaps` | Any | List gaps (filterable by severity/status, open/overdue) |
| GET | `/api/compliance/gaps/{gap_id}` | Any | Gap details |
| POST | `/api/compliance/gaps/{gap_id}/resolve` | Any | Resolve by linking document |
| POST | `/api/compliance/gaps/{gap_id}/waive` | Any | Waive requirement |
| PATCH | `/api/compliance/gaps/{gap_id}/status` | Any | Update gap status |
| GET | `/api/compliance/gaps/{gap_id}/suggestions` | Any | Suggest matching documents |

### Regulatory Obligations

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/compliance/obligations` | Any | List regulatory obligations |
| GET | `/api/compliance/obligations/{id}` | Any | Obligation details |
| PATCH | `/api/compliance/obligations/{id}/status` | Any | Update compliance status |

### Analysis & Dashboard

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/compliance/check/{contract_id}` | Any | Run compliance check (creates gaps/alerts) |
| POST | `/api/compliance/detect-industry/{contract_id}` | Any | Detect contract industry |
| GET | `/api/compliance/dashboard` | Any | Compliance dashboard |
| GET | `/api/compliance/by-industry` | Any | Compliance by industry |
| GET | `/api/compliance/contracts` | Any | Contracts with compliance summaries |

---

## 24. Connectors

**Prefix:** `/api/connectors`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/connectors/status` | Any | All connector statuses |
| GET | `/api/connectors/sla-actuals/{contract_id}` | Any | Actual SLA values from external system |
| GET | `/api/connectors/sla-history/{contract_id}` | Any | Historical SLA performance (1-24 months) |
| GET | `/api/connectors/milestones` | Any | Project milestone statuses |
| GET | `/api/connectors/milestones/timeline` | Any | Gantt-style milestone timeline |
| GET | `/api/connectors/fx/rate` | Any | Exchange rate (`base`, `target` params) |
| GET | `/api/connectors/fx/history` | Any | Historical FX rates |
| GET | `/api/connectors/fx/cola-adjustment` | Any | COLA adjustment calculation |
| GET | `/api/connectors/incident-metrics` | Any | Incident management metrics |
| POST | `/api/connectors/compare/{contract_id}` | Any | Full SLA comparison against actuals |
| GET | `/api/connectors/compliance-dashboard/{contract_id}` | Any | SLA compliance dashboard |

> **Note:** Connectors currently use stub data for demo purposes. Real ServiceNow/Salesforce integrations are planned.

---

## 25. Post-Signing Dashboard

**Prefix:** `/api/dashboard/postsigning`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/dashboard/postsigning` | Any | Complete post-signing dashboard |
| GET | `/api/dashboard/postsigning/obligations` | Any | Detailed obligation list |
| GET | `/api/dashboard/postsigning/slas` | Any | Detailed SLA list |

**Dashboard Widgets:**
- **Obligations:** total, completed, in_progress, overdue, compliance_rate, urgent_items
- **SLAs:** total, active, compliant, breached, penalties_MTD, recent_breaches
- **Renewals:** expiring 30/60/90, past_notice_deadline, value_at_risk
- **Vendors:** total, at_risk, avg_performance_score, top/bottom performers
- **Milestones:** total, completed, overdue, at_risk, due_this_week
- **Compliance:** overall_rate (60% obligations + 40% SLAs), trend, contracts_at_risk

---

## 26. Milestones

**Prefix:** `/api/milestones`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/milestones/health` | Any | Milestone health dashboard (statuses, time buckets) |
| GET | `/api/milestones/at-risk-contracts` | Any | Contracts at risk based on milestone status |
| GET | `/api/milestones/portfolio-compliance` | Any | Portfolio compliance metrics |
| PUT | `/api/milestones/{milestone_id}/owner` | Any | Assign milestone owner |

**Compliance Formula:** Overall = (Obligation Compliance x 0.6) + (SLA Compliance x 0.4)

**Time Buckets:** `overdue`, `this_week` (0-7 days), `next_week` (8-14), `this_month` (15-30), `future` (>30)

---

## 27. Knowledge Graph

**Prefix:** `/api/knowledge-graph`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/knowledge-graph/contracts/{id}/extract` | Any | Extract entities/relationships (async, 202) |
| GET | `/api/knowledge-graph/contracts/{id}` | Any | Full knowledge graph (nodes + edges) |
| GET | `/api/knowledge-graph/contracts/{id}/stats` | Any | Graph statistics |
| GET | `/api/knowledge-graph/contracts/{id}/entities` | Any | Search entities (by type/keyword) |
| GET | `/api/knowledge-graph/contracts/{id}/entities/{eid}` | Any | Entity with relationships |
| GET | `/api/knowledge-graph/contracts/{id}/resolve-term` | Any | Resolve defined term to meaning |
| GET | `/api/knowledge-graph/contracts/{id}/party-obligations` | Any | Party obligations with limits |
| GET | `/api/knowledge-graph/contracts/{id}/related-clauses` | Any | Related clauses (graph traversal, max depth 10) |
| GET | `/api/knowledge-graph/contracts/{id}/risk-analysis` | Any | Risk patterns (unlimited obligations, missing jurisdictions, undefined terms) |

---

## 28. Contract Links & Suggested Links

**Prefix:** `/api/contracts`

### Established Links (Approved)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/contracts/{id}/links` | Any | Get established parent-child links for a contract (16 link types) |

### AI-Suggested Links

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/contracts/{id}/suggested-links` | Any | Suggested links for contract (multi-signal scored) |
| POST | `/api/contracts/{id}/suggested-links/{sid}/review` | Any | Review: approve/reject/modify |
| GET | `/api/contracts/pending-suggestions` | Any | All pending suggestions for tenant |
| POST | `/api/contracts/{id}/suggested-links/batch-review` | Any | Batch approve/reject |

**Auto-Link Detection Signals:** Counterparty match (30%), fuzzy match (20%), type hierarchy (25%), semantic similarity (20%), filename pattern (15%), date proximity (10%).

---

## 29. Master Data Admin

**Prefix:** `/api/admin/master-data`

### SLA Master Data

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/admin/master-data/slas` | Admin | List SLA configs |
| POST | `/api/admin/master-data/slas` | Admin | Create SLA config |
| GET | `/api/admin/master-data/slas/{id}` | Admin | Get SLA config |
| PUT | `/api/admin/master-data/slas/{id}` | Admin | Update SLA config |
| DELETE | `/api/admin/master-data/slas/{id}` | Admin | Delete SLA config (204) |
| POST | `/api/admin/master-data/slas/seed` | Admin | Seed from stubs |

### Milestone Master Data

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/admin/master-data/milestones` | Admin | List milestone configs |
| POST | `/api/admin/master-data/milestones` | Admin | Create milestone config |
| GET | `/api/admin/master-data/milestones/{id}` | Admin | Get milestone config |
| PUT | `/api/admin/master-data/milestones/{id}` | Admin | Update milestone config |
| DELETE | `/api/admin/master-data/milestones/{id}` | Admin | Delete milestone config (204) |
| POST | `/api/admin/master-data/milestones/seed` | Admin | Seed from stubs |

### Maintenance

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/admin/master-data/seed-all` | Admin | Seed all master data |
| POST | `/api/admin/master-data/cleanup-vectors` | Admin | Clean orphaned ChromaDB vectors |
| GET | `/api/admin/master-data/vector-stats` | Admin | Vector store consistency check |

---

## 30. Scheduler Admin

**Prefix:** `/api/admin/scheduler`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/admin/scheduler/status` | Admin | Overall scheduler status |
| GET | `/api/admin/scheduler/jobs` | Admin | List all jobs |
| GET | `/api/admin/scheduler/jobs/{job_name}` | Admin | Job details and metrics |
| PATCH | `/api/admin/scheduler/jobs/{job_name}` | Admin | Update job config (interval, enabled) |
| POST | `/api/admin/scheduler/jobs/{job_name}/run` | Admin | Trigger immediate run |
| GET | `/api/admin/scheduler/jobs/{job_name}/history` | Admin | Execution history |
| POST | `/api/admin/scheduler/start` | Admin | Start scheduler |
| POST | `/api/admin/scheduler/stop` | Admin | Stop scheduler |

---

## 31. Settings (Langfuse)

**Prefix:** `/api/settings`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/settings/langfuse/status` | Admin | Langfuse integration status |
| POST | `/api/settings/langfuse/sync-prompts` | Admin | Sync local prompts to Langfuse |
| GET | `/api/settings/langfuse/prompts` | Admin | List all prompts |
| GET | `/api/settings/langfuse/prompts/{name}` | Admin | Get specific prompt |
| POST | `/api/settings/langfuse/flush` | Admin | Flush pending events |
| DELETE | `/api/settings/langfuse/prompts/cache` | Admin | Clear prompt cache |

---

## 32. Custom Fields

### Admin (Prefix: `/api/admin/custom-fields`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/admin/custom-fields/{entity_type}` | Admin | List field definitions |
| POST | `/api/admin/custom-fields/{entity_type}` | Admin | Create field |
| GET | `/api/admin/custom-fields/{entity_type}/{field_name}` | Admin | Get field definition |
| PUT | `/api/admin/custom-fields/{entity_type}/{field_name}` | Admin | Update field (cannot change type) |
| DELETE | `/api/admin/custom-fields/{entity_type}/{field_name}` | Admin | Delete field (`hard_delete` param) |
| POST | `/api/admin/custom-fields/{entity_type}/reorder` | Admin | Reorder fields |

### Public (Prefix: `/api/custom-fields`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/custom-fields/{entity_type}` | Any | Read-only field definitions for tenant |

**Field Types:** `text`, `textarea`, `number`, `dropdown`, `multi_select`, `date`, `checkbox`

---

## 33. Organizations

**Prefix:** `/organizations`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/organizations` | Any | List organizations (paginated, filterable) |
| POST | `/organizations` | Admin/Legal | Create organization |
| GET | `/organizations/{org_id}` | Any | Get organization |
| PUT | `/organizations/{org_id}` | Admin/Legal | Update organization |
| DELETE | `/organizations/{org_id}` | Admin | Delete/deactivate (`hard_delete` param) |
| GET | `/organizations/{org_id}/relationships` | Any | Organization's relationships |

**Types:** `customer`, `vendor`, `partner`, `internal`

**Sizes:** `startup`, `small`, `medium`, `large`, `enterprise`

---

## 34. Relationships

**Prefix:** `/relationships`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/relationships` | Any | List relationships (paginated, filterable) |
| POST | `/relationships` | Admin/Legal | Create relationship |
| GET | `/relationships/{rel_id}` | Any | Get relationship with team members |
| PUT | `/relationships/{rel_id}` | Admin/Legal | Update relationship |
| GET | `/relationships/{rel_id}/team` | Any | List team members |
| POST | `/relationships/{rel_id}/team` | Admin/Legal | Add team member |
| PUT | `/relationships/{rel_id}/team/{member_id}` | Admin/Legal | Update team member |
| DELETE | `/relationships/{rel_id}/team/{member_id}` | Admin/Legal | Remove team member (soft, 204) |
| GET | `/relationships/{rel_id}/health` | Any | Health score with breakdown |

**Relationship Types:** `customer_vendor`, `partnership`, `internal`, `consulting`

**Governance Tiers:** `strategic`, `managed`, `transactional`

---

## 35. KPIs & Perception

**Prefix:** `/kpis`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/kpis` | Any | List KPIs (filter by relationship, category) |
| POST | `/kpis` | Any | Create KPI |
| GET | `/kpis/{kpi_id}` | Any | Get KPI with latest perception data |
| PUT | `/kpis/{kpi_id}` | Any | Update KPI |
| DELETE | `/kpis/{kpi_id}` | Any | Soft delete KPI (204) |
| GET | `/kpis/{kpi_id}/scores` | Any | List perception scores |
| POST | `/kpis/{kpi_id}/scores` | Any | Submit perception score |
| GET | `/kpis/{kpi_id}/gaps` | Any | Perception gaps for KPI |
| GET | `/kpis/relationship/{rel_id}/gaps` | Any | All gaps for relationship |
| GET | `/kpis/relationship/{rel_id}/summary` | Any | Gap summary for period |

**Perception Gap:** Difference between internal and external scores per KPI per period. Auto-calculated when scores are submitted.

**Gap Severities:** `minor`, `significant`, `critical`

---

## 36. Improvements

**Prefix:** `/improvements`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/improvements` | Any | List improvements (paginated, filterable) |
| POST | `/improvements` | Any | Create improvement point |
| GET | `/improvements/{id}` | Any | Get improvement with actions |
| PUT | `/improvements/{id}` | Any | Update improvement |
| DELETE | `/improvements/{id}` | Any | Cancel improvement (204) |
| GET | `/improvements/{id}/actions` | Any | List actions for improvement |
| POST | `/improvements/{id}/actions` | Any | Add action |
| PUT | `/improvements/{id}/actions/{action_id}` | Any | Update action |
| DELETE | `/improvements/{id}/actions/{action_id}` | Any | Delete action (204) |
| GET | `/improvements/relationship/{rel_id}/summary` | Any | Summary for relationship |
| POST | `/improvements/generate-from-gaps` | Any | Auto-generate from perception gaps |

**Statuses:** `open`, `in_progress`, `completed`, `blocked`, `cancelled`

**Priorities:** `low`, `medium`, `high`, `critical`

---

## 37. Surveys

**Prefix:** `/surveys`

### Templates (Admin manages, any user reads)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/surveys/templates` | Any | List templates |
| POST | `/surveys/templates` | Admin | Create template with questions |
| GET | `/surveys/templates/{id}` | Any | Get template with questions |
| PUT | `/surveys/templates/{id}` | Admin | Update template |
| DELETE | `/surveys/templates/{id}` | Admin | Soft delete template (204) |
| POST | `/surveys/templates/{id}/questions` | Admin | Add question |
| PUT | `/surveys/templates/{id}/questions/{qid}` | Admin | Update question |
| DELETE | `/surveys/templates/{id}/questions/{qid}` | Admin | Soft delete question (204) |

### Instances (Survey lifecycle)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/surveys/instances` | Any | List instances (paginated, filterable) |
| POST | `/surveys/instances` | Admin/Legal | Create instance |
| GET | `/surveys/instances/{id}` | Any | Get instance |
| PUT | `/surveys/instances/{id}` | Admin/Legal | Update instance |
| POST | `/surveys/instances/{id}/send` | Admin/Legal | Send survey (DRAFT -> IN_PROGRESS) |
| POST | `/surveys/instances/{id}/close` | Admin/Legal | Close survey (IN_PROGRESS -> CLOSED) |
| GET | `/surveys/instances/{id}/responses` | Any | List responses |
| GET | `/surveys/instances/{id}/responses/{rid}` | Any | Get response details |
| POST | `/surveys/instances/{id}/generate-token` | Admin/Legal | Generate external access token |

### External (No Auth - Token-Based)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/surveys/external/{token}` | Public | Get survey context (template, questions) |
| POST | `/surveys/external/{token}` | Public | Submit survey response |

**Question Types:** `rating` (1-5), `text`, `multiple_choice`, `yes_no`

---

## 38. Business Units

**Prefix:** `/api/business-units`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/business-units` | Any | List business units (paginated, searchable) |
| GET | `/api/business-units/tree` | Any | Hierarchical tree structure |
| POST | `/api/business-units` | Admin | Create business unit |
| GET | `/api/business-units/{bu_id}` | Any | Get with parent/children/full_path |
| PUT | `/api/business-units/{bu_id}` | Admin | Update (validates no circular refs) |
| DELETE | `/api/business-units/{bu_id}` | Admin | Deactivate (soft delete, 204) |
| GET | `/api/business-units/{bu_id}/users` | Any | Users in business unit |
| GET | `/api/business-units/{bu_id}/contracts` | Any | Contract summary for business unit |

---

## 39. External Users

**Prefix:** `/api/external-users`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/external-users` | Any | List external users (paginated) |
| POST | `/api/external-users` | Admin/Legal | Create external user |
| POST | `/api/external-users/invite` | Admin/Legal | Invite and share contracts in one step |
| GET | `/api/external-users/{id}` | Any | Get with share count |
| PUT | `/api/external-users/{id}` | Admin/Legal | Update external user |
| DELETE | `/api/external-users/{id}` | Admin/Legal | Revoke access (cascades to shares/tokens) |
| POST | `/api/external-users/{id}/resend-invite` | Admin/Legal | Resend invitation with new token |
| GET | `/api/external-users/{id}/shares` | Any | List contract shares |

### POST `/api/external-users/invite`

**Request:**
```json
{
  "email": "vendor@example.com",
  "full_name": "Jane Vendor",
  "company_name": "Vendor Corp",
  "contract_ids": ["uuid1", "uuid2"],
  "expires_in_days": 30,
  "can_download": true,
  "can_comment": true,
  "message": "Please review these contracts."
}
```

**Response:** Returns external user, number of shares created, access token, and access URL.

---

## 40. External Portal

**Prefix:** `/api/external` | **Auth:** Token-based (no JWT)

All endpoints require a `token` query parameter.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/external/validate?token=...` | Token | Validate token, get user and contract info |
| GET | `/api/external/contracts?token=...` | Token | List shared contracts |
| GET | `/api/external/contracts/{id}?token=...` | Token | View contract details (clauses truncated) |
| GET | `/api/external/contracts/{id}/download?token=...` | Token | Download contract file (if permitted) |
| GET | `/api/external/contracts/{id}/comments?token=...` | Token | List comments (non-internal only) |
| POST | `/api/external/contracts/{id}/comments?token=...` | Token | Add comment (if permitted) |

> External users only see non-internal comments and cannot create internal comments.

---

## 41. Health & System

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | Public | Root endpoint (API info) |
| GET | `/api/health` | Public | Service health (ChromaDB, OpenAI, Langfuse) |
| GET | `/api/system-health` | Public | Comprehensive health (DB, CPU, memory, disk, process) |

### GET `/api/health`

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {
    "chromadb": "healthy",
    "openai": "healthy",
    "langfuse": "healthy",
    "agents_registered": 8
  }
}
```

---

## Endpoint Summary

| Category | Endpoints | Description |
|----------|-----------|-------------|
| Authentication | 3 | Login, current user, logout |
| Tenants | 8 | Multi-tenant management |
| Users | 8 | User CRUD with RBAC |
| Audit Logs | 3 | Audit log viewing and stats |
| Clients | 6 | Client management |
| Contracts | 28 | Upload, CRUD, search, sharing, comments |
| Amendments | 7 | Version history, diffs, supersedes |
| Schemas | 7 | Extraction schemas and AI extraction |
| Obligations | 7 | Obligation tracking with RAG status |
| SLA Tracking | 8 | SLA management and breach detection |
| Renewals | 6 | Calendar, recommendations, ICS export |
| Vendors | 5 | Performance scoring and comparison |
| Dashboards | 21 | Role-based and contract-level dashboards |
| Query & AI | 3 | RAG Q&A and AI analysis |
| Chat Sessions | 6 | Chat session and message management |
| Reports | 4 | Compliance reports and CSV export |
| Metrics | 5 | Trend data and snapshots |
| Alerts | 12 | Alert lifecycle management |
| Monitor & Events | 10 | Event detection and workflow execution |
| Notifications | 7 | Notification management and retry |
| Notification Rules | 9 | Configurable notification rules |
| Workflow Admin | 19 | Workflows, templates, integrations, approvers |
| Compliance | 17 | Rules, gaps, regulatory obligations |
| Connectors | 11 | External system integrations (stubs) |
| Post-Signing | 3 | Post-signing governance dashboard |
| Milestones | 4 | Milestone health and compliance |
| Knowledge Graph | 9 | Entity extraction and graph analysis |
| Contract Links & Suggested Links | 5 | Established links + AI-detected relationships |
| Master Data | 15 | SLA/Milestone configs and maintenance |
| Scheduler | 8 | Background job management |
| Settings | 6 | Langfuse prompt management |
| Custom Fields | 7 | Tenant-specific field definitions |
| Organizations | 6 | Organization management (Evaluetor) |
| Relationships | 9 | Business relationship management |
| KPIs | 10 | KPI and perception scoring |
| Improvements | 11 | Improvement tracking and actions |
| Surveys | 20 | Templates, instances, external access |
| Business Units | 8 | Hierarchical business unit management |
| External Users | 8 | External user and invitation management |
| External Portal | 6 | Token-based external contract access |
| Health & System | 3 | Health checks |
| **Total** | **~311** | |

---

## Error Responses

All endpoints return errors in a consistent format:

```json
{
  "detail": "Error message describing the issue"
}
```

| Status Code | Meaning |
|-------------|---------|
| 400 | Bad Request - Invalid parameters or validation failure |
| 401 | Unauthorized - Missing or invalid JWT token |
| 403 | Forbidden - Insufficient role permissions |
| 404 | Not Found - Resource does not exist or not in tenant |
| 409 | Conflict - Duplicate resource (username, email, code) |
| 422 | Unprocessable Entity - Request body validation error |
| 500 | Internal Server Error |

---

## Common Patterns

### Soft Deletes
Users, tenants, organizations, business units, and KPIs use soft delete (`is_active=false`). Contracts use hard delete with cascade to all related data.

### Audit Logging
All significant actions are logged: login/logout, contract upload/delete, queries, status changes. Logs include user ID, IP address, user agent, and timestamp.

### Tenant Isolation
All queries are automatically scoped to the authenticated user's tenant via SQLAlchemy filters. Super admins can bypass tenant isolation.

### File Uploads
File uploads use `multipart/form-data`. Supported formats: PDF, DOCX. Maximum batch size: 50 files.

---

*Last Updated: 2026-03-07*
*Document Owner: Development Team*
*Total API Endpoints: ~311*
