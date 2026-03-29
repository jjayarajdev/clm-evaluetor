# Contract Upload Pipeline - What Happens When You Upload a Contract

> **Codebase Stats (March 2026):** 44 routers, 53 models, 38 services, 11 agent files, 25 scripts, ~405 API endpoints, 38 Alembic migrations, 37 frontend pages, 28 frontend components.

## The Short Version

When you upload a contract (MSA, SOW, NDA, Addendum, etc.), the platform:

1. **Creates** a contract record and returns immediately (status: pending)
2. **Parses** the document (PDF/DOCX to text, with OCR fallback for image-based PDFs)
3. **Chunks & classifies** each section semantically via LLM (scope, payment, SLA, termination, etc.)
4. **Embeds** chunks into ChromaDB for AI-powered search
5. **Runs AI agents** to extract metadata, assess risks, detect links, extract clauses, obligations, SLAs, renewals, and compliance gaps
6. **Bridges to governance** -- auto-creates organizations, business relationships, KPIs from SLAs, and improvement points from high-risk clauses
7. **Populates** the dashboard, compliance tracker, renewal calendar, and risk register

All of this happens **automatically in the background** via `asyncio.create_task` -- the user gets an immediate upload confirmation while processing runs asynchronously.

---

## End-to-End Flow

```
User Uploads File
       |
       v
+-----------------------------+
|  PHASE 1: UPLOAD            |  Immediate (< 1 second)
|  POST /api/contracts/upload |
|  Create contract record     |
|  Store file on disk         |
|  Return {id, status:pending}|
|  Spawn asyncio.create_task  |
+-------------+---------------+
              | (async background)
              v
+-----------------------------+
|  PHASE 2: INDEXING          |  ~30s (text PDF) to ~4min (OCR)
|  Parse PDF/DOCX -> text     |
|  Chunk into sections        |
|  Classify chunks via LLM    |
|  Store in ChromaDB          |
|  Extract metadata (AI)      |
|  Extract custom fields      |
|  Flush metadata to DB       |
|  Assess risk (AI)           |
|  Auto-detect links (pass 1) |
|  Mark contract COMPLETED    |
+-------------+---------------+
              | (called immediately after indexing)
              v
+-----------------------------+
|  PHASE 3: DEEP ANALYSIS    |  ~1-2 minutes per file
|  Re-parse full text         |
|  Store extracted_text on DB |
|  Extract clauses (AI)       |
|  Extract obligations (AI)   |
|  Extract SLAs (AI)          |
|  Reclassify chunks          |
|  Store all results to DB    |
|  Extract renewal terms (AI) |
|  Schema-based extraction    |
|  Auto-link detection (pass 2)|
|  Compliance analysis        |
|  Knowledge graph extraction |
|  Governance bridge (7 auto) |
+-----------------------------+
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
| 6 | Commit to DB, spawn `asyncio.create_task` | `_auto_process_contract` starts without blocking |
| 7 | Return response | `{"id": "...", "status": "pending", "message": "Processing started"}` |

The user sees the contract appear immediately in the contracts list with a "Processing" badge.

**Code path:** `contracts.py:upload_single_file` -> `asyncio.create_task(_auto_process_contract(...))` -> `IndexingService.index_contract()` -> `_run_deep_analysis()`

---

## Phase 2: Indexing Pipeline

Runs inside `IndexingService.index_contract()` in `app/services/indexer.py`. Uses a progress tracker so the frontend can poll for status updates.

### Step 2.1 -- Document Parsing

The parser extracts raw text from PDF (via PyMuPDF/fitz) or DOCX (via python-docx). For image-based PDFs (e.g., scanned documents, WeasyPrint-generated), OCR fallback via Tesseract is used automatically. Additional format support: XLSX/XLS (openpyxl/xlrd), PPTX/PPT (python-pptx).

```
MSA_FOXO_KR8AI_2025.pdf -> "MASTER SOFTWARE AND SERVICES AGREEMENT\n\n
This Master Software and Services Agreement ('Agreement') is entered into
as of March 15, 2025, by and between FOXO Technologies Inc. ('Client')
and KR8 AI Solutions LLC ('Provider')...\n\n1. SCOPE OF SERVICES..."
```

**Output:** Full text + extracted title

**Timing:** < 1 second for proper text PDFs (PyMuPDF direct text extraction); ~3.5 minutes for image-based/OCR PDFs on a t2.micro instance.

### Step 2.2 -- Semantic Chunking

The document is split into meaningful chunks (not arbitrary 500-word blocks). A 20-page MSA typically produces ~45 chunks.

```
Chunk 0:  Preamble (pages 1-1)     -> "This Master Software and Services Agreement..."
Chunk 1:  Definitions (pages 1-2)   -> "1. DEFINITIONS. 'Services' means..."
Chunk 2:  Scope (pages 2-3)         -> "2. SCOPE OF SERVICES. Provider shall..."
Chunk 3:  Payment (pages 3-4)       -> "3. PAYMENT TERMS. Client shall pay..."
Chunk 4:  SLA (pages 4-6)           -> "4. SERVICE LEVELS. 4.1 Uptime..."
Chunk 5:  Confidentiality (page 6)  -> "5. CONFIDENTIALITY..."
...
Chunk 44: Signatures (page 20)      -> "IN WITNESS WHEREOF..."
```

### Step 2.3 -- AI Section Classification (LLM)

Each chunk is classified by an LLM (GPT-4o) into one of 17 semantic types via `smart_classify_batch()` in `app/services/section_classifier.py`. Chunks are processed in batches of 10.

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

Each classification includes a **confidence score**, **section title**, and **semantic tags** (e.g., `"liability,indemnification"`).

Each classified chunk also creates a `Clause` database record with the mapped `ClauseType`:

```
Clause: SERVICE_LEVEL | "4. SERVICE LEVELS. 4.1 System Uptime..." | page 4 | confidence 0.92
Clause: PAYMENT_TERMS | "3. PAYMENT TERMS. Client shall pay..." | page 3 | confidence 0.95
Clause: TERMINATION   | "8. TERMINATION. Either party may..." | page 8 | confidence 0.89
```

### Step 2.4 -- ChromaDB Vector Storage

Every chunk is embedded and stored in ChromaDB with rich metadata. On first use, the `all-MiniLM-L6-v2` embedding model (~79MB) is downloaded automatically.

```python
{
    "id": "contract-uuid_chunk_4",
    "text": "4. SERVICE LEVELS. 4.1 System Uptime...",
    "metadata": {
        "contract_id": "...",
        "tenant_id": "...",
        "filename": "MSA_FOXO_KR8AI_2025.pdf",
        "section_type": "sla",
        "section_title": "Service Levels",
        "page_number": 4,
        "semantic_tags": "sla,uptime,performance"
    }
}
```

This enables the **Ask AI** feature -- users can ask natural language questions and get answers grounded in the actual contract text via RAG (Retrieval-Augmented Generation).

### Step 2.5 -- Metadata Extraction (AI Agent #1)

The **Metadata Extraction Agent** reads the document and extracts structured data:

| Field | MSA Example | Addendum Example |
|-------|------------|------------------|
| `contract_type` | MSA | AMENDMENT |
| `counterparty` | FOXO Technologies Inc. | FOXO Technologies Inc. |
| `effective_date` | 2025-03-15 | 2025-04-01 |
| `expiration_date` | 2028-03-14 | 2026-03-31 |
| `contract_value` | 1,200,000.00 | 240,000.00 |
| `currency` | USD | USD |
| `jurisdiction` | State of Delaware | State of Delaware |
| `parties` | ["FOXO Technologies Inc.", "KR8 AI Solutions LLC"] | ["FOXO Technologies Inc.", "KR8 AI Solutions LLC"] |

**Contract type mapping:** The agent handles full names and maps them to the enum. For example, "Master Software and Services Agreement" maps to MSA. Unrecognized types do not clear existing values.

**Excluded parties:** The tenant name and client name are passed as excluded parties so the AI does not set the uploader's own organization as the counterparty.

**Critical checkpoint:** Metadata is flushed to DB here (`await self.db.flush()`). Even if subsequent AI stages fail, the contract's core metadata is preserved.

### Step 2.6 -- Custom Field Extraction

If the tenant has custom field definitions configured, those fields are extracted from the contract text and stored as `contract.custom_fields` (JSONB).

### Step 2.7 -- Risk Assessment (AI Agent #2)

The **Risk Detection Agent** scans for 10 risk categories. For long documents, it processes text in chunks (e.g., 3 chunks for a 20-page MSA):

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
  - broad_indemnification: HIGH (score 35) -- "Provider shall indemnify and hold harmless..."
  - auto_renewal_trap: MEDIUM (score 25) -- "Agreement auto-renews for successive 12-month periods..."
  - weak_termination: MEDIUM (score 20) -- "Client may terminate for convenience with 30 days notice"
```

