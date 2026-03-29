# Governance Section - Complete Implementation Guide

## Overview

The Governance section implements **Evaluetor's Relationship Governance Framework** - a structured approach to managing business relationships through perception-based KPI scoring, gap analysis, and continuous improvement tracking. It spans 20+ database tables (within a platform total of 55+), 6 governance routers with 80+ governance endpoints (within ~405 total endpoints across 44 routers), 10 governance models (within 53 total), and 9 frontend pages.

The core philosophy: relationships are measured not just by hard SLA metrics, but by **perception gaps** between how each party views performance. When internal teams rate themselves 4.5/5 on "Communication Clarity" but the external partner rates them 3.2/5, that 1.3-point gap surfaces a blind spot that traditional metrics miss.

The **Governance Bridge** service closes the loop between contract intelligence and relationship governance - automatically creating organizations, relationships, KPIs, and improvement points from AI-extracted contract data.

---

## Architecture

```
+------------------------------------------------------------------+
|                        FRONTEND (React)                          |
|  9 Governance Pages + API Client (src/lib/api.ts)                |
+------------------------------------------------------------------+
|                        BACKEND (FastAPI)                         |
|  6 Routers -> 10 Models -> PostgreSQL                            |
|  Organizations | Relationships | KPIs | Improvements | Surveys  |
|  Service Portfolio | Governance Bridge (service)                  |
+------------------------------------------------------------------+
|                      DATABASE (PostgreSQL)                        |
|  55+ Tables total, 20+ governance tables                         |
|  Multi-tenant isolation (tenant_id on every row)                 |
+------------------------------------------------------------------+
```

### Data Flow

```
                     AI Pipeline (Contract Upload)
                            |
                    Governance Bridge
                    (automated service)
                            |
        +-------------------+-------------------+
        |                   |                   |
Organizations          Business            Service
   |                  Relationships         Portfolio
   |                   |      |
   |          +--------+------+--------+
   |          |        |      |        |
   |        KPIs    Team   Status   Service
   |          |    Members History   Links
   |          |
   |    +-----+------+
   |    |            |
   |  Perception   Perception ---> Gap Analysis
   |  Scores       Gaps
   |                 |
   |           Improvement Points ---> Action Tracking
   |
   +-- Organization Officers
   +-- Survey Instances ---> Responses
```

---

## 1. Governance Bridge (Automated Contract-to-Governance Pipeline)

The **GovernanceBridgeService** (`backend/app/services/governance_bridge.py`, ~640 lines) is the central automation that bridges contract intelligence to relationship governance. It runs at the end of the `_run_deep_analysis` pipeline, after all AI agents have completed (metadata, risk, clauses, obligations, SLAs, renewals, schema extraction, auto-link detection). Each automation is independent and fault-tolerant: one failure does not block others.

### Trigger Point

```
Contract Upload -> Parse -> Chunk -> Embed -> Extract Metadata ->
Detect Risks -> Extract Clauses -> Extract Obligations -> Detect Renewals ->
Extract SLAs -> Auto-Link Detection -> ** Governance Bridge **
```

### 7 Automations

#### Automation 1: Counterparty -> Organization

Maps the AI-extracted counterparty name to an existing Organization or auto-creates one.

**Matching strategy (in order):**
1. **Exact match** - case-insensitive name comparison against existing organizations in the tenant
2. **Fuzzy match** - partial name containment (org name contains counterparty or first 10 chars match)
3. **Auto-create** - if no match found, creates a new Organization with:
   - `name` = counterparty as extracted
   - `code` = auto-generated from initials (e.g., "KR8 AI Inc." -> "KAI")
   - `org_type` = inferred from contract type (MSA/SOW -> customer, NDA -> partner, Vendor Agreement -> vendor)
   - `organization_level` = holding (default)
   - Code uniqueness enforced with retry (up to 5 attempts, appending digits)

#### Automation 2: Contract -> Business Relationship

Finds or creates a BusinessRelationship between the tenant's internal organization and the counterparty organization.

