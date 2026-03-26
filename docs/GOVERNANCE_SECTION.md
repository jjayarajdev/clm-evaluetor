# Governance Section - Complete Implementation Guide

## Overview

The Governance section implements **Evaluetor's Relationship Governance Framework** - a structured approach to managing business relationships through perception-based KPI scoring, gap analysis, and continuous improvement tracking. It spans 16 database tables, 7 API routers with 70+ endpoints, and 9 frontend pages.

The core philosophy: relationships are measured not just by hard SLA metrics, but by **perception gaps** between how each party views performance. When internal teams rate themselves 4.5/5 on "Communication Clarity" but the external partner rates them 3.2/5, that 1.3-point gap surfaces a blind spot that traditional metrics miss.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                         │
│  9 Governance Pages + API Client (src/lib/api.ts)               │
├─────────────────────────────────────────────────────────────────┤
│                        BACKEND (FastAPI)                        │
│  7 Routers → Models → PostgreSQL                                │
│  Organizations │ Relationships │ KPIs │ Improvements │ Surveys  │
│  Service Portfolio │ KPI Approvals                               │
├─────────────────────────────────────────────────────────────────┤
│                      DATABASE (PostgreSQL)                       │
│  16 Tables with multi-tenant isolation (tenant_id on every row) │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Organizations ──┐
                ├── Business Relationships ──┬── KPIs ──┬── Perception Scores ──► Approval Workflow
                │                            │          ├── Perception Gaps ─────► Gap Analysis
                │                            │          └── Improvement Points ──► Action Tracking
                │                            ├── Team Members
                │                            ├── Status History ──► Performance Trends
                │                            ├── Survey Instances ──► Responses
                │                            └── Service Links
                ├── Organization Officers
                └── Service Portfolio
```

---

## 1. Organization Management

### Database Model

**Table: `organizations`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `tenant_id` | UUID (FK → tenants) | Multi-tenant isolation |
| `name` | VARCHAR(255) | Organization name |
| `code` | VARCHAR(50) | Short code, unique per tenant |
| `org_type` | ENUM | `customer`, `vendor`, `partner`, `internal` |
| `parent_organization_id` | UUID (FK → self) | Hierarchy - parent org |
| `organization_level` | ENUM | `holding`, `subsidiary`, `division`, `branch`, `department` |
| `industry` | VARCHAR(100) | e.g., "Manufacturing", "Technology" |
| `size` | ENUM | `startup`, `smb`, `mid_market`, `enterprise`, `global` |
| `region` | VARCHAR(100) | Geographic region |
| `country` | VARCHAR(100) | Country |
| `website` | VARCHAR(255) | |
| `address` | TEXT | |
| `primary_contact_name` | VARCHAR(255) | |
| `primary_contact_email` | VARCHAR(255) | |
| `primary_contact_phone` | VARCHAR(50) | |
| `relationship_owner_id` | UUID (FK → users) | Owner |
| `is_active` | BOOLEAN | Soft delete flag (default: true) |
| `notes` | TEXT | |
| `created_at`, `updated_at` | TIMESTAMP | |

**Table: `organization_officers`** - Key contacts/governance personnel

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `tenant_id` | UUID (FK) | |
| `organization_id` | UUID (FK → organizations) | |
| `name` | VARCHAR(255) | Officer name |
| `title` | VARCHAR(255) | Job title |
| `email` | VARCHAR(255) | |
| `phone` | VARCHAR(50) | |
| `department` | VARCHAR(100) | |
| `governance_role` | ENUM | See below |
| `side` | ENUM | `internal`, `external` |
| `is_primary` | BOOLEAN | Primary contact flag |
| `is_active` | BOOLEAN | |
| `notes` | TEXT | |

**Governance Roles:** `account_manager`, `service_delivery_manager`, `relationship_owner`, `executive_sponsor`, `commercial_manager`, `technical_lead`, `operations_lead`, `compliance_officer`, `other`

### API Endpoints (14 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/organizations` | List with search, type/industry/region/active filters, pagination |
| POST | `/api/organizations` | Create (validates unique code per tenant) |
| GET | `/api/organizations/tree` | Full hierarchical tree (nested children) |
| GET | `/api/organizations/{id}` | Get single organization |
| PUT | `/api/organizations/{id}` | Update |
| DELETE | `/api/organizations/{id}` | Soft delete (or hard delete with `?hard_delete=true`) |
| GET | `/api/organizations/{id}/subsidiaries` | Direct child organizations |
| GET | `/api/organizations/{id}/hierarchy` | Full context: parent chain + children |
| GET | `/api/organizations/{id}/relationships` | Bidirectional relationship lookup |
| GET | `/api/organizations/{id}/officers` | List officers (filter by role, side, active) |
| POST | `/api/organizations/{id}/officers` | Create officer |
| PUT | `/api/organizations/{id}/officers/{oid}` | Update officer |
| DELETE | `/api/organizations/{id}/officers/{oid}` | Soft delete officer |