### Step 2.8 -- Auto-Link Detection (First Pass)

After marking the contract as COMPLETED, the **Auto-Link Detector** runs a first pass using 6 weighted signals. At this point, `extracted_text` may not yet be available (it is stored during deep analysis), so this pass relies on metadata and filename signals.

| Signal | Weight | Description |
|--------|--------|-------------|
| **Counterparty Match** | 0.30 | Exact or fuzzy match of counterparty names |
| **Type Hierarchy** | 0.25 | SOW is child of MSA, Amendment modifies parent, etc. |
| **Semantic Similarity** | 0.20 | Vector similarity of document content |
| **Filename Pattern** | 0.15 | "SOW" or "Amendment" in filename |
| **Date Proximity** | 0.10 | Dates fall within parent contract term |
| **Same Batch** | 0.15 | Uploaded together in a batch |

Creates `SuggestedContractLink` records with confidence scores. Minimum confidence threshold: 0.30.

---

## Phase 3: Deep Analysis

Called immediately after indexing completes (from `_auto_process_contract` in `contracts.py`). Runs in its own database sessions to avoid FK violations poisoning the indexer session.

### Step 3.1 -- Document Re-Parse and Text Storage

The document is parsed again (OCR again if needed for image-based PDFs) and the full `extracted_text` is stored on the contract record. This text is used by all subsequent AI agents.