- Looks for the `internal` org type in the tenant (required - logs warning if missing)
- Searches for existing relationship in either direction (org_a/org_b)
- If no relationship exists, creates one with:
  - `name` = "{Counterparty Name} - {Relationship Type Title}" (e.g., "KR8 AI Inc. - Customer")
  - `relationship_type` = inferred from org type (customer -> customer, vendor -> supplier, partner -> partner)
  - `governance_tier` = operational (default)
  - `review_frequency_days` = 90
  - `status` = active
- Links the contract to the relationship via `contract.business_relationship_id`

#### Automation 3: SLA -> KPI

Maps extracted SLA metrics to KPI records on the relationship.

**Metric type to KPI mapping:**

| SLA Metric Type | KPI Category | Measurement Type |
|----------------|-------------|-----------------|
| uptime_percentage | service_delivery | percentage |
| availability | service_delivery | percentage |
| response_time | timeliness | time_hours |
| resolution_time | timeliness | time_hours |
| delivery_time | timeliness | time_days |
| success_rate | compliance | percentage |
| error_rate | quality | percentage |
| compliance_rate | compliance | percentage |
| utilization | service_delivery | percentage |
| throughput | service_delivery | number |
| recovery_time | service_delivery | time_hours |
| recovery_point | service_delivery | time_hours |
| quality_score | quality | rating |
| custom | other | number |

- Skips KPIs where a matching name already exists on the relationship (deduplication)
- Sets `target_value` from the SLA target and `threshold_amber` from the SLA warning threshold
- KPIs are created as metric-based (`is_perception_based=false`), not perception-based

#### Automation 4: Risk -> Improvement Points

Generates improvement action items from high-risk and critical-risk clauses.

**Clause types monitored:**
- indemnification -> "Broad Indemnification"
- limitation_of_liability -> "Weak Liability Protection"
- termination -> "Unfavorable Termination Terms"
- intellectual_property -> "IP Ownership Risk"
- confidentiality -> "Weak Confidentiality"
- auto_renewal -> "Auto-Renewal Trap"
- data_protection -> "Data Protection Gap"
- force_majeure -> "Missing Force Majeure Protection"

- Source set to `contract_risk` (distinct from `perception_gap`, `sla_breach`, etc.)
- Priority: `critical` for critical-risk clauses, `high` for high-risk
- Includes clause excerpt (first 300 chars) in the improvement description
- Deduplicates by checking existing improvement titles on the relationship

#### Automation 5: Health Score

Calculates a composite health score (0-100) for the relationship.

**Component weights and formulas:**

| Component | Weight | Formula |
|-----------|--------|---------|
| Risk Health | 30% | `(1 - high_risk_ratio) * 10` -- ratio of high/critical risk clauses to total |
| SLA Compliance | 40% | `compliance_percentage / 10` -- average compliance rate across active SLAs |
| Obligation Health | 30% | `(1 - overdue_ratio) * 10` -- ratio of overdue obligations to total |

- Each component produces a score on a 0-10 scale
- Weights are normalized if not all components have data
- Default score of 75 if no data is available
- Updates `relationship.health_score` and `relationship.last_health_calculation`

#### Automation 7: SOW Services -> Service Portfolio

Links SOW (Statement of Work) service descriptions to existing Service Portfolio entries.

- Only runs for contracts with `contract_type = SOW`
- Extracts service names from `schema_data.services.line_items` or from `service_description`/`scope` clauses
- Fuzzy-matches against existing ServicePortfolio entries (does not auto-create portfolios)
- Creates `RelationshipService` links with scope referencing the SOW filename
- Caps at 5 service links per SOW

### Auto-Link Detection (`backend/app/services/auto_link_detector.py`)

The auto-link detector uses 7-signal weighted scoring to identify related contracts (e.g., linking an addendum to its parent MSA).

**Signal Weights:**

| Signal | Weight | Description |
|--------|--------|-------------|
| `counterparty_match` | 0.30 | Exact counterparty name match |
| `counterparty_fuzzy` | 0.20 | Fuzzy counterparty name match |
| `type_hierarchy` | 0.25 | Contract type parent-child relationship (e.g., MSA -> SOW/Amendment) |
| `semantic_similarity` | 0.20 | Vector similarity of document content (scaled by actual similarity) |
| `filename_pattern` | 0.15 | Shared naming patterns in filenames |
| `same_batch` | 0.15 | Contracts uploaded in the same batch |
| `date_proximity` | 0.10 | Temporal proximity of contract dates |