### Frontend Pages

**Organizations List** (`/organizations`)
- Searchable/filterable table with org type badges
- Create modal with full form validation
- Click-through to detail page

**Organization Detail** (`/organizations/:id`)
- Tabs: Overview | Officers | Hierarchy | Relationships
- Officers tab: CRUD with governance role/side assignment
- Hierarchy tab: visual tree showing parent chain and subsidiaries
- Relationships tab: all business relationships involving this org

---

## 2. Business Relationships

### Database Models

**Table: `business_relationships`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `tenant_id` | UUID (FK) | |
| `org_a_id` | UUID (FK → organizations) | Party A (typically internal) |
| `org_b_id` | UUID (FK → organizations) | Party B (external partner) |
| `relationship_type` | ENUM | `customer`, `supplier`, `partner`, `joint_venture`, `reseller`, `distributor` |
| `status` | ENUM | `prospecting`, `active`, `at_risk`, `on_hold`, `terminated` |
| `name` | VARCHAR(255) | e.g., "Acme Corporation - Strategic Client" |
| `description` | TEXT | |
| `health_score` | INTEGER | 0-100 composite score |
| `last_health_calculation` | TIMESTAMP | |
| `governance_tier` | ENUM | `operational`, `tactical`, `strategic`, `executive` |
| `governance_config` | JSON | Custom governance rules |
| `start_date` | TIMESTAMP | |
| `review_frequency_days` | INTEGER | e.g., 30, 90 |
| `next_review_date` | TIMESTAMP | |

**Table: `relationship_teams`** - People assigned to manage a relationship

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `relationship_id` | UUID (FK) | |
| `user_id` | UUID (FK → users) | Platform user |
| `role` | ENUM | `relationship_manager`, `account_manager`, `executive_sponsor`, `technical_lead`, `operations_lead`, `finance_lead`, `member` |
| `responsibilities` | JSON | List of responsibility strings |
| `is_primary` | BOOLEAN | |
| `is_active` | BOOLEAN | |
| `joined_at`, `left_at` | TIMESTAMP | |

**Table: `relationship_status_history`** - Performance status over time

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `tenant_id` | UUID (FK) | |
| `relationship_id` | UUID (FK) | |
| `status` | ENUM | `excellent`, `good`, `acceptable`, `concerning`, `poor`, `critical` |
| `previous_status` | ENUM | Previous period's status |
| `overall_score` | NUMERIC(5,2) | 0-100 |
| `period` | VARCHAR(20) | e.g., "2025-Q1", "2025-Q4" |
| `recorded_date` | TIMESTAMP | |
| `recorded_by` | UUID (FK → users) | |
| `notes` | TEXT | Context for the assessment |
| `trigger` | VARCHAR(100) | `manual`, `kpi_evaluation_cycle`, `health_score_recalc` |