### Step 3.2 -- Agent Registration

Calls `initialize_default_agents()` and `register_all_agents()` to ensure the SLA extraction agent and other agents are available in the agent registry.

### Step 3.3 -- Clause Extraction (AI Agent #3)

The **Clause Extraction Agent** does a thorough pass, splitting the document into chunks and extracting clauses across 17 clause types. A 20-page MSA typically yields 19-25 clauses.

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
```json
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

**Verified test data:** FOXO/KR8 AI MSA produced 25 clauses; Addendum produced 13 clauses.

### Step 3.4 -- Obligation Extraction (AI Agent #4)

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
- **Status tracking:** PENDING -> IN_PROGRESS -> COMPLETED (or OVERDUE)
- **RAG status:** GREEN / AMBER / RED for compliance dashboard
- **Priority:** 1 (highest) to 5 (lowest)
- **Critical flag:** For obligations that trigger penalties on breach

**Verified test data:** FOXO/KR8 AI MSA produced 19 obligations; Addendum produced 12 obligations.

### Step 3.5 -- SLA Extraction (AI Agent #5)

The **SLA Extraction Agent** pulls out measurable service levels:

**14 Metric Types:** UPTIME_PERCENTAGE, AVAILABILITY, RESPONSE_TIME, RESOLUTION_TIME, DELIVERY_TIME, SUCCESS_RATE, ERROR_RATE, COMPLIANCE_RATE, UTILIZATION, THROUGHPUT, RECOVERY_TIME, RECOVERY_POINT, QUALITY_SCORE, CUSTOM

**Example extractions from an MSA with SLA addendum:**

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

**Excel support:** For `.xlsx`/`.xls` files, structured SLA extraction is attempted first via `extract_and_store_excel_slas()`.

**Verified test data:** Addendum with SLA terms produced 6 SLAs.

### Step 3.6 -- Chunk Reclassification

After clause extraction, uncategorized chunks (those classified as `OTHER` during indexing) are reclassified. For example, chunks containing SLA patterns are reclassified as `SERVICE_LEVEL`, and chunks with governing law content are reclassified as `GOVERNING_LAW`. This uses `reclassify_sla_chunks()` from the clause extraction agent.

### Step 3.7 -- Database Commit

All clauses, obligations, and SLAs are committed to the database in a single transaction. Existing records for the contract (except `OTHER`-type clauses from indexing) are cleaned up before storing new results.

### Step 3.8 -- Renewal Analysis (AI Agent #6)

The **Renewal Monitoring Agent** extracts renewal terms:

```
MSA Renewal Terms:
  has_auto_renewal: true
  auto_renewal_term_months: 12
  notice_period_days: 90
  notice_deadline: 2028-01-14  (calculated: expiration - 90 days)
  initial_term_months: 36
  termination_for_convenience: true
  termination_notice_days: 60
  renewal_clause_text: "This Agreement shall automatically renew for successive
                        twelve (12) month periods unless either party provides
                        written notice of non-renewal at least ninety (90) days
                        prior to expiration."
