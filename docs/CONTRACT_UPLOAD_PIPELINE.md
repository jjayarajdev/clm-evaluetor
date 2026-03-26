# Contract Upload Pipeline - What Happens When You Load an MSA + SOWs

## The Short Version

When you upload an MSA and a bunch of SOWs for a client, the platform:

1. **Parses** each document (PDF/DOCX → text)
2. **Chunks & classifies** each section semantically (scope, payment, SLA, termination, etc.)
3. **Embeds** chunks into ChromaDB for AI-powered search
4. **Runs 9 AI agents** to extract metadata, risks, clauses, obligations, SLAs, renewals, and compliance gaps
5. **Auto-detects parent-child links** between the MSA and its SOWs using 6 weighted signals
6. **Populates** the dashboard, compliance tracker, renewal calendar, and risk register

All of this happens **automatically in the background** — the user gets an immediate upload confirmation while processing runs asynchronously.

---

## End-to-End Flow

```
User Uploads Files
       │
       ▼
┌─────────────────────────────┐
│  PHASE 1: UPLOAD            │  Immediate (< 1 second)
│  Create contract records    │
│  Store files on disk        │
│  Return success response    │
│  Queue background tasks     │
└──────────┬──────────────────┘
           │ (async background)
           ▼
┌─────────────────────────────┐
│  PHASE 2: INDEXING           │  ~30-60 seconds per file
│  Parse PDF/DOCX → text      │
│  Chunk into sections         │
│  Classify sections (AI)      │
│  Store in ChromaDB           │
│  Extract metadata (AI)       │
│  Assess risk (AI)            │
│  Auto-detect links           │
│  Mark contract COMPLETED     │
└──────────┬──────────────────┘
           │ (async background)
           ▼
┌─────────────────────────────┐
│  PHASE 3: DEEP ANALYSIS     │  ~2-5 minutes per file
│  Extract clauses (AI)        │
│  Extract obligations (AI)    │
│  Extract SLAs (AI)           │
│  Analyze renewals (AI)       │
│  Schema-based extraction     │
│  Compliance gap detection    │
│  Enhanced auto-linking       │
└─────────────────────────────┘
```

---

## Phase 1: Upload

**Endpoint:** `POST /api/contracts/upload`

When a user uploads a file, the system:

| Step | Action | Result |
|------|--------|--------|
| 1 | Validate file (PDF/DOCX, size limits) | Reject invalid files |
| 2 | Compute SHA256 content hash | Detect duplicate uploads |
| 3 | Store file to disk | `storage/uploads/{tenant}/{date}/{filename}` |
| 4 | Create Contract record | Status = `PENDING`, links to tenant + user |
| 5 | Log audit entry | `CONTRACT_UPLOAD` with filename and size |
| 6 | Spawn background task | Indexing starts without blocking the user |
| 7 | Return response | `{"id": "...", "status": "pending", "message": "Processing started"}` |

The user sees the contract appear immediately in the contracts list with a "Processing" badge.

---

## Phase 2: Indexing Pipeline

### Step 2.1 — Document Parsing

The parser extracts raw text from PDF (via pdfplumber) or DOCX (via python-docx):

```
MSA_Acme_2024.pdf → "MASTER SERVICES AGREEMENT\n\nThis Master Services Agreement
('Agreement') is entered into as of January 1, 2024, by and between Acme Corporation
('Client') and Our Company ('Provider')...\n\n1. SCOPE OF SERVICES..."
```

**Output:** Full text + extracted title

### Step 2.2 — Semantic Chunking

The document is split into meaningful chunks (not arbitrary 500-word blocks):

```
Chunk 0: Preamble (pages 1-1)     → "This Master Services Agreement..."
Chunk 1: Definitions (pages 1-2)   → "1. DEFINITIONS. 'Services' means..."
Chunk 2: Scope (pages 2-3)         → "2. SCOPE OF SERVICES. Provider shall..."
Chunk 3: Payment (pages 3-4)       → "3. PAYMENT TERMS. Client shall pay..."
Chunk 4: SLA (pages 4-6)           → "4. SERVICE LEVELS. 4.1 Uptime..."
Chunk 5: Confidentiality (page 6)  → "5. CONFIDENTIALITY..."
...
```