- Minimum confidence threshold: **0.30** (candidates below this are excluded)
- Total confidence capped at 1.0
- Type hierarchies defined: MSA -> [SOW, Amendment], NDA -> [Amendment], SOW -> [Amendment], Vendor Agreement -> [SOW, Amendment], Employment Contract -> [Amendment]

### Verified Test Results (FOXO/KR8 AI Pipeline)

The full governance bridge pipeline has been verified end-to-end with real contract uploads on AWS:

**Step 1: MSA Upload (FOXO_KR8AI_MSA.pdf)**
- AI extracted counterparty: "KR8 AI Inc."
- Automation 1: No existing org match -> auto-created "KR8 AI Inc." (code: `kr8-ai`, type: `customer`)
- Automation 2: Found internal org within Acme Corp tenant (auto-detected "Our Company")
- Automation 2: No existing relationship -> auto-created "KR8 AI Inc. - Customer" business relationship (Acme Corp <-> KR8 AI)
- Contract linked to new relationship via `business_relationship_id`

**Step 2: Addendum Upload (FOXO_KR8AI_Addendum.docx)**
- AI extracted counterparty: "KR8 AI Inc."
- Automation 1: **Matched existing org** (exact match) - no duplicate created
- Automation 2: **Matched existing relationship** - no duplicate created
- Automation 3: 6 SLAs extracted -> 6 KPIs auto-created:

| KPI Name | Target | Metric Type |
|----------|--------|-------------|
| Platform Availability | 99.9% | uptime_percentage |
| Response Time - Standard Queries | 200ms | response_time |
| Incident Response - Critical | 15 min | response_time |
| Incident Resolution - Critical | 4 hrs | resolution_time |
| Data Processing Accuracy - Structured Data | 97% | success_rate |
| Data Processing Accuracy - Unstructured Data | 95% | success_rate |

- Auto-link detection: addendum linked to MSA as amendment (confidence: **0.50**)

---

## 2. Organization Management

### Database Model

**Table: `organizations`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `tenant_id` | UUID (FK -> tenants) | Multi-tenant isolation |
| `name` | VARCHAR(255) | Organization name |
| `code` | VARCHAR(50) | Short code, unique per tenant |
| `org_type` | ENUM | `customer`, `vendor`, `partner`, `internal` |
| `parent_organization_id` | UUID (FK -> self) | Hierarchy - parent org |
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
| `relationship_owner_id` | UUID (FK -> users) | Owner |
| `is_active` | BOOLEAN | Soft delete flag (default: true) |
| `notes` | TEXT | |
| `created_at`, `updated_at` | TIMESTAMP | |

**Table: `organization_officers`** - Key contacts/governance personnel

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `tenant_id` | UUID (FK) | |
| `organization_id` | UUID (FK -> organizations) | |
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

## 3. Business Relationships

### Database Models

**Table: `business_relationships`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `tenant_id` | UUID (FK) | |
| `org_a_id` | UUID (FK -> organizations) | Party A (typically internal) |
| `org_b_id` | UUID (FK -> organizations) | Party B (external partner) |
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
| `user_id` | UUID (FK -> users) | Platform user |
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
| `recorded_by` | UUID (FK -> users) | |
| `notes` | TEXT | Context for the assessment |
| `trigger` | VARCHAR(100) | `manual`, `kpi_evaluation_cycle`, `health_score_recalc`, `quarterly_review`, `sla_breach` |

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

**Relationship Detail** (`/relationships/:id`) - the richest governance page
- **5 tabs:**
  1. **KPIs** - Perception scorecard with internal (blue bars) and external (purple bars) comparison, gap visualization
  2. **Team** - Team members with roles, add/remove
  3. **Improvements** - Gap-linked improvements with progress bars, source tags, priority/status badges
  4. **History** - Performance trend bar chart + status history table (period, status, score, notes, trigger)
  5. **Overview** - Status, parties, health score, governance tier, review frequency