### API Endpoints (14 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/relationships` | List with type/status/org/my_relationships filters |
| POST | `/api/relationships` | Create (validates both orgs exist, not same org) |
| GET | `/api/relationships/{id}` | Get with team members loaded |
| PUT | `/api/relationships/{id}` | Update |
| GET | `/api/relationships/{id}/team` | List team members |
| POST | `/api/relationships/{id}/team` | Add team member |
| PUT | `/api/relationships/{id}/team/{mid}` | Update (auto-sets left_at on deactivation) |
| DELETE | `/api/relationships/{id}/team/{mid}` | Soft remove |
| GET | `/api/relationships/{id}/health` | Health score with breakdown |
| GET | `/api/relationships/{id}/history` | Status history (paginated, newest first) |
| POST | `/api/relationships/{id}/history` | Record status entry (auto-lookups previous status) |
| GET | `/api/relationships/{id}/performance-trend` | Trend data for charting (deduplicated by period) |

### Frontend Pages

**Relationships List** (`/relationships`)
- Card grid layout (responsive 1/2/3 columns)
- Each card shows: status badge, health score (color-coded), org names, governance tier
- Create modal with org dropdowns

**Relationship Detail** (`/relationships/:id`) - ~1,600 lines, the richest page
- **8 tabs:**
  1. **Overview** - Status, parties, health score, governance tier, review frequency
  2. **Team** - Team members with roles, add/remove
  3. **KPIs** - Perception scorecard with internal/external comparison
  4. **Improvements** - Gap-linked improvements with progress bars
  5. **Service Portfolio** - Linked services
  6. **Surveys** - Survey instances
  7. **Performance Trends** - Line chart of score over time
  8. **Document Insights** - Contract summaries, risks, obligations

---

## 3. KPI & Perception Scoring (Core Innovation)

This is the heart of the governance system. Each KPI can be scored from two perspectives (internal and external), and the **gap between those scores** drives the improvement cycle.

### Database Models

**Table: `kpis`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `relationship_id` | UUID (FK) | Linked to a business relationship |
| `name` | VARCHAR(255) | e.g., "On-Time Delivery Rate" |
| `code` | VARCHAR(50) | Short code: "OTD" |
| `description` | TEXT | |
| `category` | ENUM | `service_delivery`, `quality`, `timeliness`, `communication`, `innovation`, `cost_efficiency`, `compliance`, `satisfaction`, `other` |
| `measurement_type` | ENUM | `percentage`, `number`, `currency`, `time_hours`, `time_days`, `rating`, `boolean` |
| `target_value` | NUMERIC(12,2) | e.g., 95.00 for 95% |
| `minimum_value` | NUMERIC(12,2) | Minimum acceptable |
| `threshold_amber` | NUMERIC(12,2) | Warning threshold |
| `threshold_red` | NUMERIC(12,2) | Critical threshold |
| `weight` | NUMERIC(5,2) | Scoring weight (default: 1.0) |
| `is_active` | BOOLEAN | |
| `is_perception_based` | BOOLEAN | Uses dual-perspective scoring |

**Table: `perception_scores`** - Individual scores from internal/external perspectives

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `kpi_id` | UUID (FK) | |
| `scorer_org_id` | UUID (FK → organizations) | Who scored |
| `scored_by_user_id` | UUID (FK → users) | Individual scorer |
| `score` | NUMERIC(5,2) | Rating (typically 1-10) |
| `period` | VARCHAR(20) | "2025-Q1" |
| `comments` | TEXT | |
| `is_internal` | BOOLEAN | Internal vs. external perspective |
| `approval_status` | ENUM | `draft`, `pending_approval`, `approved`, `rejected` |
| `approved_by` | UUID (FK → users) | |
| `approved_at` | TIMESTAMP | |
| `approval_comments` | TEXT | |
| `scored_at` | TIMESTAMP | |

