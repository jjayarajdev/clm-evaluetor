# Evaluetor — Calculations & Validations Reference

> Auto-generated from codebase analysis and live API validation (Acme Corp tenant).
> Last validated: 2026-04-17

---

## Page 1: Dashboard

The main dashboard (`/dashboard`) is served by `ModernDashboardPage.tsx` and pulls data from multiple backend endpoints. The backend computation lives primarily in `backend/app/services/postsigning_service.py` and `backend/app/services/dashboard_service.py`.

### 1.1 Top Stat Cards

#### Total Contracts
| Field | Detail |
|-------|--------|
| **Displayed** | Count of all contracts for the tenant |
| **Source** | `GET /api/dashboard/contracts-summary` |
| **Formula** | `COUNT(DISTINCT contracts.id) WHERE tenant_id = ?` |
| **Filters** | `tenant_id` (from JWT), `business_unit_id` (if assigned) |
| **Live Value** | **22** |
| **Trend** | `((last_period_count - first_period_count) / max(first_period_count, 1)) * 100` |

#### Contracts At Risk
| Field | Detail |
|-------|--------|
| **Displayed** | Contracts with significant overdue obligations |
| **Source** | `GET /api/dashboard/postsigning` → `compliance.contracts_at_risk` |
| **Formula** | Contract is "at risk" if: `overdue_obligations >= 2` **OR** `(total_obligations > 0 AND overdue/total > 0.30)` |
| **Code** | `postsigning_service.py:397-401` |
| **Live Value** | **3** |

#### Overall Compliance Rate
| Field | Detail |
|-------|--------|
| **Displayed** | Weighted blend of obligation and SLA compliance |
| **Source** | `GET /api/dashboard/postsigning` → `compliance.overall_compliance_rate` |
| **Formula** | **`obligation_compliance × 0.6 + sla_compliance × 0.4`** |
| **Code** | `postsigning_service.py:395` |
| **Live Value** | **39.13%** |
| **Validation** | `18.23 × 0.6 + 70.48 × 0.4 = 39.13%` ✓ |

#### Total Contract Value
| Field | Detail |
|-------|--------|
| **Displayed** | Sum of all contract values |
| **Source** | `GET /api/dashboard/postsigning` → `total_value` |
| **Formula** | `SUM(contracts.contract_value) WHERE contract_value IS NOT NULL` |
| **Live Value** | **$9,280,650.00** |

### 1.2 Obligation Compliance Rate

| Field | Detail |
|-------|--------|
| **Displayed** | Percentage of obligations being addressed |
| **Source** | `GET /api/dashboard/postsigning` → `obligations.compliance_rate` |
| **Formula** | **`(completed + in_progress) / assessable × 100`** |
| **Where** | `assessable = total - waived - pending_future` |
| **Where** | `pending_future = obligations WHERE status=PENDING AND deadline > today` |
| **Code** | `postsigning_service.py:97-104` |
| **Live Value** | **18.23%** |
| **Validation** | `(51 + 13) / 351 × 100 = 18.23%` ✓ |

**Obligation breakdown (live):**
| Metric | Value |
|--------|-------|
| Total | 351 |
| Completed | 51 |
| In Progress | 13 |
| Overdue | 8 |
| Pending | 279 |
| RAG Green | 63 |
| RAG Amber | 9 |
| RAG Red | 8 |
| Not Assessed | 271 |

### 1.3 SLA Compliance Rate

| Field | Detail |
|-------|--------|
| **Displayed** | Average compliance rate across all SLAs |
| **Source** | `GET /api/dashboard/postsigning` → `slas.compliance_rate` |
| **Formula** | **`AVG(contract_sla.current_compliance_rate) WHERE current_compliance_rate IS NOT NULL`** |
| **Note** | This is NOT a count of compliant SLAs. It averages each SLA's individual compliance percentage. |
| **Code** | `postsigning_service.py:175-176` |
| **Live Value** | **70.48%** |

**SLA breakdown (live):**
| Metric | Value |
|--------|-------|
| Total SLAs | 102 |
| Active | 102 |
| Compliant (count) | 85 |
| Breached (count) | 17 |
| Critical Breaches | 5 |
| Penalties MTD | $0.00 |

> **Important distinction:** `compliant=85` is a count of SLAs currently meeting targets. `compliance_rate=70.48%` is the average of each SLA's `current_compliance_rate` column — a different metric.

### 1.4 Vendor Performance

| Field | Detail |
|-------|--------|
| **Source** | `GET /api/dashboard/postsigning` → `vendors` |
| **Avg Performance Score** | `AVG(vendor_score)` across all vendors |
| **Vendor Score Formula** | Per vendor: weighted combination of obligation compliance, SLA compliance, and overdue penalties |
| **Code** | `postsigning_service.py:_build_vendor_widget()` |
| **Live Value** | **54.73** (average across 19 vendors) |

**Top/Bottom Performers (live):**
| Rank | Vendor | Score |
|------|--------|-------|
| #1 | UptimeRobot | 90.23 |
| #2 | TechVendor Solutions | 76.65 |
| #3 | CareerSource | 76.20 |
| ... | ... | ... |
| #17 | CloudSoft Technologies | 43.61 |
| #18 | Northwestern IT | 41.23 |
| #19 | KR8 AI Inc. | 31.48 |

### 1.5 Milestone Completion

| Field | Detail |
|-------|--------|
| **Source** | `GET /api/dashboard/postsigning` → `milestones` |
| **Completion Rate** | `completed / total × 100` |
| **Live Value** | **64.91%** (`37 / 57`) |

### 1.6 Renewal Alerts

| Field | Detail |
|-------|--------|
| **Source** | `GET /api/dashboard/postsigning` → `renewals` |
| **Expiring 30d** | `COUNT(contracts) WHERE 0 <= (expiration_date - today).days <= 30` |
| **Expiring 90d** | Same with `<= 90` |
| **Past Notice Deadline** | `COUNT(contracts) WHERE auto_renewal=TRUE AND (expiration_date - notice_period_days) < today` |
| **Total Value at Risk** | `SUM(contract_value)` of expiring contracts |

### 1.7 Quick Action Badges