---

## 4. KPI & Perception Scoring (Core Innovation)

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
| `scorer_org_id` | UUID (FK -> organizations) | Who scored |
| `scored_by_user_id` | UUID (FK -> users) | Individual scorer |
| `score` | NUMERIC(5,2) | Rating (typically 1-10) |
| `period` | VARCHAR(20) | "2025-Q1" |
| `comments` | TEXT | |
| `is_internal` | BOOLEAN | Internal vs. external perspective |
| `approval_status` | ENUM | `draft`, `pending_approval`, `approved`, `rejected` |
| `approved_by` | UUID (FK -> users) | |
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
| >= 2.5 | `critical` |
| >= 1.5 | `significant` |
| >= 0.8 | `moderate` |
| >= 0.3 | `minor` |
| < 0.3 | `minor` (aligned) |

**Gap Summary API:**

`GET /api/kpis/relationship/{id}/gaps` returns all perception gaps for a relationship, filterable by severity and period. The summary endpoint (`/api/kpis/relationship/{id}/summary`) provides aggregate statistics: counts by severity, average gap, and worst-performing KPI.

### Perception Scoring Framework

**Internal Perception Scores:**
- Submitted by team members within the tenant organization
- Represent how the internal team perceives their own performance on each KPI
- Typically submitted during Quarterly Business Reviews (QBRs)
- Require approval workflow before feeding into gap calculations

**External Perception Scores:**
- Submitted by the counterparty organization (customer, vendor, partner)
- Represent how the external party perceives performance
- Can be collected via the survey system or external portal
- Also require approval before gap calculation

**Gap Analysis:**
- Auto-computed when scores are submitted or approved
- `gap = internal_score - external_score`
- Positive gap = overconfidence (internal rates higher than external perceives)
- Negative gap = underconfidence (rare, but indicates external rates higher)
- Severity thresholds drive automatic improvement generation

**"Generate Improvements from Gaps" Workflow:**

```
POST /api/improvements/generate-from-gaps?relationship_id=...&period=2025-Q1&min_severity=significant
```

Creates improvement points for all perception gaps meeting the severity threshold. Links each improvement back to its source KPI and gap record. Deduplicates by checking existing gap linkages.

### Approval Workflow