**Table: `perception_gaps`** - Calculated gaps between internal and external scores

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `kpi_id` | UUID (FK) | |
| `period` | VARCHAR(20) | |
| `internal_score` | NUMERIC(5,2) | Average internal score for period |
| `external_score` | NUMERIC(5,2) | Average external score for period |
| `gap` | NUMERIC(5,2) | internal - external (positive = overconfidence) |
| `gap_severity` | ENUM | Auto-calculated: see below |
| `requires_action` | BOOLEAN | Flag for gaps needing improvement |
| `notes` | TEXT | |

**Gap Severity Calculation:**
| Absolute Gap | Severity |
|-------------|----------|
| < 1.0 | `minor` |
| 1.0 - 2.0 | `moderate` |
| 2.0 - 3.0 | `significant` |
| > 3.0 | `critical` |

### Approval Workflow

```
Score Submitted ──► pending_approval ──┬──► approved (by admin/legal) ──► Gap Recalculated
                                       └──► rejected (with comments)
```

Only **approved** scores feed into gap calculations. This prevents premature or incorrect scores from distorting the analysis.

### API Endpoints (16 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/kpis` | List with relationship/category/active filters |
| POST | `/api/kpis` | Create KPI linked to relationship |
| GET | `/api/kpis/{id}` | Get with latest scores/gaps |
| PUT | `/api/kpis/{id}` | Update |
| DELETE | `/api/kpis/{id}` | Soft delete |
| GET | `/api/kpis/{id}/scores` | List scores (filter by period, is_internal) |
| POST | `/api/kpis/{id}/scores` | Submit score (auto-determines org, recalculates gap) |
| GET | `/api/kpis/pending-approvals` | List scores awaiting approval (admin/legal only) |
| POST | `/api/kpis/{id}/scores/{sid}/approve` | Approve score, recalculate gap |
| POST | `/api/kpis/{id}/scores/{sid}/reject` | Reject score with comments |
| GET | `/api/kpis/{id}/gaps` | List gaps for a KPI |
| GET | `/api/kpis/relationship/{rid}/gaps` | All gaps for a relationship (filter severity, period) |
| GET | `/api/kpis/relationship/{rid}/summary` | Gap summary: counts by severity, average gap, worst KPI |

### Frontend Pages

**KPI Scorecard** (`/kpis`)
- Relationship dropdown selector
- Summary cards: total KPIs, critical/significant/aligned gap counts
- KPI table with category, target, weight columns

**KPI Approvals** (`/kpi-approvals`) - Admin only
- Pending approvals table with perspective badge (internal/external)
- Approve/reject modal with comments
- Summary cards: pending count, internal/external breakdowns

---

## 4. Improvement Tracking

Improvements are action items born from perception gaps, SLA breaches, review meetings, customer feedback, or internal audits. Each improvement links back to the KPI and gap that triggered it.

### Database Models

**Table: `improvement_points`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `relationship_id` | UUID (FK) | |
| `kpi_id` | UUID (FK, nullable) | Linked KPI |
| `gap_id` | UUID (FK → perception_gaps, nullable) | Linked gap |
| `title` | VARCHAR(255) | |
| `description` | TEXT | |
| `source` | ENUM | `perception_gap`, `sla_breach`, `review_meeting`, `customer_feedback`, `internal_audit`, `manual` |
| `priority` | ENUM | `low`, `medium`, `high`, `critical` |
| `status` | ENUM | `open`, `in_progress`, `blocked`, `completed`, `cancelled` |
| `owner_id` | UUID (FK → users) | Responsible person |
| `assigned_org_id` | UUID (FK → organizations) | Responsible org |
| `due_date` | DATE | |
| `started_at`, `completed_at` | TIMESTAMP | Auto-set on status transitions |
| `target_outcome` | TEXT | What we want to achieve |
| `actual_outcome` | TEXT | What actually happened |
| `impact_score` | INTEGER | 1-10 post-completion impact |

**Table: `improvement_actions`** - Granular steps within an improvement

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `improvement_id` | UUID (FK) | |
| `description` | TEXT | Action step |
| `status` | ENUM | `todo`, `in_progress`, `completed`, `blocked`, `cancelled` |
| `sequence` | INTEGER | Execution order |
| `owner_id` | UUID (FK → users) | |
| `due_date` | DATE | |
| `notes` | TEXT | |
| `blocker_reason` | TEXT | Why blocked |