```

This feeds the **Renewals page** -- showing upcoming renewal deadlines, notice windows, and auto-renewal traps.

### Step 3.9 -- Schema-Based Extraction (AI Agent #7)

For known contract types (MSA, SOW, NDA, etc.), a type-specific schema extracts additional structured fields using the schema registry (`get_schema_registry()`):

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

Stored as JSONB in `contract.schema_data` for flexible querying. Schema data is also synced to relational structure via `sync_schema_to_db()`.

### Step 3.10 -- Auto-Link Detection (Second Pass)

A second auto-link detection pass runs with the full `extracted_text` now available on the contract. This enables richer semantic similarity matching and can find links that the first pass missed.

**Verified test data:** Addendum auto-link found 1 suggestion (confidence 0.50, amendment type, matching on counterparty + filename signals).

### Step 3.11 -- Compliance Analysis

For all contracts, compliance analysis runs in four stages:

1. **Industry Detection** -- AI determines the industry from contract content (e.g., technology, healthcare, finance)
2. **Compliance Gap Analysis** -- Checks against industry-specific requirements (HIPAA, SOX, GDPR, etc.) and computes a compliance score
3. **Alert Creation** -- Creates compliance alerts for critical/high gaps
4. **Regulatory Obligations** -- For regulated industries (healthcare, finance, energy, etc.), extracts obligations specific to the detected regulatory framework

### Step 3.12 -- Knowledge Graph Extraction

Knowledge graph extraction is **deferred from the indexer to deep analysis** to prevent FK violations from poisoning the SQLAlchemy session and rolling back metadata changes. The KG extractor (`knowledge_graph_extractor.py`) builds entity-relationship graphs from the contract text, identifying parties, obligations, and their connections. The indexer marks this stage as "Deferred to deep analysis" in the progress tracker.

### Step 3.13 -- Governance Bridge (Final Step)

The **Governance Bridge** (`GovernanceBridgeService`) automatically populates relationship governance data from the contract's extracted information. It runs 7 automations, each independent and fault-tolerant -- one failure does not block others:

| # | Automation | Method | What It Does |
|---|-----------|--------|-------------|
| 1 | **Organization Match/Create** | `_match_or_create_organization` | Exact match -> fuzzy match -> auto-create Organization from counterparty name |
| 2 | **Relationship Match/Create** | `_find_or_create_relationship` | Finds internal org for tenant, checks both directions, creates BusinessRelationship if none exists |
| 3 | **KPI Creation from SLAs** | `_create_kpis_from_slas` | Maps SLA metric types to KPI categories via `SLA_TO_KPI_MAP` (14 metric type mappings) |
| 4 | **Improvement Points from Risks** | `_create_improvements_from_risks` | High/critical risk clauses -> ImprovementPoint records (8 clause types mapped) |
| 5 | **Health Score Calculation** | `_calculate_health_score` | Risk health (30%) + SLA compliance (40%) + obligation health (30%) |
| 6 | **SOW Service Linking** | `_link_sow_services` | SOW service descriptions -> ServicePortfolio -> RelationshipService records |
| 7 | **Auto-Link Re-Run** | (in `_run_deep_analysis`) | Re-runs auto-link detection with enriched metadata from all deep analysis stages |

**Organization matching strategy:**
1. Exact case-insensitive match on counterparty name
2. Fuzzy match: org name contains counterparty or first 10 chars overlap
3. Auto-create with type inferred from contract type (MSA/SOW -> CUSTOMER, VENDOR_AGREEMENT -> VENDOR, NDA -> PARTNER)

**Health score formula:**
- **Risk health (30% weight):** `100 - contract.risk_score` (inverted: low risk = high health)
- **SLA compliance (40% weight):** Average `current_compliance_rate` across all active SLAs
- **Obligation health (30% weight):** Weighted by RAG status (GREEN=100, AMBER=50, RED=0, NOT_ASSESSED=75)

**KPI category mapping (SLA metric type -> KPI):**
| SLA Metric Type | KPI Category | Measurement Type |
|----------------|-------------|-----------------|
| UPTIME_PERCENTAGE, AVAILABILITY, UTILIZATION | SERVICE_DELIVERY | PERCENTAGE |
| RESPONSE_TIME, RESOLUTION_TIME | TIMELINESS | TIME_HOURS |
| DELIVERY_TIME | TIMELINESS | TIME_DAYS |
| SUCCESS_RATE, COMPLIANCE_RATE | COMPLIANCE | PERCENTAGE |
| ERROR_RATE | QUALITY | PERCENTAGE |
| THROUGHPUT | SERVICE_DELIVERY | NUMBER |
| RECOVERY_TIME, RECOVERY_POINT | SERVICE_DELIVERY | TIME_HOURS |
| QUALITY_SCORE | QUALITY | RATING |

**Verified test data:** FOXO/KR8 AI MSA governance bridge auto-created KR8 AI organization, business relationship, and KPIs from SLAs. Addendum governance bridge matched existing organization, matched existing relationship, created 6 KPIs from SLAs.

---

## What the User Sees After Processing

### Contracts Page
```
+------------------------------------------------------------------+
| Contracts                                              [Upload]   |
+------------------------------------------------------------------+
| MSA_FOXO_KR8AI_2025.pdf     MSA    FOXO Technologies  Risk: MED  |
|   +-- Addendum_SLA_2025.pdf  AMEND  FOXO Technologies  Risk: LOW  |
+------------------------------------------------------------------+
```

### Contract Detail Page (MSA)
- **Overview tab:** Type, parties, dates, value, jurisdiction, risk score
- **Clauses tab:** 19-25 extracted clauses across 17 types with risk levels
- **Obligations tab:** 12-19 obligations with deadlines, parties, and RAG status
- **SLAs tab:** 6+ service levels with targets, penalties, compliance rates
- **Renewals tab:** Auto-renewal status, notice deadline, term details
- **Risk tab:** Risk score breakdown by category with recommendations
- **Linked Contracts:** Addendum shown as child
- **Ask AI:** Natural language Q&A grounded in the contract text

### Dashboard Impact
- **Contract count** increments
- **Risk distribution** updates (new medium-risk MSA)
- **Upcoming renewals** shows the MSA's notice deadline
- **Obligation tracker** shows new obligations needing monitoring

### Renewals Page
```
+-----------------------------------------------------------------+
| Upcoming Renewals                                                |
+-----------------------------------------------------------------+
| MSA_FOXO_KR8AI_2025.pdf                                         |
|   Auto-Renewal: YES (12 months)                                  |
|   Notice Deadline: Dec 14, 2027  -- 630 days remaining           |
|   Expiration: Mar 14, 2028                                       |
|   Action Required: Send non-renewal notice by Dec 14 or          |
|   agreement auto-renews through Mar 14, 2029                     |
+-----------------------------------------------------------------+
```

### Compliance Page
```
+-----------------------------------------------------------------+
| Obligation Compliance                                            |
+-----------------------------------------------------------------+
| [GREEN]  Monthly payment - $100,000 due by 30th    Due: Apr 30  |
| [GREEN]  Monthly status report                      Due: Apr 5   |
| [AMBER]  SOC 2 certification renewal                Due: Jun 30  |
| [RED]    Insurance certificate expired               Overdue!     |
+-----------------------------------------------------------------+
```

### Governance Impact (7 Automations)
- **Organization** created or matched for counterparty (exact -> fuzzy -> auto-create)
- **Business Relationship** created or matched (checks both directions)
- **KPIs** created from extracted SLAs with targets and measurement types (14 metric type mappings)
- **Improvement Points** flagged for high/critical-risk clauses (8 clause types mapped)
- **Health Score** calculated from risk (30%) + SLA compliance (40%) + obligation health (30%)
- **Service Portfolio** linked for SOW contracts (service descriptions -> RelationshipService)
- **Auto-Link Re-Run** with enriched metadata from deep analysis

---

## MSA to SOW/Addendum Relationship Specifics

When SOWs or Addendums are uploaded against an existing MSA, the auto-linker recognizes the parent-child pattern.

### What Gets Inherited
The SOW/Addendum inherits context from its parent MSA:
- Same counterparty (used for link detection)
- Governing law from MSA applies to children
- MSA's master terms (confidentiality, liability, IP) cover all children
- Risk factors from MSA cascade to child risk assessment

### What's Child-Specific
Each SOW/Addendum has its own:
- Contract value (project-specific budget)
- Effective/expiration dates (project timeline)
- Deliverables and milestones (SOW)
- Project-specific SLAs (Addendum)
- Team composition
- Acceptance criteria

### Link Types
The platform supports 15 link types for contract relationships:

| Link Type | Direction | Example |
|-----------|-----------|---------|
| `sow` | SOW is child of MSA | SOW references master terms |
| `amendment` | Amendment modifies parent | Change order to MSA |
| `addendum` | Addendum extends parent | Additional SLA terms |
| `renewal` | Renewal extends parent | Contract extension |
| `exhibit` | Exhibit attached to parent | Pricing schedule |
| `schedule` | Schedule attached to parent | Service catalog |
| `appendix` | Appendix to parent | Technical specifications |
| `supersedes` | New contract replaces old | Updated MSA |
| `work_order` | Work order under MSA | Similar to SOW |
| `change_order` | Modifies existing SOW | Scope change |

### How Links Are Created

1. **Auto-suggested (two passes)** -- System detects during indexing (pass 1) and deep analysis (pass 2) with confidence scores; user approves or rejects
2. **Manual** -- User explicitly links contracts in the UI
3. **Batch upload** -- Files uploaded together get higher link confidence via the `same_batch` signal

**Confidence calculation example:**
```
Addendum -> MSA link:
  counterparty_match:  0.30  (exact match: "FOXO Technologies Inc.")
  type_hierarchy:      0.00  (not a recognized parent-child type pairing)
  filename_pattern:    0.15  ("Addendum" in filename)
  semantic_similarity: 0.05  (some shared terminology)
  same_batch:          0.00  (uploaded separately)
  date_proximity:      ~0.00
  ─────────────────────────
  Total confidence:    0.50  -- Moderate match, pending user review