```
Score Submitted --> pending_approval --+--> approved (by admin/legal) --> Gap Recalculated
                                       +--> rejected (with comments)
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

## 5. Improvement Tracking

Improvements are action items born from perception gaps, SLA breaches, contract risks, review meetings, customer feedback, or internal audits. Each improvement links back to the KPI and gap that triggered it.

### Database Models

**Table: `improvement_points`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `relationship_id` | UUID (FK) | |
| `kpi_id` | UUID (FK, nullable) | Linked KPI |
| `gap_id` | UUID (FK -> perception_gaps, nullable) | Linked gap |
| `title` | VARCHAR(255) | |
| `description` | TEXT | |
| `source` | ENUM | `perception_gap`, `sla_breach`, `review_meeting`, `customer_feedback`, `internal_audit`, `contract_risk`, `manual` |
| `priority` | ENUM | `low`, `medium`, `high`, `critical` |
| `status` | ENUM | `open`, `in_progress`, `blocked`, `completed`, `cancelled` |
| `owner_id` | UUID (FK -> users) | Responsible person |
| `assigned_org_id` | UUID (FK -> organizations) | Responsible org |
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
| `owner_id` | UUID (FK -> users) | |
| `due_date` | DATE | |
| `notes` | TEXT | |
| `blocker_reason` | TEXT | Why blocked |

**Computed:** `progress_percentage` = (completed_actions / total_actions) * 100

### Improvement Sources

Improvements can originate from multiple channels:

| Source | How Created | Description |
|--------|------------|-------------|
| `perception_gap` | Auto (from gap API) | Generated when perception gap exceeds severity threshold |
| `contract_risk` | Auto (Governance Bridge) | High/critical risk clauses create improvement items during contract processing |
| `sla_breach` | Manual or scheduled | Created when SLA compliance drops below threshold |
| `review_meeting` | Manual | Action items from QBRs and governance reviews |
| `customer_feedback` | Manual | Direct customer feedback requiring follow-up |
| `internal_audit` | Manual | Findings from compliance or security audits |
| `manual` | Manual | Ad-hoc improvements |

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

## 6. Service Portfolio

Tracks what services organizations provide and links them to business relationships.

### Database Models

**Table: `service_portfolios`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `tenant_id` | UUID (FK) | |
| `organization_id` | UUID (FK -> organizations) | Service provider |
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

## 7. Surveys

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
| POST | `/api/surveys/instances/{id}/send` | Send survey (draft -> in_progress) |
| POST | `/api/surveys/instances/{id}/generate-token` | Create public access link |
| GET | `/api/surveys/instances/{id}/responses` | Get responses |

### Frontend Page

**Surveys** (`/surveys`)
- Tabs: Survey Instances | Templates
- Instances: status badges, send button, create modal
- Templates: name, description, question count, create modal

---

## 8. Enterprise Data Sources

In a production enterprise deployment, governance data flows in from multiple systems. This section documents where each data element originates and how it enters the platform, along with the current implementation state.

### Data Origin Map

| Data Element | Automated Source | Manual Source | Frequency |
|-------------|-----------------|--------------|-----------|
| **KPIs** | SLA extraction via Governance Bridge | Admin UI, seed scripts | On contract upload + manual |
| **Internal perception scores** | - | Team members submit via UI during QBRs | Quarterly |
| **External perception scores** | - | Counterparty submits via survey system / external portal | Quarterly |
| **Perception gaps** | Auto-computed on score submission/approval | - | On every score event |
| **Team members** | - | Assigned at relationship creation + admin UI | On relationship changes |
| **Improvement points** | Auto from gaps (generate-from-gaps API) + auto from contract risks (Governance Bridge) | Manual from QBRs, audit findings, customer feedback | Continuous |
| **Performance history** | Event-triggered (SLA breaches, health score recalc) | Manual quarterly snapshots from governance reviews | Quarterly + event-driven |
| **Health score** | Governance Bridge (on contract upload), scheduled recalculation | Manual override possible | Weekly (scheduled) + on upload |
| **Survey templates** | - | Admin creates via UI | As needed |
| **Survey responses** | Respondents complete via public links | - | Per survey campaign |

### Enterprise Data Source Mapping

The table below maps enterprise data sources to their ideal integration points, with the current implementation state:

| Data Category | Enterprise Source | Current State |
|--------------|------------------|---------------|
| **ServiceNow** | SLA actuals, incidents | Stub integration (`snow_integration` router + `snow_sync_service`) |
| **Salesforce** | Accounts, contacts, renewal pipeline | Planned connector |
| **SAP / Oracle ERP** | Financial actuals, PO matching | Planned connector |
| **Workday** | Team members, reporting lines | Planned connector |
| **Qualtrics / SurveyMonkey** | External perception surveys | Survey module exists (`survey.py` model + `surveys.py` router) |
| **Datadog / PagerDuty** | Availability monitoring, incident response | Planned connector |

### Enterprise Integration Map

The platform is designed to integrate with enterprise systems for each governance data category:

| External System | Data Provided | Integration Point |
|----------------|--------------|------------------|
| **ServiceNow** | SLA measurements, incident data, CMDB relationships | KPIs (metric values), improvement points (SLA breaches) |
| **Salesforce** | Account teams, customer health scores, pipeline data | Team members, organizations, relationship metadata |
| **SAP / Oracle ERP** | Financial KPIs, payment compliance, spend tracking | KPIs (cost_efficiency category), obligation compliance |
| **Workday** | Workforce/team data for staffing contracts | Team members, organization officers |
| **Qualtrics / Survey tools** | External perception scores at scale | Perception scores (external), survey responses |
| **Datadog / New Relic** | API response times, uptime percentages, error rates | KPIs (service_delivery, quality categories) |
| **Jira / Azure DevOps** | Issue resolution metrics, delivery timelines | KPIs (timeliness category), improvement action tracking |

### KPI Data Flow (Enterprise)

```
ServiceNow SLA Module ----+
                          |
Datadog/New Relic --------+--> KPI actual values
                          |