**Computed:** `progress_percentage` = (completed_actions / total_actions) * 100

### Auto-Generation from Gaps

```
POST /api/improvements/generate-from-gaps?relationship_id=...&period=2025-Q1&min_severity=significant
```

Automatically creates improvement points for all perception gaps meeting the severity threshold. Avoids duplicates by checking existing gap linkages.

### API Endpoints (11 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/improvements` | List with status/priority/owner/overdue filters |
| POST | `/api/improvements` | Create linked to relationship/KPI/gap |
| GET | `/api/improvements/{id}` | Get with actions |
| PUT | `/api/improvements/{id}` | Update (auto-sets started_at, completed_at) |
| DELETE | `/api/improvements/{id}` | Soft delete (sets status=cancelled) |
| GET | `/api/improvements/{id}/actions` | List actions (ordered by sequence) |
| POST | `/api/improvements/{id}/actions` | Add action step |
| PUT | `/api/improvements/{id}/actions/{aid}` | Update action |
| DELETE | `/api/improvements/{id}/actions/{aid}` | Delete action |
| GET | `/api/improvements/relationship/{rid}/summary` | Counts by status + overdue + priority |
| POST | `/api/improvements/generate-from-gaps` | Auto-create from perception gaps |

### Frontend Page

**Improvements** (`/improvements`)
- Filter by status and priority dropdowns
- Summary cards: open, in_progress, blocked, completed, cancelled counts
- Improvement cards with priority/status badges, source tags, progress bars
- Create modal linked to relationship and KPI

---

## 5. Service Portfolio

Tracks what services organizations provide and links them to business relationships.

### Database Models

**Table: `service_portfolios`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `tenant_id` | UUID (FK) | |
| `organization_id` | UUID (FK → organizations) | Service provider |
| `name` | VARCHAR(255) | e.g., "Cloud Infrastructure Services" |
| `code` | VARCHAR(50) | Unique per tenant |
| `description` | TEXT | |
| `service_type` | ENUM | `it_services`, `consulting`, `legal`, `financial`, `logistics`, `manufacturing`, `marketing`, `hr`, `procurement`, `other` |
| `status` | ENUM | `active`, `inactive`, `planned`, `deprecated` |

**Table: `relationship_services`** - Links services to relationships

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `relationship_id` | UUID (FK) | |
| `service_portfolio_id` | UUID (FK) | |
| `scope` | TEXT | Service scope for this relationship |
| `start_date`, `end_date` | TIMESTAMP | |
| `is_active` | BOOLEAN | |

### API Endpoints (8 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/service-portfolio` | List with search/type/status/org filters |
| POST | `/api/service-portfolio` | Create (validates unique code) |
| GET | `/api/service-portfolio/organization/{oid}` | Services for an org |
| GET | `/api/service-portfolio/{id}` | Get single |
| PUT | `/api/service-portfolio/{id}` | Update |
| DELETE | `/api/service-portfolio/{id}` | Soft delete (sets status=deprecated) |
| GET | `/api/service-portfolio/{id}/relationships` | Linked relationships |
| POST | `/api/service-portfolio/{id}/relationships` | Link to relationship |
| DELETE | `/api/service-portfolio/{id}/relationships/{rsid}` | Unlink |

### Frontend Page

**Service Portfolio** (`/service-portfolio`)
- Search, type filter, status filter
- Summary cards: total, active, planned, type count
- Table with service name, code, type, organization, status badge
- Create modal with org dropdown

---

## 6. Surveys

Structured feedback collection linked to relationships and KPIs.

### Database Models