| Badge | Source | Formula |
|-------|--------|---------|
| High Risk | `contracts-summary.by_risk.high` | `COUNT(contracts) WHERE risk_level IN ('high','critical')` |
| Pending | `contracts-summary.by_status.pending` | `COUNT(contracts) WHERE status = 'pending'` |
| Expiring 30d | `postsigning.renewals.expiring_30_days` | See §1.6 |
| SLA Critical | `postsigning.slas.critical_breaches` | `COUNT(slas) WHERE consecutive_breaches > 0 AND severity = 'critical'` |
| Overdue | `postsigning.obligations.overdue` | `COUNT(obligations) WHERE status = 'overdue'` |

---

### 1.8 Obligations Compliance Dashboard (`/api/dashboard/obligations-compliance`)

This endpoint powers the detailed obligations view with RAG analysis.

#### RAG Status Summary

| Field | Detail |
|-------|--------|
| **Formula** | Count obligations by `rag_status` column |
| **Compliance Rate** | **`green / total × 100`** (different from §1.2!) |
| **Code** | `dashboard_service.py:get_obligations_compliance()` |
| **Live Values** | Green=63, Amber=9, Red=8, Not Assessed=271, Total=351 |
| **Compliance Rate** | `63/351 = 17.9%` |

> **Two different obligation compliance rates exist:**
> - **Postsigning** (§1.2): `(completed + in_progress) / assessable` = 18.23% — task-progress based
> - **Obligations dashboard** (§1.8): `green / total` = 17.9% — RAG-status based

#### Contracts at Risk (RAG-based)
| Metric | Formula |
|--------|---------|
| Contracts with Red | `COUNT(DISTINCT contract_id) WHERE any obligation has rag_status = RED` |
| Contracts with Amber | `COUNT(DISTINCT contract_id) WHERE any obligation has rag_status = AMBER AND no RED` |
| Top Risk Contracts | Sorted by `(red_count DESC, amber_count DESC, overdue_count DESC)` |

---

### 1.9 Portfolio Dashboard (`/api/dashboard/portfolio`)

#### Value Metrics
| Metric | Formula | Live Value |
|--------|---------|------------|
| Total Value | `SUM(contract_value)` | $9,280,650 |
| Average Value | `SUM(value) / COUNT(contracts_with_value)` | — |
| Contracts with Value | `COUNT(*) WHERE contract_value IS NOT NULL` | 12 |

#### Risk Metrics
| Metric | Formula | Live Value |
|--------|---------|------------|
| By Risk Level | `GROUP BY risk_level` | low=22 |
| High Risk Count | `COUNT(*) WHERE risk_level IN ('high','critical')` | 0 |
| Expiring 30d | `WHERE 0 <= days_to_expiry <= 30` | — |
| Auto-Renewal Count | `WHERE auto_renewal = TRUE` | — |

#### Obligation Metrics (Portfolio)
| Metric | Formula | Live Value |
|--------|---------|------------|
| Compliance Rate | `green / total × 100` | 17.9% |
| Overdue | `COUNT(*) WHERE status = 'overdue'` | 8 |
| By RAG | See table | green=63, amber=9, red=8, not_assessed=271 |

#### Clause Coverage
| Metric | Formula |
|--------|---------|
| Average Coverage | `AVG(coverage_percentage)` from `ContractClauseIndicator` |
| Missing Critical | Count contracts missing each of 6 critical clause types: `limitation_of_liability`, `indemnification`, `confidentiality`, `termination_for_cause`, `governing_law`, `force_majeure` |

#### Counterparty Exposure (Top 10)
Per counterparty:
- Contract Count: `COUNT(contracts)`
- Total Value: `SUM(contract_value)`
- Avg Risk Score: `AVG(risk_score)`
- Expiring Soon: `COUNT WHERE days_to_expiry <= 30`
- Red Obligations: `COUNT WHERE rag_status = RED`

---

### 1.10 Admin Dashboard (`/api/dashboard/admin`)

| Metric | Formula |
|--------|---------|
| Contracts by Type | `GROUP BY contract_type, COUNT(*)` |
| Contracts by Status | `GROUP BY status, COUNT(*)` |
| Users by Role | `GROUP BY role, COUNT(*)` (active/inactive) |
| Queries 7d | `COUNT(audit_log) WHERE action = QUERY_EXECUTE AND date >= today-7d` |
| Queries 30d | Same with 30-day window |
| Uploads 7d | `COUNT(audit_log) WHERE action = CONTRACT_UPLOAD AND date >= today-7d` |
| Uploads 30d | Same with 30-day window |
| Ingestion Status | `GROUP BY status` for pending/processing/completed/failed |

### 1.11 Legal Dashboard (`/api/dashboard/legal`)

| Metric | Formula |
|--------|---------|
| High Risk Contracts | `WHERE risk_level IN ('high','critical') OR has_clauses(risk_level='high')` — top 10 by risk_score |
| Expiration Timeline | Buckets: 0-30d, 31-60d, 61-90d |
| High Risk Clauses | `WHERE risk_level = 'high'` — last 20 |

### 1.12 Procurement Dashboard (`/api/dashboard/procurement`)

| Metric | Formula |
|--------|---------|
| Spend by Vendor | `GROUP BY counterparty, SUM(contract_value)` — top 20 |
| Upcoming Obligations | `WHERE status = PENDING AND deadline BETWEEN today AND today+30d` |
| Auto-Renewal Urgency | `notice_deadline = expiration_date - notice_period_days`; levels: IMMEDIATE (<7d), SOON (<30d), UPCOMING (<90d), FUTURE |

### 1.13 Insights (`/api/dashboard/insights`)

Dynamic alerts generated from live data:

| Insight | Trigger Condition |
|---------|-------------------|
| Renewal Opportunity | `COUNT(contracts expiring in 30d) > 0` |
| Compliance Alert | `COUNT(SLAs with consecutive_breaches > 0) > 0` |
| Overdue Obligations | `COUNT(obligations WHERE deadline < today AND status NOT IN completed/waived) > 0` |
| High Risk Contracts | `COUNT(contracts WHERE risk_level IN high/critical) > 0` |

---

### Data Flow Diagram

```
contracts table ──┬── COUNT/GROUP BY ──→ Contract Stats (total, by_status, by_risk, by_type)
                  ├── SUM(contract_value) ──→ Total Value, Avg Value, Value by Vendor
                  ├── expiration_date math ──→ Renewal Alerts, Expiry Buckets
                  └── JOIN obligations ─┬── (completed+in_progress)/assessable ──→ Obligation Compliance (18.23%)
                                        └── GROUP BY rag_status ──→ RAG Summary (green/total = 17.9%)

contract_sla table ── AVG(current_compliance_rate) ──→ SLA Compliance (70.48%)

Obligation Compliance × 0.6 + SLA Compliance × 0.4 ──→ Overall Compliance (39.13%)
```