```

---

## Processing Times (Verified with Real Uploads)

### Image-Based PDF (FOXO MSA, 20 pages, WeasyPrint-generated)

| Stage | Duration | What's Happening |
|-------|----------|-----------------|
| Upload | < 1 second | File storage, record creation, return response |
| OCR Parsing | ~3.5 minutes | PyMuPDF + Tesseract OCR fallback for image-based PDF |
| Chunking + Classification | ~15 seconds | 45 chunks classified via LLM in batches of 10 |
| ChromaDB Storage | ~5 seconds | all-MiniLM-L6-v2 embedding (79MB download on first use) |
| Metadata Extraction | ~10 seconds | GPT-4o reads full document |
| Risk Assessment | ~15 seconds | GPT-4o processes in 3 chunks, scores 0-100 |
| Auto-Link (pass 1) | ~2 seconds | 6-signal scoring |
| **Indexing Total** | **~4 minutes** | |
| Clause Extraction | ~30 seconds | GPT-4o processes chunks, extracts 25 clauses |
| Obligation Extraction | ~20 seconds | GPT-4o extracts 19 obligations |
| SLA Extraction | ~10 seconds | GPT-4o pulls metrics + penalties |
| Renewal Analysis | ~5 seconds | GPT-4o identifies renewal terms |
| Compliance Analysis | ~15 seconds | Industry detection + gap analysis |
| Governance Bridge | ~5 seconds | Org/relationship/KPI creation |
| Auto-Link (pass 2) | ~2 seconds | Second pass with extracted_text |
| **Deep Analysis Total** | **~2 minutes** | |
| **End-to-End Total** | **~6 minutes** | |

### Proper Text PDF (Addendum, ~5 pages)

| Stage | Duration | What's Happening |
|-------|----------|-----------------|
| Upload | < 1 second | File storage, record creation |
| Parsing | < 1 second | PyMuPDF direct text extraction |
| Indexing total | ~30 seconds | Chunking, classification, embedding, metadata, risk |
| Clause Extraction | ~15 seconds | 13 clauses extracted |
| Obligation Extraction | ~15 seconds | 12 obligations extracted |
| SLA Extraction | ~10 seconds | 6 SLAs extracted from SLA terms |
| Auto-Link (pass 2) | ~2 seconds | Found 1 suggestion (confidence 0.50) |
| Governance Bridge | ~3 seconds | Matched org, matched relationship, created 6 KPIs |
| **Deep Analysis Total** | **~1 minute** | |
| **End-to-End Total** | **~1.5 minutes** | |

### Batch Upload (1 MSA + 2 SOWs)

Batch uploads process up to 2 contracts concurrently (`max_concurrent=2` via semaphore). Expected total: ~8-12 minutes depending on PDF types.

---

## Real Test Results (FOXO/KR8 AI MSA Upload on AWS)

These are verified results from uploading the FOXO/KR8 AI Master Software and Services Agreement on the AWS t2.micro instance:

| Metric | Result |
|--------|--------|
| **Text PDF parse time** | < 1 second (reportlab-generated) |
| **OCR PDF parse time** | ~3.5 minutes (WeasyPrint/image-based) |
| **Clauses extracted** | 25 (from MSA) |
| **Obligations extracted** | 19 |
| **SLAs extracted** | Varies by contract content |
| **Auto-link confidence (addendum)** | 0.50 (counterparty + filename pattern + date proximity) |
| **Governance bridge outcome** | Auto-created KR8 AI organization, business relationship, and KPIs from SLAs |

**Auto-link breakdown for addendum:**
```
Addendum -> MSA link:
  counterparty_match:  0.30  (exact match: "FOXO Technologies Inc.")
  type_hierarchy:      0.00  (not a recognized parent-child type pairing)
  filename_pattern:    0.15  ("Addendum" in filename)
  semantic_similarity: 0.05  (some shared terminology)
  same_batch:          0.00  (uploaded separately)
  date_proximity:      ~0.00
  ─────────────────────────
  Total confidence:    0.50  -- Moderate match, pending user review