### Step 2.3 — AI Section Classification

Each chunk is classified by an AI model into one of 16 semantic types:

| Section Type | Examples |
|-------------|----------|
| `preamble` | Opening paragraph, recitals |
| `definitions` | Defined terms |
| `parties` | Party identification |
| `scope` | Services description, deliverables |
| `terms` | Term and duration |
| `payment` | Fees, invoicing, payment schedules |
| `confidentiality` | NDA provisions |
| `liability` | Limitation of liability, indemnification |
| `termination` | Termination rights, notice periods |
| `ip` | Intellectual property ownership |
| `compliance` | Regulatory, data protection |
| `governance` | Management structure, escalation |
| `sla` | Service levels, performance metrics |
| `exhibits` | Schedules, appendices |
| `signatures` | Signature blocks |
| `general` | Miscellaneous provisions |

Each classification includes a **confidence score** and **semantic tags** (e.g., `"liability,indemnification"`).

### Step 2.4 — ChromaDB Vector Storage

Every chunk is embedded and stored in ChromaDB with rich metadata:

```python
{
    "id": "contract-uuid_chunk_4",
    "text": "4. SERVICE LEVELS. 4.1 System Uptime...",
    "metadata": {
        "contract_id": "...",
        "tenant_id": "...",
        "filename": "MSA_Acme_2024.pdf",
        "section_type": "sla",
        "section_title": "Service Levels",
        "page_number": 4,
        "semantic_tags": "sla,uptime,performance"
    }
}
```

This enables the **Ask AI** feature — users can ask natural language questions and get answers grounded in the actual contract text via RAG (Retrieval-Augmented Generation).

### Step 2.5 — Clause Record Creation

Each classified chunk becomes a `Clause` database record:

```
Clause: SERVICE_LEVEL | "4. SERVICE LEVELS. 4.1 System Uptime..." | page 4 | confidence 0.92
Clause: PAYMENT_TERMS | "3. PAYMENT TERMS. Client shall pay..." | page 3 | confidence 0.95
Clause: TERMINATION   | "8. TERMINATION. Either party may..." | page 8 | confidence 0.89
```

### Step 2.6 — Metadata Extraction (AI Agent #1)

The **Metadata Extraction Agent** reads the document and extracts structured data:

| Field | MSA Example | SOW Example |
|-------|------------|-------------|
| `contract_type` | MSA | SOW |
| `counterparty` | Acme Corporation | Acme Corporation |
| `effective_date` | 2024-01-01 | 2024-03-01 |
| `expiration_date` | 2026-12-31 | 2024-09-01 |
| `contract_value` | 600,000.00 | 150,000.00 |
| `currency` | USD | USD |
| `jurisdiction` | State of Delaware | State of Delaware |
| `parties` | ["Acme Corporation", "Our Company"] | ["Acme Corporation", "Our Company"] |

**Critical checkpoint:** Metadata is flushed to DB here. Even if subsequent AI stages fail, the contract's core metadata is preserved.

### Step 2.7 — Risk Assessment (AI Agent #2)

The **Risk Detection Agent** scans for 10 risk categories:

| Category | Weight | Example Finding |
|----------|--------|-----------------|
| `unlimited_liability` | 15 | "No liability cap specified in Section 7" |
| `broad_indemnification` | 12 | "Provider indemnifies for all claims including indirect damages" |
| `weak_termination` | 10 | "Client can terminate for convenience; Provider cannot" |
| `auto_renewal_trap` | 10 | "Auto-renews for 2 years with only 30-day notice window" |
| `unfavorable_ip` | 12 | "All work product becomes Client property including pre-existing IP" |
| `weak_confidentiality` | 8 | "No time limit on confidentiality obligations" |
| `missing_limitation` | 15 | "No cap on consequential damages" |
| `one_sided_terms` | 10 | "Client can assign; Provider cannot without consent" |
| `regulatory_risk` | 8 | "No data residency requirements despite GDPR scope" |
| `ambiguous_language` | 5 | "'Best efforts' used without clear definition" |