### Multi-Tenant Isolation

Every query applies:
1. `tenant_id` filter from JWT token (`CurrentTenantId` dependency)
2. `business_unit_id` filter via `apply_bu_filter()` if user has BU assignment
3. Super admin (`tenant_id = NULL`) sees cross-tenant data

---

---

## Page 2: Contracts List & Detail

The contracts list (`/contracts`) is served by `ContractsPage.tsx` and the detail view by `ContractViewPage.tsx`. Backend logic lives in `backend/app/routers/contracts.py`, with AI agents in `backend/app/agents/`.

### 2.1 Contracts List — Stat Cards

| Card | Formula | Source | Live Value |
|------|---------|--------|------------|
| Total Contracts | `response.total` (server-side COUNT) | `GET /api/contracts` | **22** |
| High Risk | Client-side: `items.filter(c => risk_level IN ('high','critical')).length` | Contract list | **0** |
| Processing | Client-side: `items.filter(c => status === 'processing').length` | Contract list | **0** |
| Completed | Client-side: `items.filter(c => status === 'completed').length` | Contract list | **22** |

### 2.2 Contract List — Pagination

| Field | Detail |
|-------|--------|
| **Formula** | `pages = CEIL(total / page_size)` |
| **Code** | `contracts.py:1375` — `(total + page_size - 1) // page_size` |
| **Defaults** | `page=1`, `page_size=20`, max `page_size=100` |
| **Example** | 22 contracts / 20 per page = 2 pages |

### 2.3 Filter Options

| Filter | Backend Query | Details |
|--------|--------------|---------|
| Counterparty | `GROUP BY counterparty, COUNT(id)` | Shows count next to each name |
| Client | `LEFT JOIN clients, COUNT(contracts)` per client | Shows contract count |
| Status | `GROUP BY status` | Enum: pending, processing, completed, failed |
| Contract Type | `GROUP BY contract_type` | Enum: nda, msa, sow, amendment, vendor_agreement, employment_contract |
| Risk Level | `GROUP BY risk_level` | Enum: low, medium, high, critical |

### 2.4 Contract Detail — Key Metrics

**Sample contract: FOXO_KR8AI_Master_Software_Services_Agreement_2024.pdf**

| Field | Value | Source |
|-------|-------|--------|
| Contract Type | MSA | AI metadata extraction |
| Counterparty | KR8 AI Inc. | AI metadata extraction |
| Contract Value | $2,500,000.00 | AI metadata extraction |
| Currency | USD | AI metadata extraction (ISO code) |
| Effective Date | 2024-01-12 | AI metadata extraction |
| Risk Score | 0 | AI risk detection agent |
| Risk Level | low | Derived from risk_score thresholds |
| File Size | 10,700 bytes | File system |

### 2.5 Contract Intelligence (`/api/dashboard/intelligence/{id}`)

**Clause Breakdown (live for KR8 MSA):**

| Clause Type | Count | High Risk |
|-------------|-------|-----------|
| intellectual_property | 2 | 0 |
| warranty | 2 | 0 |
| service_level | 2 | 0 |
| confidentiality | 1 | 0 |
| payment_terms | 1 | 0 |

**Obligations Matrix:**
| Metric | Formula |
|--------|---------|
| Provider Obligations | `COUNT WHERE obligated_party LIKE '%provider%' OR '%vendor%'` |
| Client Obligations | `COUNT WHERE obligated_party NOT LIKE provider pattern` |
| Total | Sum of both |

**Extraction Status:**
| Metric | Formula |
|--------|---------|
| Total Clauses | `COUNT(clauses) WHERE contract_id = ?` |
| Classified | `COUNT(clauses) WHERE clause_type != 'other'` |
| Total Obligations | `COUNT(obligations) WHERE contract_id = ?` |

---

### 2.6 AI Processing Pipeline

The upload pipeline runs sequentially through these stages:

```
Upload → Parse (PDF/DOCX) → Chunk → Embed (ChromaDB) → Metadata Extraction
                                                          ↓
                                    ┌─────────────────────┘
                                    ↓
                              Risk Detection → Clause Extraction → Obligation Extraction
                                                                        ↓
                                                              SLA Extraction → Renewal Detection
                                                                                    ↓
                                                                            Auto-Link Detection
```

### 2.7 Risk Score Calculation

| Component | Detail |
|-----------|--------|
| **Agent** | `risk_detection.py` (SK-004) |
| **Model** | GPT-4o (temperature=0) |
| **Input** | Full contract text, chunked at 30KB with 2KB overlap |

**10 Risk Categories with Weights:**

| Category | Weight | Default Severity |
|----------|--------|-----------------|
| `unlimited_liability` | 15 | HIGH |
| `missing_limitation` | 15 | HIGH |
| `broad_indemnification` | 12 | HIGH |
| `unfavorable_ip` | 12 | HIGH |
| `weak_termination` | 10 | MEDIUM |
| `auto_renewal_trap` | 10 | MEDIUM |
| `one_sided_terms` | 10 | HIGH |
| `weak_confidentiality` | 8 | MEDIUM |
| `regulatory_risk` | 8 | MEDIUM |
| `ambiguous_language` | 5 | LOW |

**Score Aggregation (multi-chunk):**

```python
# Per risk factor: keep highest-scoring instance across chunks
# If found in multiple chunks: score = min(100, score * 1.1)

# Overall score from chunk scores:
overall_score = int(0.6 * max(chunk_scores) + 0.4 * avg(chunk_scores))
overall_score = min(100, overall_score)
```

**Risk Level Thresholds:**

| Level | Score Range |
|-------|------------|
| **LOW** | 0–25 |
| **MEDIUM** | 26–50 |
| **HIGH** | 51–75 |
| **CRITICAL** | 76–100 |

### 2.8 Metadata Extraction

| Component | Detail |
|-----------|--------|
| **Agent** | `metadata_extraction.py` (SK-001) |
| **Model** | GPT-4o (temperature=0) |
| **Input** | First 12,000 chars + last 4,000 chars (or full text if < 25,000) |