**Table: `survey_templates`** - Reusable survey designs

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `name` | VARCHAR(255) | |
| `description` | TEXT | |
| `frequency` | ENUM | `one_time`, `monthly`, `quarterly`, `semi_annual`, `annual` |
| `introduction_text` | TEXT | Survey intro message |
| `closing_text` | TEXT | Thank you message |
| `allow_anonymous` | BOOLEAN | |
| `require_all_questions` | BOOLEAN | |
| `is_active` | BOOLEAN | |
| `version` | INTEGER | Auto-incremented on update |

**Table: `survey_questions`** - Questions within a template

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `template_id` | UUID (FK) | |
| `text` | TEXT | Question text |
| `help_text` | TEXT | Guidance |
| `question_type` | ENUM | `rating`, `rating_5`, `multiple_choice`, `single_choice`, `text`, `text_long`, `yes_no`, `nps` |
| `options` | JSON | For choice questions |
| `rating_min_label`, `rating_max_label` | VARCHAR(100) | e.g., "Poor" / "Excellent" |
| `kpi_id` | UUID (FK, nullable) | Link question to KPI |
| `sequence` | INTEGER | Display order |
| `is_required` | BOOLEAN | |

**Table: `survey_instances`** - Sent survey campaigns

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `template_id` | UUID (FK) | |
| `relationship_id` | UUID (FK) | Target relationship |
| `period` | VARCHAR(20) | "2025-Q1" |
| `status` | ENUM | `draft`, `scheduled`, `sent`, `in_progress`, `completed`, `expired`, `cancelled` |
| `scheduled_send_date`, `sent_at`, `due_date`, `closed_at` | DATE/TIMESTAMP | |
| `target_respondent_count` | INTEGER | |
| `actual_respondent_count` | INTEGER | |

**Table: `survey_responses`** - Individual respondent answers

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `survey_instance_id` | UUID (FK) | |
| `respondent_email`, `respondent_name` | VARCHAR(255) | |
| `respondent_org_id` | UUID (FK, nullable) | |
| `is_anonymous` | BOOLEAN | |
| `answers` | JSON | `{question_id: answer_value}` |
| `completion_time_seconds` | INTEGER | |
| `is_complete` | BOOLEAN | |
| `access_token` | VARCHAR(100) | For public survey links |

**Computed:** `response_rate` = (actual / target) * 100

### API Endpoints (12 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/surveys/templates` | List (active_only filter) |
| POST | `/api/surveys/templates` | Create with embedded questions |
| GET | `/api/surveys/templates/{id}` | Get with questions |
| PUT | `/api/surveys/templates/{id}` | Update (auto-increments version) |
| DELETE | `/api/surveys/templates/{id}` | Soft delete |
| POST | `/api/surveys/templates/{id}/questions` | Add question |
| PUT | `/api/surveys/templates/{id}/questions/{qid}` | Update question |
| DELETE | `/api/surveys/templates/{id}/questions/{qid}` | Remove question |
| GET | `/api/surveys/instances` | List (relationship/template/status filters) |
| POST | `/api/surveys/instances` | Create for a relationship |
| POST | `/api/surveys/instances/{id}/send` | Send survey (draft → in_progress) |
| POST | `/api/surveys/instances/{id}/generate-token` | Create public access link |
| GET | `/api/surveys/instances/{id}/responses` | Get responses |

### Frontend Page

**Surveys** (`/surveys`)
- Tabs: Survey Instances | Templates
- Instances: status badges, send button, create modal
- Templates: name, description, question count, create modal

---

## 7. Seed Data

### Core Governance Seed (`scripts/seed_relationship_governance.py`)

Creates the foundational governance data:

- **6 Organizations:**
  - Our Company (internal, enterprise, tech)
  - Acme Corporation (customer, enterprise, manufacturing)
  - TechStart Inc (customer, smb, tech)
  - GlobalSupply International (vendor, mid_market, logistics)
  - CloudServices Pro (vendor, smb, cloud)
  - Strategic Partners LLC (partner, smb, consulting)