**Output:** Risk score (0-100) and risk level (LOW / MEDIUM / HIGH / CRITICAL)

```
MSA Risk: score=45, level=MEDIUM
  - broad_indemnification: HIGH (score 35) — "Provider shall indemnify and hold harmless..."
  - auto_renewal_trap: MEDIUM (score 25) — "Agreement auto-renews for successive 12-month periods..."
  - weak_termination: MEDIUM (score 20) — "Client may terminate for convenience with 30 days notice"
```

### Step 2.8 — Auto-Link Detection

This is where the MSA-SOW relationship is discovered. The **Auto-Link Detector** uses 6 weighted signals:

| Signal | Weight | MSA↔SOW Match? |
|--------|--------|----------------|
| **Counterparty Match** | 0.30 | Yes — both say "Acme Corporation" |
| **Type Hierarchy** | 0.25 | Yes — SOW is a known child type of MSA |
| **Semantic Similarity** | 0.20 | Likely — SOW references MSA terms |
| **Filename Pattern** | 0.15 | Maybe — "SOW" in filename |
| **Date Proximity** | 0.10 | Yes — SOW dates fall within MSA term |
| **Same Batch** | 0.15 | Yes — uploaded together |

**Confidence calculation example:**
```
SOW1 → MSA link:
  counterparty_match:  0.30  (exact match: "Acme Corporation")
  type_hierarchy:      0.25  (SOW is child of MSA)
  filename_pattern:    0.15  ("SOW" in filename)
  same_batch:          0.15  (uploaded in same session)
  ─────────────────────────
  Total confidence:    0.85  ✓ Strong match
```

**Creates a `SuggestedContractLink`:**
```json
{
  "source_contract": "Acme_SOW_Project1.pdf",
  "target_contract": "MSA_Acme_2024.pdf",
  "suggested_link_type": "sow",
  "suggested_direction": "source_is_child",
  "confidence_score": 0.85,
  "reasoning": "Type hierarchy: SOW falls under MSA; Same counterparty: Acme Corporation; Filename contains 'SOW'",
  "status": "pending"
}
```

The user can **approve or reject** these suggestions in the UI.

---

## Phase 3: Deep Analysis

After indexing completes, a second background task runs the heavier AI agents.

### Step 3.1 — Clause Extraction (AI Agent #3)

The **Clause Extraction Agent** does a thorough pass, extracting up to **30 clause types**:

**Legal/Risk Clauses:**
- INDEMNIFICATION, LIMITATION_OF_LIABILITY, TERMINATION, CONFIDENTIALITY
- INTELLECTUAL_PROPERTY, PAYMENT_TERMS, WARRANTY, FORCE_MAJEURE
- NON_COMPETE, NON_SOLICITATION, DATA_PROTECTION, DISPUTE_RESOLUTION
- ASSIGNMENT, NOTICE, GOVERNING_LAW, AUTO_RENEWAL

**IT Service/Outsourcing Clauses (for MSA/SOW):**
- SERVICE_DESCRIPTION, SERVICE_LEVEL, DELIVERABLE, GOVERNANCE
- TRANSITION, CHANGE_MANAGEMENT, SUPPORT, SECURITY
- PERSONNEL, PRICING, RISK_MITIGATION, SCOPE, ACCEPTANCE

For each clause:
```
{
  "clause_type": "SERVICE_LEVEL",
  "text": "Provider shall maintain 99.9% system uptime measured monthly...",
  "section_number": "4.1",
  "page_number": 4,
  "risk_level": "MEDIUM",
  "confidence": 0.94,
  "key_terms": ["99.9%", "monthly", "service credits"],
  "notes": "Penalty structure references Exhibit B"
}
```

### Step 3.2 — Obligation Extraction (AI Agent #4)