**Extracted Fields:**

| Field | DB Column | Validation |
|-------|-----------|------------|
| Contract Type | `contract_type` (Enum) | Must match one of 15 defined types |
| Counterparty | `counterparty` (VARCHAR 255) | Must be real company name, not placeholder |
| Effective Date | `effective_date` (Date) | ISO format YYYY-MM-DD |
| Expiration Date | `expiration_date` (Date) | Can be calculated from term clause |
| Contract Value | `contract_value` (Numeric 15,2) | Parsed to decimal |
| Currency | `currency` (VARCHAR 3) | Mapped to ISO code (e.g., "US Dollar" → "USD") |
| Jurisdiction | `jurisdiction` (VARCHAR 100) | State/country name |
| Parties | N/A (used for counterparty logic) | List of all entities |

**Confidence Score per Field:**

| Range | Meaning |
|-------|---------|
| 0.9–1.0 | Clearly stated in text |
| 0.7–0.9 | Inferred from context |
| 0.5–0.7 | Pattern-matched or ambiguous |
| 0.0–0.5 | Fallback/guess |

**Overall Confidence:** `AVG(field_confidences)` across fields with values

**Counterparty Validation Rules:**
- Must have legal entity suffix (Inc., LLC, Ltd., Corp., etc.)
- Must NOT be placeholder (`[Company Name]`, `Party A`)
- Must NOT be generic term (`Contractor`, `Vendor`, `Client`)
- If template detected (brackets, underline blanks): return null

### 2.9 Contract Type Mapping

The metadata agent extracts a type string, mapped to the DB enum:

| Full Name | Enum Value |
|-----------|------------|
| Master Services Agreement | `msa` |
| Non-Disclosure Agreement | `nda` |
| Statement of Work | `sow` |
| Amendment/Addendum | `amendment` |
| Vendor Agreement | `vendor_agreement` |
| Employment Contract | `employment_contract` |
| Service Level Agreement | `sla` |
| License Agreement | `license` |
| Lease Agreement | `lease` |
| Purchase Order | `purchase_order` |
| Consulting Agreement | `consulting` |
| Partnership Agreement | `partnership` |
| Distribution Agreement | `distribution` |
| Franchise Agreement | `franchise` |
| Other | `other` |

### 2.10 Deep Analysis Pipeline

Runs async after initial indexing completes (`_run_deep_analysis()`):

| Stage | Agent | Output Table | Key Fields |
|-------|-------|-------------|------------|
| Clause Extraction | SK-003 | `clauses` | clause_type (17 types), text, summary, confidence |
| Obligation Extraction | SK-005 | `obligations` | description, deadline, consequence, party, status |
| SLA Extraction | SK-008 | `contract_sla` | sla_name, target_value, metric_type, penalty |
| Renewal Detection | SK-006 | `contracts` (update) | auto_renewal, notice_period_days, renewal_term_months |
| Auto-Link Detection | N/A | `contract_links` | parent_id, child_id, link_type |

**17 Clause Types:**
`indemnification`, `liability`, `limitation_of_liability`, `termination`, `confidentiality`, `non_compete`, `non_solicitation`, `intellectual_property`, `warranty`, `governing_law`, `dispute_resolution`, `force_majeure`, `assignment`, `amendment`, `payment_terms`, `service_level`, `other`

### 2.11 Contract Value & Currency Handling

| Rule | Detail |
|------|--------|
| **DB Column** | `contract_value` — `Numeric(15,2)` |
| **Currency Column** | `currency` — `VARCHAR(3)` |
| **Mapping** | Full names mapped to ISO codes: "US Dollar" → "USD", "Euro" → "EUR", "British Pound" → "GBP" |
| **Display** | `formatCurrency(value, currency)` — locale-aware formatting |
| **Constraint** | VARCHAR(3) will reject full currency names — must be ISO code |

### 2.12 Status Transitions

```
pending → processing → completed
                    ↘ failed
```

| Status | Meaning |
|--------|---------|
| `pending` | Uploaded, awaiting processing |
| `processing` | AI pipeline running |
| `completed` | All extraction stages done |
| `failed` | Pipeline error (see `processing_error`) |

### 2.13 File Size Display

Frontend formatting function:
```
< 1024 bytes → "X bytes"
< 1 MB → "X.X KB"
< 1 GB → "X.X MB"
else → "X.X GB"
```

### 2.14 Days Until Expiration

| Field | Detail |
|-------|--------|
| **Formula** | `(contract.expiration_date - today).days` |
| **Used in** | Contract cards, renewal alerts, dashboard badges |
| **Notice Deadline** | `expiration_date - notice_period_days` |
| **Urgency Levels** | OVERDUE (<0), IMMEDIATE (≤7d), SOON (≤30d), UPCOMING (≤90d), FUTURE (>90d) |

---

### Data Flow Diagram

```
PDF/DOCX Upload
    ↓
Parse → Chunk → Embed in ChromaDB
    ↓
GPT-4o: Metadata Extraction
    ├── contract_type, counterparty, dates, value, currency
    └── confidence scores (0.0-1.0 per field)
    ↓
GPT-4o: Risk Detection
    ├── 10 risk categories with weights
    ├── risk_score (0-100) = 0.6 × max + 0.4 × avg
    └── risk_level (low/medium/high/critical based on thresholds)
    ↓
GPT-4o: Clause Extraction → 17 clause types with confidence
    ↓
GPT-4o: Obligation Extraction → deadlines, parties, consequences
    ↓
GPT-4o: SLA Extraction → metrics, targets, penalties
    ↓
GPT-4o: Renewal Detection → auto_renewal, notice_period, renewal_term
    ↓
Auto-Link Detection → parent/child contract relationships
```

---

## Page 3: Obligations

The Obligations page (`/obligations`) displays obligation tracking with compliance rates, status management, and evidence tracking. Backend logic lives in `backend/app/routers/obligations.py`.

### 3.1 Obligation Status Values

| Status | Meaning |
|--------|---------|
| `pending` | Not yet started |
| `in_progress` | Work underway |
| `completed` | Fulfilled — auto-sets RAG to GREEN, records `last_compliance_date` |
| `overdue` | Past deadline — auto-sets RAG to RED |
| `waived` | Excused from compliance — excluded from assessable count |

### 3.2 RAG Status