SAP Financial Reports ----+
                          |
Survey Templates ---------+--> Perception scores (automated collection)
                          |
Qualtrics -----------------+
                          |
                          v
              Gap Calculation Engine
                          |
                          v
              Improvement Generation
                          |
                          v
              Quarterly Business Review
```

---

## 9. Seed Scripts

Three seed scripts populate governance data for development and demo environments.

### Core Governance Seed

**Script:** `backend/scripts/seed_relationship_governance.py`
**Command:** `cd backend && uv run python -m scripts.seed_relationship_governance`

Creates the foundational governance data:

- **6 Organizations:**
  - Our Company (internal, enterprise, tech)
  - Acme Corporation (customer, enterprise, manufacturing)
  - TechStart Inc (customer, smb, tech)
  - GlobalSupply International (vendor, mid_market, logistics)
  - CloudServices Pro (vendor, smb, cloud)
  - Strategic Partners LLC (partner, smb, consulting)

- **5 Business Relationships** (all from "Our Company" to each external org):
  - Acme - Strategic Client (strategic tier, 30-day reviews, health: ~80)
  - TechStart - Growth Client (operational tier, 90-day reviews, health: ~82)
  - GlobalSupply - Key Vendor (strategic tier, 30-day reviews, health: ~92)
  - CloudServices Pro - Vendor (operational tier, 90-day reviews, health: ~79)
  - Strategic Partners - Implementation Partner (strategic tier, 30-day reviews, health: ~90)

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
- **3 Improvement Points** generated from significant/critical gaps, with 4 action steps
- **1 Survey Template** ("Quarterly Relationship Health Survey") with 7 questions
- **1 Survey Instance** (in_progress for current quarter)

### KR8 AI Relationship Seed (Rich Demo Data)

**Script:** `backend/scripts/seed_kr8_relationship.py`
**Command:** `cd backend && uv run python -m scripts.seed_kr8_relationship`

Populates rich demo data for the KR8 AI Inc. relationship (created by Governance Bridge from contract upload). Requires the FOXO/KR8 AI contracts to have been uploaded first.

- **72 Perception Scores** (6 KPIs x 6 quarters x 2 perspectives):
  - Covers 2024-Q1 through 2025-Q2
  - Realistic patterns: internal scores consistently 0.5-2.0 points higher than external
  - Includes event spikes (e.g., Q2 2024 incident resolution gap of 2.0 from missed SLA)
  - All scores set to `approved` status

- **36 Perception Gaps** (6 KPIs x 6 quarters):
  - Computed from scores with severity classification
  - Notable gaps: Incident Response Q2 2024 (significant), Unstructured Data Q1 2025 (moderate)

- **2 Team Members:**
  - Relationship Manager (primary) - "Alex Morgan"
  - Operations Lead - "Jordan Chen"

- **6 Improvement Points** from multiple sources:
  - 3 from perception gaps (incident resolution, unstructured data, response time)
  - 1 from customer feedback (proactive communication)
  - 1 from internal audit (security review)
  - 1 from contract risk (IP ownership)
  - Mix of statuses: in_progress, open, completed

- **6 Status History Entries** (2024-Q1 through 2025-Q2):
  - Shows realistic trajectory: good -> concerning (SLA breach) -> acceptable -> good -> acceptable -> good
  - Scores ranging from 65 to 82

- **Relationship metadata update:** governance tier upgraded to `strategic`, description enriched

### Business Unit Hierarchy Seed

**Script:** `backend/scripts/seed_business_units.py`
**Command:** `cd backend && uv run python -m scripts.seed_business_units`

Creates business unit hierarchy for all active tenants:

- **5 Top-level Business Units:** Legal (LEGAL), Procurement (PROC), Sales (SALES), Operations (OPS), Finance (FIN)
- **2 Sub-units under Sales:** Enterprise Sales (SALES-ENT), SMB Sales (SALES-SMB)
- Idempotent: checks for existing BUs by code before creating
- Runs for every active tenant in the database

---

## 10. Sidebar Navigation

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

## 11. Key Architectural Patterns

| Pattern | Implementation |
|---------|----------------|
| **Multi-Tenant Isolation** | Every query filtered by `tenant_id` via `CurrentTenantId` dependency |
| **Soft Deletes** | `is_active` flag or `status=cancelled/deprecated` - never hard delete |
| **Status Auto-Transitions** | `started_at` set when status -> in_progress, `completed_at` when -> completed |
| **Approval Workflow** | Perception scores require admin/legal approval before feeding gap calculations |
| **Lazy Relationships** | `lazy="dynamic"` for one-to-many to avoid N+1, queried separately |
| **Computed Properties** | `progress_percentage` on improvements, `response_rate` on surveys |
| **Hierarchical Data** | Organizations support self-referencing `parent_organization_id` |
| **Gap Auto-Calculation** | Gaps recalculated on every score submission/approval using only approved scores |
| **Auto-Generation** | Improvements auto-created from perception gaps above severity threshold |
| **Contract-to-Governance Bridge** | GovernanceBridgeService auto-populates orgs, relationships, KPIs, improvements from AI pipeline |
| **Fault-Tolerant Automations** | Each bridge automation is independent; one failure does not block others |
| **Deduplication** | Bridge checks existing records by name/title before creating (orgs, KPIs, improvements) |
| **Pagination** | Standard format: `{items: [...], total, page, page_size, pages}` |

---

## 12. Governance File Reference

### Backend Routers (6)

| Router File | Purpose |
|-------------|---------|
| `organizations.py` | Organization CRUD, hierarchy, officers |
| `relationships.py` | Business relationships, team, health, history |
| `kpis.py` | KPIs, perception scores, gaps, approvals |
| `improvements.py` | Improvement points, actions, generation from gaps |
| `surveys.py` | Survey templates, instances, responses |
| `service_portfolio.py` | Service portfolio, relationship links |

### Backend Models (10)

| Model File | Purpose |
|------------|---------|
| `organization.py` | Organization entity |
| `organization_officer.py` | Key contacts/governance personnel |
| `relationship.py` | Business relationships, teams |
| `relationship_history.py` | Status history entries |
| `kpi.py` | KPIs, perception scores, perception gaps |
| `improvement.py` | Improvement points and actions |
| `survey.py` | Templates, questions, instances, responses |
| `service_portfolio.py` | Service portfolios and relationship-service links |
| `external_user.py` | External user access |
| `external_access.py` | External access/sharing configuration |

### Backend Services (key governance)

| Service File | Purpose |
|-------------|---------|
| `governance_bridge.py` (~640 lines) | 7 automations linking contract intelligence to governance |
| `auto_link_detector.py` (~591 lines) | 7-signal weighted scoring for contract relationship detection |

### Frontend Pages (9)

| Page | Route |
|------|-------|
| OrganizationsPage | `/organizations` |
| OrganizationDetailPage | `/organizations/:id` |
| RelationshipsPage | `/relationships` |
| RelationshipDetailPage | `/relationships/:id` |
| KPIScorecardPage | `/kpis` |
| KPIApprovalsPage | `/kpi-approvals` |
| ImprovementsPage | `/improvements` |
| SurveysPage | `/surveys` |
| ServicePortfolioPage | `/service-portfolio` |

---

## 13. Summary Statistics

| Metric | Count |
|--------|-------|
| Platform database tables (total) | 55+ |
| Platform API endpoints (total) | ~405 |
| Platform routers (total) | 44 |
| Platform models (total) | 53 |
| Platform services (total) | 38 |
| Platform AI agent files (total) | 11 (9 agents + base + init) |
| Governance routers | 6 |
| Governance models | 10 |
| Governance database tables | 20+ |
| Governance API endpoints | 80+ |
| Governance frontend pages | 9 |
| Governance enums | 25+ |
| Governance Pydantic schemas | 40+ |
| API client methods | 50+ |
| Seed data records | 200+ (core) + 120+ (KR8 demo) |
| Governance Bridge automations | 7 (numbered 1-5, 7, plus auto-link re-run) |
| Auto-link detection signals | 7 (weighted scoring) |
| AI agents feeding governance | 9 (metadata, risk, clauses, obligations, SLAs, renewals, schema, Q&A, intent) |