```

**Governance bridge outcome for MSA:**
1. Organization: Auto-created "KR8 AI Solutions LLC" (type: CUSTOMER)
2. Business Relationship: Created FOXO <-> KR8 AI relationship
3. KPIs: Created from extracted SLAs (uptime, response time, resolution time, etc.)
4. Improvement Points: Created from high-risk clauses (if any)
5. Health Score: Calculated from risk + SLA compliance + obligation health

---

## AI Agents Summary (11 Agent Files, 9 Agents)

| # | Agent | Phase | What It Extracts | Key Output |
|---|-------|-------|-----------------|------------|
| 1 | **Metadata Extraction** | Indexing | Type, parties, dates, value, currency, jurisdiction | Contract record fields |
| 2 | **Risk Detection** | Indexing | 10 risk categories with scores | Risk score (0-100) + level |
| 3 | **Clause Extraction** | Deep Analysis | 17 clause types | Clause records (19-25 per MSA) |
| 4 | **Obligation Tracking** | Deep Analysis | Commitments with deadlines | Obligation records with RAG status (12-19 per contract) |
| 5 | **SLA Extraction** | Deep Analysis | Metrics, targets, penalties | ContractSLA records (6+ for contracts with SLA terms) |
| 6 | **Renewal Monitoring** | Deep Analysis | Auto-renewal, notice periods | Renewal calendar entries |
| 7 | **Schema Extraction** | Deep Analysis | Type-specific structured fields | JSONB schema_data |
| 8 | **Contract Q&A** | On-demand | RAG-powered answers to user questions | Natural language answers grounded in contract text |
| 9 | **Intent Router** | On-demand | Query routing for Ask AI | Routes user questions to right agent |
| 10 | **Regulatory Extraction** | Deep Analysis | Regulatory obligations for regulated industries | Regulatory obligation records |
| 11 | **Industry/Compliance** | Deep Analysis | Regulatory gaps, industry detection | ComplianceGap records + alerts |

**Note:** The 11 agent files include `__init__.py` (agent registration) and `base.py` (shared base classes) alongside the 9 agent implementations.

---

## Key Architecture Decisions

### Why Two Auto-Link Passes?
Pass 1 (indexing) runs before `extracted_text` is stored, so it relies on metadata and filename signals. Pass 2 (deep analysis) runs after the full text is available, enabling richer semantic similarity matching.

### Why Re-Parse in Deep Analysis?
The indexer stores chunks in ChromaDB but does not persist the full `extracted_text` on the contract record. Deep analysis re-parses to get the complete text for AI agents that need the full document context (clause extraction, obligation extraction, etc.).

### Why Separate DB Sessions in Deep Analysis?
Deep analysis runs in its own `async_session_maker()` sessions to prevent FK violations (e.g., from knowledge graph extraction) from poisoning the indexer session and rolling back metadata changes.

### Why Flush Metadata Before Risk?
The metadata flush at step 2.5 ensures that even if risk assessment or subsequent stages fail, the contract's core metadata (counterparty, dates, value, type) is preserved. This is a critical resilience pattern.

### Governance Bridge Fault Tolerance
Each sub-step of the governance bridge (org match, relationship match, KPI creation, improvement points, health score, service portfolio) runs independently. One failure does not block others.