| RAG | Condition |
|-----|-----------|
| **GREEN** | `status == "completed"` or explicitly set |
| **AMBER** | Approaching deadline or manually set |
| **RED** | `status == "overdue"` or explicitly set |
| **NOT_ASSESSED** | Default — no assessment made yet |

### 3.3 Compliance Rate (Obligations Page)

| Field | Detail |
|-------|--------|
| **Formula** | `(completed / total) × 100` |
| **Code** | `obligations.py:455` |
| **Note** | Simple completed/total ratio — different from Dashboard's postsigning formula which uses assessable denominator |

### 3.4 Compliance Rate by Owner

| Field | Detail |
|-------|--------|
| **Formula** | `(completed / total) × 100` per `owner_type` |
| **Code** | `obligations.py:458-467` |
| **Groups** | provider, client, mutual, third_party, unspecified |
| **Metrics** | total, completed, overdue per group |

### 3.5 Compliance Rate by Category

| Field | Detail |
|-------|--------|
| **Formula** | `(completed / total) × 100` per `category` |
| **Code** | `obligations.py:470-479` |
| **Groups** | service_provision, payment, data_protection, compliance, etc. |

### 3.6 Per-Contract Compliance

| Field | Detail |
|-------|--------|
| **Formula** | `(completed / total) × 100` per contract |
| **Code** | `obligations.py:493-508` |
| **Metrics** | total, completed, in_progress, overdue, pending, rag_green, rag_amber, rag_red |

### 3.7 Overdue Detection

```python
# obligations.py:403-406
if status_val == "overdue":
    overdue_count += 1
    if obl.is_critical:
        critical_overdue += 1
```

### 3.8 Upcoming Deadlines

```python
# obligations.py:450-452
today = date.today()
seven_days = today + timedelta(days=7)
if obl.deadline and today <= obl.deadline <= seven_days:
    upcoming_7_days += 1
```

### 3.9 Dashboard vs Obligations Page Compliance Rates

| Metric | Dashboard (postsigning) | Obligations Page |
|--------|------------------------|------------------|
| **Numerator** | `completed + in_progress` | `completed` only |
| **Denominator** | `total - waived - pending_future` (assessable) | `total` |
| **Live Value** | 18.23% | 17.9% |
| **Reason** | More forgiving — credits partial work | Stricter — only fully done |

---

## Page 4: SLAs

SLA management served by `backend/app/routers/sla.py`. Individual SLA compliance uses a rolling measurement window.

### 4.1 Compliance Check

```python
# sla.py:102-114
def check_compliance(target_value, actual_value, operator):
    # operator: >=, <=, >, <, =
    if operator == ">=": return actual_value >= target_value
    elif operator == "<=": return actual_value <= target_value
    # ... etc
```

### 4.2 Deviation Percentage

| Field | Detail |
|-------|--------|
| **Formula (≥ targets)** | `((actual - target) / target) × 100` |
| **Formula (≤ targets)** | `((target - actual) / target) × 100` |
| **Code** | `sla.py:117-129` |
| **Note** | Negative deviation = below target for ≥ operators |

### 4.3 Breach Severity

| Severity | Threshold |
|----------|-----------|
| MINOR | `|deviation| < 5%` |
| MODERATE | `5% ≤ |deviation| < 15%` |
| MAJOR | `15% ≤ |deviation| < 30%` |
| CRITICAL | `|deviation| ≥ 30%` |
| **Code** | `sla.py:132-142` |

### 4.4 Penalty Calculation

```python
# sla.py:291-301
if not is_compliant and sla.has_penalty and sla.penalty_value:
    penalty_amount = sla.penalty_value  # flat or percentage
    if sla.max_penalty_cap and penalty_amount > sla.max_penalty_cap:
        penalty_amount = sla.max_penalty_cap
```

### 4.5 Current Compliance Rate (Per SLA)

| Field | Detail |
|-------|--------|
| **Formula** | `(compliant_count / total_measurements) × 100` |
| **Window** | Last 10 measurements (rolling) |
| **Code** | `sla.py:330-338` |

```python
recent = [r[0] for r in perf_result.all()]  # last 10 is_compliant booleans
sla.current_compliance_rate = Decimal(sum(recent) / len(recent) * 100)
```

### 4.6 SLA Compliance Summary (Aggregate)

| Field | Detail |
|-------|--------|
| **"Compliant" threshold** | `current_compliance_rate ≥ 95%` |
| **Overall rate** | `(total_compliant / total_slas) × 100` |
| **Code** | `sla.py:410-441` |

### 4.7 Consecutive Breaches

```python
# sla.py:324-327
if is_compliant:
    sla.consecutive_breaches = 0
else:
    sla.consecutive_breaches = (sla.consecutive_breaches or 0) + 1
```

### 4.8 Compliance Trend

| Field | Detail |
|-------|--------|
| **Window** | Last 3 measurements vs prior 3 |
| **Improving** | `recent_rate > older_rate + 0.1` (10% threshold) |
| **Declining** | `recent_rate < older_rate - 0.1` |
| **Stable** | Otherwise |
| **Code** | `sla.py:187-199` |

### 4.9 Active Breaches

A SLA is "in breach" when `consecutive_breaches > 0` (code: `sla.py:495`).

### 4.10 SLA Metric Types

`UPTIME_PERCENTAGE`, `AVAILABILITY`, `RESPONSE_TIME`, `RESOLUTION_TIME`, `DELIVERY_TIME`, `SUCCESS_RATE`, `ERROR_RATE`, `COMPLIANCE_RATE`, `UTILIZATION`, `THROUGHPUT`, `RECOVERY_TIME`, `RECOVERY_POINT`, `QUALITY_SCORE`, `CUSTOM`

---

## Page 5: Renewals

Renewal management served by `backend/app/routers/renewals.py` and displayed in `frontend/src/pages/RenewalsPage.tsx`.

### 5.1 Notice Deadline

```python
# renewals.py:33-39
notice_deadline = expiration_date - timedelta(days=notice_period_days)
```

### 5.2 Renewal Window

| Window | Condition |
|--------|-----------|
| `expired` | `days_until < 0` |
| `critical` | Past notice deadline AND not yet expired |
| `30_days` | `0 ≤ days_until ≤ 30` |
| `60_days` | `31 ≤ days_until ≤ 60` |
| `90_days` | `61 ≤ days_until ≤ 90` |
| `beyond_90` | `days_until > 90` |
| **Code** | `renewals.py:42-58, 116-118` |