The **Obligation Tracking Agent** extracts actionable commitments from both parties:

**Obligation Types:** PAYMENT, DELIVERY, REPORTING, COMPLIANCE, NOTIFICATION, PERFORMANCE, OTHER

**25 Detailed Categories:** SERVICE_PROVISION, SERVICE_LEVELS, DELIVERY, PAYMENT, INVOICING, DATA_PROTECTION, AUDIT, INSURANCE, STAFFING, TRAINING, MAINTENANCE, SUPPORT, TESTING, and more.

**Example extractions from an MSA:**

| Obligated Party | Description | Type | Deadline | Recurrence |
|-----------------|-------------|------|----------|------------|
| Provider | Maintain 99.9% system uptime | PERFORMANCE | Ongoing | Monthly measured |
| Provider | Provide 24/7 technical support | PERFORMANCE | Ongoing | Continuous |
| Provider | Submit monthly status reports | REPORTING | Recurring | Monthly |
| Provider | Maintain SOC 2 Type II certification | COMPLIANCE | Annual | Annually |
| Client | Pay $50,000/month within 30 days of invoice | PAYMENT | Recurring | Monthly |
| Client | Provide 30 days notice for scope changes | NOTIFICATION | Relative | Per event |
| Both | Maintain confidentiality for 3 years post-termination | COMPLIANCE | Fixed Date | N/A |

Each obligation gets:
- **Status tracking:** PENDING → IN_PROGRESS → COMPLETED (or OVERDUE)
- **RAG status:** GREEN / AMBER / RED for compliance dashboard
- **Priority:** 1 (highest) to 5 (lowest)
- **Critical flag:** For obligations that trigger penalties on breach

### Step 3.3 — SLA Extraction (AI Agent #5)

The **SLA Extraction Agent** pulls out measurable service levels:

**13 Metric Types:** UPTIME_PERCENTAGE, AVAILABILITY, RESPONSE_TIME, RESOLUTION_TIME, DELIVERY_TIME, SUCCESS_RATE, ERROR_RATE, COMPLIANCE_RATE, UTILIZATION, THROUGHPUT, RECOVERY_TIME, RECOVERY_POINT, QUALITY_SCORE, CUSTOM

**Example extractions from an MSA:**

| SLA Name | Metric Type | Target | Operator | Penalty |
|----------|-------------|--------|----------|---------|
| System Uptime | UPTIME_PERCENTAGE | 99.9% | >= | 1% credit per 0.1% below |
| P1 Response Time | RESPONSE_TIME | 15 min | <= | $500 per incident |
| P1 Resolution Time | RESOLUTION_TIME | 4 hours | <= | $1,000 per incident |
| P2 Response Time | RESPONSE_TIME | 4 hours | <= | None |
| P2 Resolution Time | RESOLUTION_TIME | 24 hours | <= | None |
| Monthly Report Delivery | DELIVERY_TIME | 5 business days | <= | None |

Each SLA gets:
- **Severity:** CRITICAL / HIGH / MEDIUM / LOW
- **Penalty details:** Type (fixed/percentage/credit/tiered), value, cap
- **Measurement period:** Monthly, quarterly, annual
- **Compliance tracking:** `current_compliance_rate`, `consecutive_breaches`

**These SLAs are what connects to the ServiceNow integration** — SNOW SLA definitions can be mapped to these extracted SLAs for automated compliance monitoring.

### Step 3.4 — Renewal Analysis (AI Agent #6)

The **Renewal Monitoring Agent** extracts renewal terms:

```
MSA Renewal Terms:
  has_auto_renewal: true
  auto_renewal_term_months: 12
  notice_period_days: 90
  notice_deadline: 2026-10-02  (calculated: expiration - 90 days)
  initial_term_months: 36
  termination_for_convenience: true
  termination_notice_days: 60
  renewal_clause_text: "This Agreement shall automatically renew for successive
                        twelve (12) month periods unless either party provides
                        written notice of non-renewal at least ninety (90) days
                        prior to expiration."
```