- **5 Business Relationships** (all from "Our Company" to each external org):
  - Acme - Strategic Client (strategic tier, 30-day reviews, health: 80)
  - TechStart - Growth Client (operational tier, 90-day reviews, health: 82)
  - GlobalSupply - Key Vendor (strategic tier, 30-day reviews, health: 92)
  - CloudServices Pro - Vendor (operational tier, 90-day reviews, health: 79)
  - Strategic Partners - Implementation Partner (strategic tier, 30-day reviews, health: 90)

- **12 KPIs per relationship** across 9 categories:
  - Service Delivery: On-Time Delivery Rate (95%), Issue Resolution Time (24h)
  - Quality: Quality Score (4.5/10)
  - Communication: Response Time (4h), Communication Clarity (4/10)
  - Cost Efficiency: Budget Adherence (90%), Invoice Accuracy (98%)
  - Compliance: SLA Compliance (95%), Security Compliance (4.5/10)
  - Innovation: Innovation Score (3.5/10)
  - Satisfaction: Overall Satisfaction (4/10), Collaboration Effectiveness (4/10)

- **Perception Scores** with realistic gaps (internal typically higher than external)
- **Perception Gaps** auto-calculated with severity classification
- **3 Improvement Points** generated from significant/critical gaps
- **1 Survey Template** ("Quarterly Relationship Health Survey") with 7 questions

### Fit-Gap Seed (`scripts/seed_fitgap.py`)

Extends governance with additional data:

- **Organization Hierarchy:** Acme=holding, TechStart=subsidiary, CloudServices=division
- **17 Organization Officers:** Governance contacts with roles (account managers, executive sponsors, technical leads, etc.) across 6 organizations
- **12 Service Portfolio Entries:** IT Support, Cloud Infrastructure, Logistics, Consulting etc. across organizations, plus 5 relationship-service links
- **KPI Approval Workflow Data:** Updates 80 perception scores with approval statuses (Q1-Q2 approved, Q3 mostly approved + some rejected, Q4 pending)
- **20 Relationship Status History Entries:** Performance tracking across 5 relationships over 4 quarters (2025-Q1 through 2025-Q4)

---

## 8. Sidebar Navigation

The governance section appears as a labeled group in the sidebar:

| Menu Item | Route | Roles |
|-----------|-------|-------|
| Organizations | `/organizations` | admin, legal, procurement |
| Relationships | `/relationships` | admin, legal, procurement |
| Service Portfolio | `/service-portfolio` | admin, legal, procurement |
| KPI Scorecard | `/kpis` | admin, legal, procurement |
| KPI Approvals | `/kpi-approvals` | admin only |
| Improvements | `/improvements` | admin, legal, procurement |
| Surveys | `/surveys` | admin, legal |

---

## 9. Key Architectural Patterns

| Pattern | Implementation |
|---------|----------------|
| **Multi-Tenant Isolation** | Every query filtered by `tenant_id` via `CurrentTenantId` dependency |
| **Soft Deletes** | `is_active` flag or `status=cancelled/deprecated` - never hard delete |
| **Status Auto-Transitions** | `started_at` set when status → in_progress, `completed_at` when → completed |
| **Approval Workflow** | Perception scores require admin/legal approval before feeding gap calculations |
| **Lazy Relationships** | `lazy="dynamic"` for one-to-many to avoid N+1, queried separately |
| **Computed Properties** | `progress_percentage` on improvements, `response_rate` on surveys |
| **Hierarchical Data** | Organizations support self-referencing `parent_organization_id` |
| **Gap Auto-Calculation** | Gaps recalculated on every score submission/approval using only approved scores |
| **Auto-Generation** | Improvements auto-created from perception gaps above severity threshold |
| **Pagination** | Standard format: `{items: [...], total, page, page_size, pages}` |

---

## 10. Summary Statistics

| Metric | Count |
|--------|-------|
| Database tables | 16 |
| API endpoints | 70+ |
| Frontend pages | 9 |
| Enums | 25+ |
| SQLAlchemy models | 14 |
| Pydantic schemas | 40+ |
| API client methods | 50+ |
| Seed data records | 200+ |