### 5.3 Days Until Expiration

```python
days_until_expiration = (contract.expiration_date - today).days
```

### 5.4 SLA Stats for Renewal

```python
# renewals.py:61-88
avg_compliance = total_compliance / count_with_compliance  # avg of current_compliance_rate
active_breaches = sum of consecutive_breaches > 0
```

### 5.5 At-Risk Thresholds

| Risk Factor | Threshold |
|-------------|-----------|
| SLA breaches | `breaches > 0` |
| Low SLA compliance | `compliance < 90%` |
| High value | `contract_value > $100,000` |
| **Code** | `renewals.py:295-303` |

### 5.6 Value at Risk

`SUM(contract_value)` for all contracts in the selected renewal window.

### 5.7 Requires Action

`is_past_notice_deadline AND NOT auto_renewal` — contracts that won't auto-renew and are past notice.

### 5.8 Renewal Recommendation (AI)

| Factor | Positive | Neutral | Negative |
|--------|----------|---------|----------|
| SLA Compliance | ≥ 95% | 85-95% | < 85% |
| Contract Value | — | — | > $500K → "Request volume discount" |
| Risk Level | low | medium | high/critical → "conduct risk review" |

**Decision Logic (renewals.py:599-622):**

```
if negative_count > positive_count:
    if sla_compliance < 70% → "terminate" (confidence: 0.8)
    else → "renegotiate" (confidence: 0.75)
elif positive_count > negative_count:
    → "renew" (confidence: 0.85)
else:
    → "review_terms" (confidence: 0.6)
```

---

## Page 6: Compliance Reports

Reports page (`/reports`) served by `backend/app/routers/reports.py` and `backend/app/services/reporting_service.py`.

### 6.1 Overall Compliance Formula

| Field | Detail |
|-------|--------|
| **Formula** | `obligation_compliance × 0.6 + sla_compliance × 0.4` |
| **Code** | `reporting_service.py:180` |
| **Weights** | Obligations 60%, SLAs 40% |

### 6.2 Obligation Compliance (Reports)

| Field | Detail |
|-------|--------|
| **Formula** | `(completed / total) × 100` |
| **Default** | 100% if no obligations |
| **Code** | `reporting_service.py:175` |

### 6.3 SLA Compliance (Reports)