This feeds the **Renewals page** — showing upcoming renewal deadlines, notice windows, and auto-renewal traps.

### Step 3.5 — Schema-Based Extraction (AI Agent #7)

For known contract types (MSA, SOW, NDA, etc.), a type-specific schema extracts additional structured fields:

**MSA Schema Fields:**
- Pricing model (fixed/T&M/milestone)
- Payment terms (Net 30, Net 60)
- Insurance requirements
- Data handling provisions
- Audit rights
- Governing law
- Services catalog

**SOW Schema Fields:**
- Project name and description
- Deliverables list with acceptance criteria
- Timeline and milestones
- Team composition and roles
- Pricing breakdown
- Dependencies and assumptions
- Out-of-scope items

Stored as JSONB in `contract.schema_data` for flexible querying.

### Step 3.6 — Compliance Gap Detection

For regulated industries (healthcare, finance, energy, etc.):

1. **Industry Detection** — AI determines the industry from contract content
2. **Compliance Gap Analysis** — Checks against industry-specific requirements (HIPAA, SOX, GDPR, etc.)
3. **Regulatory Obligations** — Extracts obligations specific to the detected regulatory framework

---

## What the User Sees After Processing

### Contracts Page
```
┌──────────────────────────────────────────────────────────────────┐
│ Contracts                                              [Upload] │
├──────────────────────────────────────────────────────────────────┤
│ MSA_Acme_2024.pdf          MSA    Acme Corp   Risk: MEDIUM  ●  │
│   ├── Acme_SOW_Project1.pdf  SOW  Acme Corp   Risk: LOW    ●  │
│   └── Acme_SOW_Project2.pdf  SOW  Acme Corp   Risk: LOW    ●  │
└──────────────────────────────────────────────────────────────────┘
```

### Contract Detail Page (MSA)
- **Overview tab:** Type, parties, dates, value, jurisdiction, risk score
- **Clauses tab:** 15-25 extracted clauses with risk levels
- **Obligations tab:** 10-20 obligations with deadlines, parties, and RAG status
- **SLAs tab:** 5-10 service levels with targets, penalties, compliance rates
- **Renewals tab:** Auto-renewal status, notice deadline, term details
- **Risk tab:** Risk score breakdown by category with recommendations
- **Linked Contracts:** SOW1, SOW2 shown as children
- **Ask AI:** Natural language Q&A grounded in the contract text

### Dashboard Impact
- **Contract count** increments
- **Risk distribution** updates (new medium-risk MSA)
- **Upcoming renewals** shows the MSA's notice deadline
- **Obligation tracker** shows new obligations needing monitoring

### Renewals Page
```
┌─────────────────────────────────────────────────────────────────┐
│ Upcoming Renewals                                               │
├─────────────────────────────────────────────────────────────────┤
│ MSA_Acme_2024.pdf                                               │
│   Auto-Renewal: YES (12 months)                                 │
│   Notice Deadline: Oct 2, 2026  ⚠️ 190 days remaining          │
│   Expiration: Dec 31, 2026                                      │
│   Action Required: Send non-renewal notice by Oct 2 or          │
│   agreement auto-renews through Dec 31, 2027                    │
└─────────────────────────────────────────────────────────────────┘
```

### Compliance Page
```
┌─────────────────────────────────────────────────────────────────┐
│ Obligation Compliance                                           │
├─────────────────────────────────────────────────────────────────┤
│ 🟢 Monthly payment - $50,000 due by 30th       Due: Apr 30     │
│ 🟢 Monthly status report                        Due: Apr 5      │
│ 🟡 SOC 2 certification renewal                  Due: Jun 30     │
│ 🔴 Insurance certificate expired                 Overdue!        │
└─────────────────────────────────────────────────────────────────┘
```

### ServiceNow Connection
The extracted SLAs can be mapped to ServiceNow SLA definitions:

```
Platform SLA: "System Uptime" (99.9%, monthly)
     ↕ mapped to
SNOW SLA: "Priority 1 response (15 minutes)" [sys_id: 2ca94b74...]

→ SLA measurements flow from SNOW into the platform
→ Compliance rates auto-calculated
→ Breach alerts triggered when thresholds crossed
```

---

## MSA → SOW Relationship Specifics

When SOWs are uploaded against an existing MSA, the auto-linker recognizes the parent-child pattern:

### What Gets Inherited
The SOW inherits context from its parent MSA:
- Same counterparty (used for link detection)
- Governing law from MSA applies to SOWs
- MSA's master terms (confidentiality, liability, IP) cover all SOWs
- Risk factors from MSA cascade to SOW risk assessment

### What's SOW-Specific
Each SOW has its own:
- Contract value (project-specific budget)
- Effective/expiration dates (project timeline)
- Deliverables and milestones
- Project-specific SLAs
- Team composition
- Acceptance criteria

### Link Types
The platform supports 15 link types for contract relationships:

| Link Type | Direction | Example |
|-----------|-----------|---------|
| `sow` | SOW is child of MSA | SOW references master terms |
| `amendment` | Amendment modifies parent | Change order to MSA |
| `addendum` | Addendum extends parent | Additional terms |
| `renewal` | Renewal extends parent | Contract extension |
| `exhibit` | Exhibit attached to parent | Pricing schedule |
| `schedule` | Schedule attached to parent | Service catalog |
| `appendix` | Appendix to parent | Technical specifications |
| `supersedes` | New contract replaces old | Updated MSA |
| `work_order` | Work order under MSA | Similar to SOW |
| `change_order` | Modifies existing SOW | Scope change |

### How Links Are Created

1. **Auto-suggested** — System detects with confidence score, user approves
2. **Manual** — User explicitly links contracts in the UI
3. **Batch upload** — Files uploaded together get higher link confidence

---

## Processing Times (Typical)

| Stage | Duration | What's Happening |
|-------|----------|-----------------|
| Upload | < 1 second | File storage, record creation |
| Parsing | 2-5 seconds | PDF/DOCX text extraction |
| Chunking + Classification | 5-10 seconds | AI section classification |
| ChromaDB Storage | 2-3 seconds | Vector embedding + storage |
| Metadata Extraction | 5-15 seconds | GPT-4o reads full document |
| Risk Assessment | 10-20 seconds | GPT-4o analyzes 10 risk categories |
| Auto-Link Detection | 2-5 seconds | Signal matching + vector similarity |
| Clause Extraction | 30-90 seconds | GPT-4o processes 25KB chunks |
| Obligation Extraction | 20-60 seconds | GPT-4o extracts commitments |
| SLA Extraction | 15-30 seconds | GPT-4o pulls metrics + penalties |
| Renewal Analysis | 5-10 seconds | GPT-4o identifies renewal terms |
| Schema Extraction | 10-20 seconds | Type-specific field extraction |
| Compliance Analysis | 10-30 seconds | Industry detection + gap analysis |
| **Total** | **~2-5 minutes** | **Per document** |

For a batch of 1 MSA + 2 SOWs: **~6-15 minutes total** (parallel processing).

---

## 9 AI Agents Summary

| # | Agent | What It Extracts | Key Output |
|---|-------|-----------------|------------|
| 1 | **Metadata Extraction** | Type, parties, dates, value | Contract record fields |
| 2 | **Risk Detection** | 10 risk categories with scores | Risk score + level |
| 3 | **Clause Extraction** | 30 clause types | Clause records |
| 4 | **Obligation Tracking** | Commitments with deadlines | Obligation records with RAG status |
| 5 | **Renewal Monitoring** | Auto-renewal, notice periods | Renewal calendar entries |
| 6 | **SLA Extraction** | Metrics, targets, penalties | ContractSLA records |
| 7 | **Schema Extraction** | Type-specific structured fields | JSONB schema_data |
| 8 | **Intent Router** | Query routing for Ask AI | Routes user questions to right agent |
| 9 | **Industry/Compliance** | Regulatory gaps | ComplianceGap records |