| Field | Detail |
|-------|--------|
| **Per-SLA threshold** | `compliance_rate ≥ 80%` passes |
| **Aggregate** | `(compliant_count / total_count) × 100` |
| **Code** | `reporting_service.py:134` |
| **Note** | Uses 80% threshold (different from SLA page's 95%) |

### 6.4 On-Time Detection

```python
# reporting_service.py:69-73
was_on_time = obligation.last_compliance_date <= obligation.deadline
```

### 6.5 High-Risk Contract (Reports)

Contract is high-risk if `obligation_completed / obligation_total < 0.5` (50% threshold).

### 6.6 Trend Determination

| Field | Detail |
|-------|--------|
| **Improving** | Last value − first value > 2 percentage points |
| **Declining** | Last value − first value < −2 percentage points |
| **Stable** | Otherwise |
| **Code** | `reporting_service.py:145-157` |

### 6.7 Trend Change Percentage

```python
# reporting_service.py:290-292
obligation_change = obligation_rates[-1] - obligation_rates[0]  # percentage point delta
sla_change = sla_rates[-1] - sla_rates[0]
overall_change = overall_rates[-1] - overall_rates[0]
```

### 6.8 Trend Periods

| Period | Calculation |
|--------|------------|
| **Weekly** | 7-day windows, `end = today - timedelta(weeks=i)`, `start = end - 6 days` |
| **Monthly** | Calendar months, full month boundaries |

### 6.9 CSV Export Columns

**Summary section:** Total Obligations, Completed, Overdue, Obligation Compliance Rate, Total SLAs, Compliant, Breached, SLA Compliance Rate, Total Penalties, Overall Compliance Rate

**Obligations:** Contract, Counterparty, Title, Category, Owner, Due Date, Status, RAG, On Time

**SLAs:** Contract, Counterparty, SLA Name, Metric, Target, Compliance Rate, Breaches, Penalties

---

## Page 7: Organizations

Organizations page (`/organizations`) served by `backend/app/routers/organizations.py`.

### 7.1 Organization Hierarchy

- Hierarchical tree built recursively from `parent_id` relationships
- Level determined by `organization_level` field
- Tree endpoint: `GET /api/organizations/tree`
- Subsidiaries: `GET /api/organizations/{org_id}/subsidiaries`

### 7.2 Filtering

All queries filtered by `tenant_id` (multi-tenant isolation). Super admin sees all.

### 7.3 Relationships Per Org

`GET /api/organizations/{org_id}/relationships` returns all `BusinessRelationship` records where the org is `org_a_id` or `org_b_id`.

---

## Page 8: Business Relationships

Relationships page (`/relationships`) served by `backend/app/routers/relationships.py` and `backend/app/services/governance_bridge.py`.

### 8.1 Health Score Formula

The health score is a weighted composite of three components:

| Component | Weight | Formula |
|-----------|--------|---------|
| Contract Risk | 30% | `100 - average_risk_score` (inverted) |
| SLA Compliance | 40% | `AVG(ContractSLA.current_compliance_rate)` |
| Obligation Health | 30% | RAG-weighted average (see below) |

**Code:** `governance_bridge.py:814-884` and `relationships.py:462-599`

### 8.2 Obligation Health Component

| RAG Status | Points |
|------------|--------|
| GREEN | 100 |
| AMBER | 50 |
| RED | 0 |
| NOT_ASSESSED | 75 |

```
obligation_health = SUM(score × count) / total_obligations
```

### 8.3 Final Health Score

```
normalized_score = SUM(component_value × component_weight) / SUM(weights)
health_score = CLAMP(ROUND(normalized_score), 0, 100)
```

### 8.4 Summary Cards

| Card | Formula |
|------|---------|
| Total Relationships | `COUNT(*)` |
| Average Health | `MEAN(health_score)` |
| Healthy | `COUNT WHERE health_score ≥ 80` |
| At Risk | `COUNT WHERE health_score < 70` |

---

## Page 9: KPI Scorecard

KPI page (`/kpis`) served by `backend/app/routers/kpis.py` and `backend/app/services/kpi_service.py`.

### 9.1 Perception Gap Calculation

```python
# kpi_service.py:66-124
# Only APPROVED scores included
internal_avg = MEAN([s.score for s in scores if s.is_internal and s.approval_status == "approved"])
external_avg = MEAN([s.score for s in scores if not s.is_internal and s.approval_status == "approved"])
gap = ROUND(internal_avg - external_avg, 2)
```

### 9.2 Gap Severity Classification

| Severity | Threshold | Requires Action |
|----------|-----------|-----------------|
| `minor` | `|gap| < 1` | No |
| `moderate` | `1 ≤ |gap| < 2` | No |
| `significant` | `2 ≤ |gap| < 3` | Yes |
| `critical` | `|gap| ≥ 3` | Yes |
| **Code** | `kpi.py:200-211` | |

### 9.3 KPI Enrichment

Each KPI response includes:
- `latest_internal_score` — most recent approved internal score
- `latest_external_score` — most recent approved external score
- `latest_gap` — calculated gap
- `latest_gap_severity` — severity classification

### 9.4 Gap Summary Aggregation

| Metric | Formula |
|--------|---------|
| `critical_gaps` | `COUNT WHERE severity = "critical"` |
| `significant_gaps` | `COUNT WHERE severity = "significant"` |
| `aligned` | `COUNT WHERE severity = "minor"` or no gap |

### 9.5 Perception Score Approval Flow

`draft` → `pending_approval` → `approved` / `rejected`

Only approved scores enter gap calculations.

---

## Page 10: Improvements

Improvements page (`/improvements`) served by `backend/app/routers/improvements.py`.

### 10.1 Status Values

`open` → `in_progress` → `completed` | `blocked` | `cancelled`

### 10.2 Priority Levels

`critical` > `high` > `medium` > `low`

### 10.3 Progress Tracking

`progress` field (0-100%) — manually set, displayed as percentage bar.

### 10.4 Auto-Creation from Risks

High-risk clause types trigger auto-creation via `governance_bridge.py:758-812`:

| Clause Type | Improvement Title |
|-------------|------------------|
| `indemnification` | "Broad Indemnification" |
| `limitation_of_liability` | "Weak Liability Protection" |
| `termination` | "Unfavorable Termination Terms" |
| `intellectual_property` | "IP Ownership Risk" |
| `confidentiality` | "Weak Confidentiality" |
| `auto_renewal` | "Auto-Renewal Trap" |
| `data_protection` | "Data Protection Gap" |
| `force_majeure` | "Missing Force Majeure Protection" |

Sources: `contract`, `manual`, `perception_gap`

### 10.5 Overdue Count

`due_date < today AND status IN (open, in_progress)`

---

## Page 11: Surveys

Surveys page (`/surveys`) served by `backend/app/routers/surveys.py`.

### 11.1 Survey Instance Status

`draft` → `scheduled` → `sent` → `in_progress` → `completed` | `expired` | `cancelled`

### 11.2 Response Rate

```
response_rate = (responses_submitted / total_respondents) × 100
```

### 11.3 Score Aggregation

| Question Type | Aggregation |
|---------------|-------------|
| `rating` (1-10) | Mean |
| `text` | Collected as-is |
| `multiple_choice` | Option counts |

### 11.4 KPI Linking

Survey questions can have `kpi_id` — responses feed into perception score workflow, enabling external stakeholder feedback to drive KPI scoring.

---

## Page 12: Risk Analysis

Risk detection served by `backend/app/agents/risk_detection.py`.

### 12.1 Risk Categories & Weights

| Category | Weight | Default Severity |
|----------|--------|-----------------|
| `unlimited_liability` | 15 | HIGH |
| `missing_limitation` | 15 | HIGH |
| `broad_indemnification` | 12 | HIGH |
| `unfavorable_ip` | 12 | HIGH |
| `weak_termination` | 10 | MEDIUM |
| `auto_renewal_trap` | 10 | MEDIUM |
| `one_sided_terms` | 10 | HIGH |
| `weak_confidentiality` | 8 | MEDIUM |
| `regulatory_risk` | 8 | MEDIUM |
| `ambiguous_language` | 5 | LOW |
| **Total** | **105** | |

### 12.2 Risk Score Formula (Content-Weighted)

```
For each deduplicated risk factor:
    contribution = (factor_score × category_weight) / total_category_weight

overall_score = MIN(100, SUM(contributions))
```

**High-severity floor:** If `≥ 3` HIGH-severity factors found and `score < 51`, floor to 51 (ensures HIGH rating).

**Code:** `risk_detection.py:268-283`

### 12.3 Risk Level Thresholds

| Level | Score Range |
|-------|------------|
| LOW | 0-25 |
| MEDIUM | 26-50 |
| HIGH | 51-75 |
| CRITICAL | 76-100 |

### 12.4 Multi-Chunk Processing

- Text split into 30KB chunks with 2KB overlap
- Each chunk analyzed independently by GPT-4o
- Risk factors deduplicated by category across chunks

### 12.5 Deduplication

```python
# Per category, keep highest-scoring factor
# If found in multiple chunks: boost score × 1.1 (capped at 100)
# Merge clause references (up to 3)
```

### 12.6 Confidence

```
overall_confidence = MEAN(factor.confidence for all deduplicated factors)
```

---

## Page 13: Extraction Quality

Extraction quality page (`/admin/extraction-quality`) served by `backend/app/services/extraction_quality_service.py`.

### 13.1 Overall Score

```python
# extraction_quality_service.py:82-87
overall_score = MEAN(scores)  # across all verified golden set contracts
```

### 13.2 Metadata Score

```python
# extraction_quality_service.py:138-154
meta_fields = [counterparty, contract_type, effective_date, expiration_date, contract_value, currency]
metadata_score = (meta_filled / len(meta_fields)) × 100
```

### 13.3 Score Color Thresholds (Frontend)

| Score | Color |
|-------|-------|
| ≥ 90% | Green |
| ≥ 70% | Yellow |
| < 70% | Red |
| null | Gray |

### 13.4 Verification Statuses

`correct` | `incorrect` | `partial` | `pending`

---

## Page 14: Vendor Management

Vendor page (`/vendors`) served by `backend/app/services/vendor_service.py`.

### 14.1 Composite Performance Score

```python
# vendor_service.py:81-105
score = (obligation_compliance × 0.40) +
        (sla_compliance × 0.30) +
        (responsiveness × 0.20) +      # defaults to 75.0
        (issue_resolution × 0.10)       # defaults to 80.0
```

### 14.2 Risk Level / Grade

| Score | Risk Level | Grade |
|-------|-----------|-------|
| ≥ 90 | — | A |
| ≥ 80 | Low | B |
| ≥ 70 | — | C |
| ≥ 60 | Medium | D |
| ≥ 40 | High | F |
| < 40 | Critical | F |

**At-risk threshold:** `score < 60` (vendor_service.py:109)

### 14.3 Vendor Metrics

| Metric | Source |
|--------|--------|
| Obligation Compliance | `(completed + in_progress) / assessable × 100` |
| SLA Compliance | `AVG(current_compliance_rate)` across vendor's SLAs |
| Total Exposure | `SUM(contract_value)` |
| Active Contracts | `COUNT WHERE expiration_date ≥ today OR NULL` |
| SLA Breaches | `COUNT WHERE consecutive_breaches > 0` |
| Penalties | `SUM(penalty_amount) WHERE penalty_applied = True` |

---

## Page 15: External Portal

External portal served by `backend/app/routers/external_portal.py`. No authentication — uses token-based access.

### 15.1 Token Validation

| Check | Rule |
|-------|------|
| Token exists | `ExternalAccessToken` with matching token string |
| Token valid | `is_valid = True`, not revoked, `expires_at > now` |
| User active | Linked `ExternalUser.is_active = True` |
| Contract access | Non-revoked `ContractShare` for the contract |
| Governance access | `token_type IN (PERCEPTION_SCORING, MULTI_PURPOSE)` with `relationship_id` |

### 15.2 Perception Score Submission (External)

- Score range: 1-10 (slider)
- Period format: `YYYY-QN` (e.g., "2026-Q2")
- Auto-approved: `approval_status = "approved"`
- Triggers `recalculate_gap()` for KPI/period

### 15.3 Governance Data Filtering

- KPIs limited to `is_active = True`
- Returns last 4 approved perception scores per KPI
- Excludes sensitive data (approver names, audit details)
- Comments filtered: external users cannot see `is_internal = True` comments

---

## Page 16: Workflow / Approvals

Workflow admin (`/admin/scheduler`) served by `backend/app/routers/workflow_admin.py`.

### 16.1 Approval State Machine

```
pending → approved (terminal — triggers action)
       → rejected (terminal)
       → escalated → approved / rejected
       → delegated → approved / rejected
       → expired (terminal — after timeout)
```

### 16.2 SLA Tracking for Approvals

| Metric | Calculation |
|--------|-------------|
| Approval timeout | `approval_timeout_hours` per step (default: 24h) |
| Expiration | `requested_at + timedelta(hours=timeout)` |
| Is expired | `now > expires_at AND status = pending` |
| Time to decision | `(decided_at - requested_at).total_seconds()` |
| Auto-escalate | If expired AND `auto_approve_after_timeout = True` |

### 16.3 Execution Status

`pending` → `pending_approval` → `approved` → `executing` → `completed` | `failed` | `skipped` | `cancelled`

### 16.4 Retry Logic

| Parameter | Default |
|-----------|---------|
| `max_retries` | 3 |
| `retry_delay_seconds` | 60 |
| `continue_on_failure` | False |
| Can retry | `status = failed AND attempts < max_attempts` |

### 16.5 Event Trigger Types

`contract_created`, `contract_uploaded`, `obligation_created`, `obligation_overdue`, `obligation_completed`, `sla_breach_detected`, `sla_resolved`, `renewal_upcoming`, `renewal_decision_due`, `approval_required`, `approval_expired`, `batch_process_started`, `batch_process_completed`

### 16.6 Integration Health

```
success_rate = (total_requests - failed_requests) / total_requests × 100
health_status = "healthy" | "unhealthy"
```

---

## Appendix A: Threshold Summary

| Metric | Threshold | Context |
|--------|-----------|---------|
| Overall Compliance | `obl × 0.6 + sla × 0.4` | Dashboard, Reports |
| Obligation Compliance (Dashboard) | `(completed + in_progress) / assessable` | Postsigning |
| Obligation Compliance (Reports) | `completed / total` | Reports page |
| SLA Compliant (SLA Page) | `current_compliance_rate ≥ 95%` | SLA summary |
| SLA Compliant (Reports) | `compliance_rate ≥ 80%` | Reports page |
| Contract At Risk | `overdue ≥ 2 OR overdue/total > 30%` | Dashboard |
| High-Risk Contract (Reports) | `completion_rate < 50%` | Reports |
| Renewal Critical | Past notice AND not expired | Renewals |
| Renewal At-Risk SLA | `compliance < 90%` | Renewals |
| Renewal High Value | `> $100,000` | Renewals |
| Breach Severity | `<5% / 5-15% / 15-30% / ≥30%` | SLA |
| SLA Trend Change | `> 10%` between periods | SLA |
| Report Trend Change | `> 2 ppt` between periods | Reports |
| Vendor At-Risk | `score < 60` | Vendors |
| Vendor Critical | `score < 25` | Vendors |
| Gap Minor/Moderate/Significant/Critical | `<1 / 1-2 / 2-3 / ≥3` | KPIs |
| Risk LOW/MEDIUM/HIGH/CRITICAL | `0-25 / 26-50 / 51-75 / 76-100` | Risk |
| Extraction Quality Good/Warning/Bad | `≥90% / ≥70% / <70%` | Extraction |
| Health Score Healthy | `≥ 80` | Relationships |
| Health Score At-Risk | `< 70` | Relationships |

## Appendix B: Weight Summary

| Calculation | Weights |
|-------------|---------|
| Overall Compliance | Obligations 60%, SLAs 40% |
| Health Score | Contract Risk 30%, SLA Compliance 40%, Obligation Health 30% |
| Vendor Score | Obligations 40%, SLA 30%, Responsiveness 20%, Issue Rate 10% |
| Risk Score | Category weights: unlimited_liability 15, missing_limitation 15, broad_indemnification 12, unfavorable_ip 12, weak_termination 10, auto_renewal_trap 10, one_sided_terms 10, weak_confidentiality 8, regulatory_risk 8, ambiguous_language 5 |
