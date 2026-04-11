# Document Processing Sequence

> Complete step-by-step breakdown of what happens from the moment a contract is uploaded until all processing completes.

*Last updated: April 2026*

---

## Overview

When a user uploads a contract, 3 phases execute automatically:

| Phase | What | Duration | Blocking? |
|-------|------|----------|-----------|
| **1. Upload** | File validation, storage, record creation | < 1 second | Yes (user waits) |
| **2. Indexing** | Parse, chunk, embed, extract metadata, assess risk, detect hierarchy | 30s - 4min | No (background) |
| **3. Deep Analysis** | Clauses, obligations, SLAs, renewals, compliance, governance bridge | 1-2 min | No (background) |

The user gets an immediate upload confirmation. A processing badge shows progress in the UI.

---

## Phase 1: Upload (Immediate)

**Entry Point:** `POST /api/contracts/upload`
**Code:** `backend/app/routers/contracts.py` -> `upload_single_file()`

```
User selects file in browser
         |
         v
    POST /api/contracts/upload (multipart form)
         |
         v
    +-----------------------------+
    | 1. Validate file            |  Reject if not PDF/DOCX/XLSX/PPTX or too large
    | 2. Compute SHA256 hash      |  Detect duplicate uploads
    | 3. Store to disk            |  storage/uploads/{tenant}/{date}/{filename}
    | 4. Create Contract record   |  Status = PENDING, linked to tenant + user
    | 5. Create ProcessingJob     |  Enqueued for background worker
    | 6. Log audit entry          |  CONTRACT_UPLOAD event
    | 7. Return response          |  {id, status: "pending", message: "Processing started"}
    +-----------------------------+
```

**What the user sees:** Contract appears in the list with a "Processing" badge.

**What happens next:** The `ProcessingWorker` (a background loop) picks up the job.

---

## Processing Worker

**Code:** `backend/app/services/processing_worker.py`

The worker runs continuously, claiming jobs from the `ContractProcessingJob` queue. It uses a `Semaphore(2)` to limit concurrency to 2 simultaneous contracts.

```
ProcessingWorker (background loop)
    |
    v
Claim next PENDING job from queue
    |
    v
_process_one_job()
    |
    +--- Phase 2: IndexingService.index_contract()
    |         |
    |         v (on success)
    +--- Phase 3: _run_deep_analysis()
    |         |
    |         v (on completion)
    +--- _check_batch_completion()
              |
              v
         Return job result to queue
```

---

## Phase 2: Indexing Pipeline

**Code:** `backend/app/services/indexer.py` -> `IndexingService.index_contract()`

Each step updates a `ProgressTracker` so the frontend can poll for real-time status.

### Step 1: Document Parsing

**Code:** `backend/app/services/parser.py`

```
Contract file (PDF/DOCX/XLSX/PPTX)
    |
    v
DocumentParser.parse()
    |
    +--- PDF: PyMuPDF (fitz) text extraction
    |         +--- If no text found: OCR fallback via Tesseract
    |
    +--- DOCX: python-docx paragraph extraction
    |
    +--- XLSX/XLS: openpyxl/xlrd cell extraction
    |
    +--- PPTX: python-pptx slide text extraction
    |
    v
Output: raw text string + extracted title
```

**Timing:** < 1 second for text PDFs; ~3.5 minutes for image/scanned PDFs (OCR on t2.micro).

### Step 2: Semantic Chunking

**Code:** `backend/app/services/chunker.py`

```
Raw text (e.g., 20-page MSA)
    |
    v
Split into logical sections using heading detection
    |
    v
~45 chunks, each with:
    - text content
    - section title (inferred)
    - page number(s)
    - chunk index
```

A 20-page MSA typically yields ~45 chunks. Chunks respect section boundaries rather than using arbitrary fixed-size windows.

### Step 3: AI Section Classification

**Code:** `backend/app/services/section_classifier.py` -> `smart_classify_batch()`

Each chunk is classified by GPT-4o into one of 17 semantic types, processed in batches of 10.

```
45 chunks
    |
    v (batches of 10)
GPT-4o classifies each chunk:
    |
    v
+------------------+------------------------------------------+
| Section Type     | Examples                                 |
+------------------+------------------------------------------+
| preamble         | Opening paragraph, recitals              |
| definitions      | Defined terms                            |
| parties          | Party identification                     |
| scope            | Services description, deliverables       |
| terms            | Term and duration                        |
| payment          | Fees, invoicing, payment schedules       |
| confidentiality  | NDA provisions                           |
| liability        | Limitation of liability, indemnification |
| termination      | Termination rights, notice periods       |
| ip               | Intellectual property ownership          |
| compliance       | Regulatory, data protection              |
| governance       | Management structure, escalation         |
| sla              | Service levels, performance metrics      |
| exhibits         | Schedules, appendices                    |
| signatures       | Signature blocks                         |
| general          | Miscellaneous provisions                 |
+------------------+------------------------------------------+
```

Each classification yields: **confidence score**, **section title**, and **semantic tags** (e.g., `"liability,indemnification"`).

Each classified chunk also creates a `Clause` record in the database with a mapped `ClauseType`.

### Step 4: ChromaDB Vector Storage

**Code:** `backend/app/services/vector_store.py`

```
Classified chunks
    |
    v (batches of 100)
Embed via all-MiniLM-L6-v2 (~79MB model, auto-downloaded)
    |
    v
Store in ChromaDB with metadata:
    {
        contract_id, tenant_id, filename,
        section_type, section_title, page_number,
        semantic_tags, uploaded_by, allowed_roles
    }
```

This enables the **Ask AI** feature -- users ask natural language questions and get answers grounded in the actual contract text via RAG (Retrieval-Augmented Generation).

### Step 5: Metadata Extraction (AI Agent)

**Code:** `backend/app/agents/metadata_extraction.py`

```
First 6000 chars + term/expiration sections
    |
    v
GPT-4o extracts:
    +-- contract_type (NDA, MSA, SOW, AMENDMENT, VENDOR, EMPLOYMENT)
    +-- counterparty (legal entity name)
    +-- effective_date (ISO format)
    +-- expiration_date (ISO format)
    +-- contract_value (numeric)
    +-- currency (ISO code: USD, EUR, GBP)
    +-- jurisdiction (governing law)
    +-- parties (list of all party names)
    |
    v
Post-processing:
    +-- LLM counterparty cleaning (gpt-4o-mini strips addresses, validates name)
    +-- Excluded parties filtering (tenant's own name excluded)
    +-- Regex fallback for low-confidence fields
    +-- Contract type mapping ("Master Services Agreement" -> MSA)
    |
    v
Update contract record with extracted metadata
```

**Confidence threshold:** Fields only applied if confidence >= 0.7.

### Step 6: Custom Field Extraction (Conditional)

**Code:** `backend/app/services/custom_field_extraction.py`

If the tenant has custom field definitions configured, those fields are extracted from the contract text and stored as `contract.custom_fields` (JSONB).

### Step 7: Metadata Flush (Critical Checkpoint)

```
await db.flush()   # Persist metadata to DB NOW
```

This is a critical resilience pattern. Even if subsequent AI stages fail (risk, linking, etc.), the contract's core metadata (counterparty, dates, value, type) is preserved.

### Step 8: Risk Assessment (AI Agent)

**Code:** `backend/app/agents/risk_detection.py`

```
Contract text (chunked for long documents)
    |
    v
GPT-4o scores 10 risk categories:
    |
    +-- unlimited_liability      (weight: 15, severity: HIGH)
    +-- missing_limitation       (weight: 15, severity: HIGH)
    +-- broad_indemnification    (weight: 12, severity: HIGH)
    +-- unfavorable_ip           (weight: 12, severity: HIGH)
    +-- weak_termination         (weight: 10, severity: MEDIUM)
    +-- auto_renewal_trap        (weight: 10, severity: MEDIUM)
    +-- one_sided_terms          (weight: 10, severity: HIGH)
    +-- weak_confidentiality     (weight: 8,  severity: MEDIUM)
    +-- regulatory_risk          (weight: 8,  severity: MEDIUM)
    +-- ambiguous_language       (weight: 5,  severity: LOW)
    |
    v
Output: risk_score (0-100) + risk_level (LOW/MEDIUM/HIGH/CRITICAL)
    LOW: 0-25 | MEDIUM: 26-50 | HIGH: 51-75 | CRITICAL: 76-100
```

### Step 9: Contract Reference Extraction (AI Agent)

**Code:** `backend/app/agents/contract_reference_extraction.py`

```
Contract text
    |
    v
GPT-4o identifies:
    +-- Is this a child document? (amendment, exhibit, schedule, SOW)
    +-- What does it reference? ("pursuant to MSA dated...", "Exhibit A to...")
    +-- Parent references with relationship type and party names
    |
    v
Stored in contract.schema_data["_contract_references"]
```

### Step 10: Mark Completed + Hierarchy Detection

**Code:** `backend/app/services/indexer.py` (lines 236-264)

```
Mark contract status: COMPLETED
    |
    v
Gather tenant's 50 most recent completed contracts
    |
    v (if 2+ contracts exist)
    |
hierarchy_detection.detect_hierarchy()
    |
    +--- Stage 1: Smart Document Extraction
    |    SmartDocumentExtractor builds a "document card" for each contract:
    |    - Section-targeted extraction (preamble, ToC, cross-refs, signatures)
    |    - 8000 char budget using key sections, not first-N-chars truncation
    |    - GPT-4o-mini extracts: title, type, parties, dates, parent refs
    |
    +--- Stage 2: Candidate Pair Generation
    |    CandidatePairGenerator reduces N^2 pairs to ~250 likely candidates:
    |    - Cross-reference matching (doc A explicitly mentions doc B)
    |    - Filename number grouping (SOW-001, SOW-002)
    |    - Master-child type matching (MSA paired with SOW/Amendment)
    |    - Party overlap (same counterparty)
    |    - Content hash matching
    |    - Sibling grouping (same type + same parties)
    |
    +--- Stage 3: Pairwise Relationship Classification
    |    RelationshipClassifier uses GPT-4o to classify each pair:
    |    - Batched: 8 pairs per LLM call, 3 concurrent batches
    |    - 5-level taxonomy:
    |      SAME_DOCUMENT, SAME_DOCUMENT_FAMILY, SAME_MASTER_FRAMEWORK,
    |      RELATED_BUT_INDIRECT, UNRELATED
    |    - Each classification: confidence score + reasoning
    |
    +--- Stage 4: Hierarchy Building & Persistence
         HierarchyBuilder creates SuggestedContractLink records:
         - Filters by confidence thresholds (family: 0.50, framework: 0.40)
         - Resolves conflicts (keeps highest confidence per pair)
         - Determines parent/child direction from contract type hierarchy
         - Maps classifier output to LinkType (amendment, sow, exhibit, etc.)
         - Stores with detection_method: "hierarchy_v2" in matching_signals
```

**Result:** SuggestedContractLink records appear in the "Related Docs" tab for review.

---

## Phase 3: Deep Analysis

**Code:** `backend/app/routers/contracts.py` -> `_run_deep_analysis()`

Triggered immediately after indexing succeeds. Runs in its own database session to prevent FK violations from poisoning the indexer session.

### Step 1: Document Re-Parse and Text Storage

```
Re-parse document -> store full extracted_text on contract record
```

The indexer stores chunks in ChromaDB but not the full text. Deep analysis re-parses to get the complete text for AI agents.

### Step 2: Clause Extraction (AI Agent)

**Code:** `backend/app/agents/clause_extraction.py`

```
Full contract text (chunked: 15000 chars with 500 char overlap)
    |
    v
GPT-4o extracts clauses across 30 types:
    |
    Legal/Risk (17):
    +-- INDEMNIFICATION, LIMITATION_OF_LIABILITY, TERMINATION
    +-- CONFIDENTIALITY, INTELLECTUAL_PROPERTY, PAYMENT_TERMS
    +-- WARRANTY, FORCE_MAJEURE, NON_COMPETE, NON_SOLICITATION
    +-- DATA_PROTECTION, DISPUTE_RESOLUTION, ASSIGNMENT
    +-- NOTICE, GOVERNING_LAW, SLA, AUTO_RENEWAL
    |
    IT Service/Outsourcing (13):
    +-- SERVICE_DESCRIPTION, SERVICE_LEVEL, DELIVERABLE
    +-- GOVERNANCE, TRANSITION, CHANGE_MANAGEMENT, SUPPORT
    +-- SECURITY, PERSONNEL, PRICING, RISK_MITIGATION, SCOPE, ACCEPTANCE
    |
    v
Each clause: type, text, section_number, page, risk_level, confidence, key_terms
    |
    v
Deduplicate (by type + first 200 chars), keep highest confidence
    |
    v
Store in Clause table (clean up old clauses for this contract first)
```

**Typical yield:** 19-25 clauses for a 20-page MSA.

### Step 3: Obligation Extraction (AI Agent)

**Code:** `backend/app/agents/obligation_tracking.py`

```
Contract text (up to 20000 chars)
    |
    v
GPT-4o extracts obligations:
    |
    For each obligation:
    +-- description (what must be done)
    +-- obligation_type (PAYMENT, DELIVERY, REPORTING, COMPLIANCE, etc.)
    +-- obligated_party (who must do it)
    +-- beneficiary_party (who benefits)
    +-- deadline_type (FIXED, RECURRING, RELATIVE, ONGOING)
    +-- deadline_value / deadline_date
    +-- recurrence_pattern (monthly, quarterly, etc.)
    +-- consequences (what happens on breach)
    +-- source_quote (exact contract text, up to 500 chars)
    +-- confidence score
    |
    v
Store in Obligation table with:
    status: PENDING -> IN_PROGRESS -> COMPLETED (or OVERDUE)
    rag_status: GREEN / AMBER / RED
    priority: 1 (highest) to 5 (lowest)
    is_critical: true for penalty-triggering obligations
```

**Typical yield:** 12-19 obligations per contract.

### Step 4: SLA Extraction (AI Agent)

**Code:** `backend/app/agents/sla_extraction.py`

```
Contract text (smart section detection for docs > 100K chars)
    |
    v
GPT-4o extracts SLAs:
    |
    For each SLA:
    +-- sla_name ("System Uptime", "P1 Response Time")
    +-- metric_type (UPTIME_PERCENTAGE, RESPONSE_TIME, etc.)
    +-- target_value (99.9, 15, 4)
    +-- target_operator (>=, <=)
    +-- warning_threshold
    +-- severity (CRITICAL, HIGH, MEDIUM, LOW)
    +-- penalty details (type, value, cap)
    +-- measurement_period (monthly, quarterly)
    |
    v
For Excel files: structured extraction via excel_sla_parser
    |
    v
Reclassify uncategorized chunks containing SLA patterns
    |
    v
Store in ContractSLA table
```

**Typical yield:** 6+ SLAs for contracts with SLA terms.

### Step 5: Renewal Analysis (AI Agent)

**Code:** `backend/app/agents/renewal_monitoring.py`

```
Contract text
    |
    v
GPT-4o extracts:
    +-- has_auto_renewal: true/false
    +-- auto_renewal_term_months: 12
    +-- notice_period_days: 90
    +-- initial_term_months: 36
    +-- termination_for_convenience: true/false
    +-- termination_notice_days: 60
    +-- renewal_clause_text: exact clause text
    |
    v
Calculate:
    notice_deadline = expiration_date - notice_period_days
    days_until_expiration
    urgency_level (IMMEDIATE / SOON / UPCOMING / FUTURE)
    |
    v
Update contract.renewal_terms -> feeds Renewals page
```

### Step 6: Schema-Based Extraction (AI Agent)

**Code:** `backend/app/schemas/extractor.py`

```
Contract type known (e.g., MSA)
    |
    v
Look up schema from SchemaRegistry (15 contract types, 1235 fields)
    |
    v
GPT-4o extracts type-specific structured fields:
    |
    MSA: pricing model, payment terms, insurance, audit rights, governing law
    SOW: deliverables, milestones, team composition, pricing breakdown
    NDA: term, scope, exclusions, permitted disclosures
    ... (15 types total)
    |
    v
Store as JSONB in contract.schema_data
    |
    v
Sync to relational tables via schema_sync.sync_schema_to_db()
```

### Step 7: Contract Type Fallback Classification

If `contract.contract_type` is still NULL (metadata extraction couldn't determine it):

```
GPT-4o-mini classifies into:
    NDA (confidentiality focus)
    MSA (master/framework/consulting)
    SOW (work order, PO)
    AMENDMENT (modifies existing)
    VENDOR_AGREEMENT (vendor terms)
    EMPLOYMENT_CONTRACT (employment)
```

### Step 8: Focused Relationship Extraction Retry

If no parent references were found in Phase 2 Step 9:

```
Second AI call specifically looking for:
    "pursuant to", "This Amendment modifies",
    "under the terms of", "Exhibit A to", etc.
    |
    v
Extract:
    is_child_document: true/false
    document_role: amendment | schedule | exhibit | sow | standalone
    parent_references with relationship type and party names
```

### Step 9: Post-Reference Corrections

```
Fix 1: Child documents misclassified as MSA -> reclassify to SOW
    (exhibits, schedules, attachments wrongly typed as master agreements)

Fix 2: Counterparty looks like filename fallback -> use parent reference party names
```

### Step 10: Hierarchy Detection (Second Pass)

Same 4-stage pipeline as Phase 2 Step 10, but now with enriched data from deep analysis (extracted text, clauses, obligations). Uses `batch_id: "deep_analysis_{contract_id}"`.

### Step 11: Compliance Analysis

**Code:** `backend/app/services/industry_detector.py`, `compliance_gap_detector.py`

```
Contract text
    |
    v
Stage 1: Industry Detection
    IndustryDetector.detect_industry()
    -> FINANCIAL, HEALTHCARE, ENERGY, TECHNOLOGY, etc.
    |
    v
Stage 2: Compliance Gap Analysis
    ComplianceGapDetector.check_compliance()
    -> Check against industry-specific requirements (HIPAA, SOX, GDPR, etc.)
    -> Compute compliance score
    |
    v
Stage 3: Alert Creation
    Create compliance alerts for CRITICAL and HIGH gaps
    |
    v
Stage 4: Regulatory Obligations (regulated industries only)
    regulatory_extraction agent extracts framework-specific obligations
    -> Store in RegulatoryObligation table
```

### Step 12: Governance Bridge (Final Step)

**Code:** `backend/app/services/governance_bridge.py`

```
Contract with all extracted data
    |
    v
GovernanceBridgeService.bridge_contract_to_governance()
    |
    +--- Automation 1: Organization Match/Create
    |    Counterparty name -> exact match -> fuzzy match -> auto-create
    |    Type inferred: MSA/SOW -> CUSTOMER, VENDOR_AGREEMENT -> VENDOR, NDA -> PARTNER
    |
    +--- Automation 2: Business Relationship Match/Create
    |    Find or create relationship between tenant org and counterparty org
    |    Type inferred from org type (Customer, Supplier, Partner)
    |
    +--- Automation 3: SLA -> KPI Conversion
    |    Map SLA metrics to KPI categories:
    |    Uptime/Availability -> Service Delivery (Percentage)
    |    Response/Resolution Time -> Timeliness (Hours)
    |    Error Rate -> Quality (Percentage)
    |    Compliance Rate -> Compliance (Percentage)
    |
    +--- Automation 4: Risk -> Improvement Points
    |    HIGH/CRITICAL risk clauses -> ImprovementPoint records
    |    8 clause types mapped to human-readable labels
    |
    +--- Automation 5: Health Score Calculation
    |    Composite score (0-100):
    |    Risk Health (30%):       100 - risk_score
    |    SLA Compliance (40%):    avg(current_compliance_rate)
    |    Obligation Health (30%): weighted by RAG status
    |
    +--- Automation 6: SOW Service Linking
         SOW service descriptions -> match against ServicePortfolio
         -> Create RelationshipService links
```

Each automation is independent and fault-tolerant. One failure does not block others. Employment contracts are skipped (no B2B governance).

---

## Batch Completion

**Code:** `backend/app/services/processing_worker.py` -> `_check_batch_completion()`

After each job completes, the worker checks if the entire batch is done.

```
All jobs in batch complete?
    |
    v (yes, and 2+ contracts in batch)
    |
Stage 1: Batch Hierarchy Detection
    Run hierarchy detection across ALL contracts in the batch
    -> Additional cross-batch relationship suggestions
    |
    v
Stage 2: Auto-Approve High-Confidence Links
    auto_link_detector.auto_approve_batch_links()
    -> Auto-approve links above confidence threshold
```

---

## End-to-End Sequence Diagram

```
USER                    FRONTEND              BACKEND                        AI / DATA
 |                         |                     |                              |
 |-- Select file --------->|                     |                              |
 |                         |-- POST /upload ---->|                              |
 |                         |                     |-- Validate file              |
 |                         |                     |-- Store to disk              |
 |                         |                     |-- Create Contract (PENDING)  |
 |                         |                     |-- Enqueue ProcessingJob      |
 |                         |<--- {id, pending} --|                              |
 |<-- "Processing..." -----|                     |                              |
 |                         |                     |                              |
 |   (background)          |                     |                              |
 |                         |                     |== INDEXING PIPELINE ======== |
 |                         |                     |-- Parse PDF/DOCX ---------->| extract text
 |                         |                     |-- Chunk document ---------->| 45 chunks
 |                         |                     |-- Classify sections ------->| GPT-4o: 17 types
 |                         |                     |-- Embed + store ----------->| ChromaDB
 |                         |                     |-- Extract metadata -------->| GPT-4o: parties, dates
 |                         |                     |-- Flush metadata to DB      |
 |                         |                     |-- Assess risk ------------->| GPT-4o: 10 categories
 |                         |                     |-- Extract references ------>| GPT-4o: parent refs
 |                         |                     |-- Mark COMPLETED            |
 |                         |                     |-- Hierarchy detection ----->| GPT-4o-mini + GPT-4o
 |                         |                     |   (extract, pair, classify, |   4-stage pipeline
 |                         |                     |    build suggestions)       |
 |                         |                     |                              |
 |                         |                     |== DEEP ANALYSIS =========== |
 |                         |                     |-- Re-parse full text         |
 |                         |                     |-- Extract clauses --------->| GPT-4o: 30 types
 |                         |                     |-- Extract obligations ----->| GPT-4o: deadlines
 |                         |                     |-- Extract SLAs ------------>| GPT-4o: metrics
 |                         |                     |-- Analyze renewals -------->| GPT-4o: terms
 |                         |                     |-- Schema extraction ------->| GPT-4o: 1235 fields
 |                         |                     |-- Classify type (fallback)  |
 |                         |                     |-- Retry relationship refs   |
 |                         |                     |-- Post-ref corrections      |
 |                         |                     |-- Hierarchy detection (v2)  |
 |                         |                     |-- Industry detection ------>| GPT-4o
 |                         |                     |-- Compliance gaps --------->| rule engine
 |                         |                     |-- Regulatory obligations -->| GPT-4o
 |                         |                     |-- Governance bridge         |
 |                         |                     |   (org, relationship, KPIs, |
 |                         |                     |    improvements, health)    |
 |                         |                     |                              |
 |                         |                     |== COMPLETE ================ |
 |                         |-- Poll status ----->|                              |
 |                         |<-- {completed} -----|                              |
 |<-- Contract ready ------|                     |                              |
```

---

## Processing Times (Verified on AWS t2.micro)

### Text PDF (20-page MSA)

| Stage | Duration |
|-------|----------|
| Upload + record creation | < 1s |
| Document parsing | < 1s |
| Chunking + classification | ~15s |
| ChromaDB storage | ~5s |
| Metadata extraction | ~10s |
| Risk assessment | ~15s |
| Reference extraction | ~5s |
| Hierarchy detection | ~10s |
| **Indexing total** | **~60s** |
| Clause extraction | ~30s |
| Obligation extraction | ~20s |
| SLA extraction | ~10s |
| Renewal analysis | ~5s |
| Schema extraction | ~15s |
| Compliance analysis | ~15s |
| Governance bridge | ~5s |
| **Deep analysis total** | **~2 min** |
| **End-to-end total** | **~3 min** |

### Image/Scanned PDF (OCR required)

| Stage | Duration |
|-------|----------|
| OCR parsing (Tesseract) | ~3.5 min |
| Everything else | same as above |
| **End-to-end total** | **~6 min** |

### Batch Upload (3 related documents)

Processes up to 2 contracts concurrently via `Semaphore(2)`. After all complete, batch hierarchy detection runs across the full set.

**Expected total:** 8-12 minutes depending on PDF types.

---

## What Gets Created

After processing completes, these records exist in the database:

| Record Type | Typical Count | Source |
|-------------|---------------|--------|
| Contract (metadata) | 1 | Metadata extraction |
| Clauses | 19-25 | Clause extraction |
| Obligations | 12-19 | Obligation extraction |
| SLAs | 6+ | SLA extraction |
| Renewal terms | 1 | Renewal analysis |
| Schema data (JSONB) | 1 | Schema extraction |
| ChromaDB embeddings | ~45 | Vector indexing |
| Suggested links | 0-10 | Hierarchy detection |
| Compliance gaps | 0-5 | Compliance analysis |
| Organization | 0-1 | Governance bridge |
| Business relationship | 0-1 | Governance bridge |
| KPIs | 0-6 | Governance bridge (from SLAs) |
| Improvement points | 0-3 | Governance bridge (from risks) |
| Health score | 1 | Governance bridge |

---

## Key Architecture Decisions

### Why a processing queue instead of inline async tasks?

The `ProcessingWorker` with `ContractProcessingJob` provides:
- **Concurrency control** via Semaphore (2 max)
- **Retry capability** for failed jobs
- **Batch tracking** (know when all uploads in a batch are done)
- **Progress visibility** (frontend polls job status)

### Why two hierarchy detection passes?

Pass 1 (indexing) runs with basic metadata. Pass 2 (deep analysis) runs with the full extracted text, clauses, and reference data -- enabling richer classification.

### Why flush metadata before risk assessment?

The `db.flush()` after metadata extraction ensures that even if risk assessment, hierarchy detection, or any subsequent stage fails, the contract's core metadata (counterparty, dates, value, type) is preserved in the database.

### Why separate sessions for deep analysis?

Deep analysis runs in its own `async_session_maker()` to prevent FK violations (e.g., from knowledge graph extraction) from rolling back the indexer session's metadata changes.

### Why is governance bridge the last step?

It depends on everything: counterparty (metadata), SLAs (extraction), risk level (assessment), and clauses (extraction). Running it last ensures all data is available.

---

## Code File Reference

| Step | File |
|------|------|
| Upload endpoint | `backend/app/routers/contracts.py` |
| Processing worker | `backend/app/services/processing_worker.py` |
| Indexing pipeline | `backend/app/services/indexer.py` |
| Document parser | `backend/app/services/parser.py` |
| Semantic chunker | `backend/app/services/chunker.py` |
| Section classifier | `backend/app/services/section_classifier.py` |
| Vector store | `backend/app/services/vector_store.py` |
| Progress tracker | `backend/app/services/progress_tracker.py` |
| Metadata agent | `backend/app/agents/metadata_extraction.py` |
| Risk agent | `backend/app/agents/risk_detection.py` |
| Reference agent | `backend/app/agents/contract_reference_extraction.py` |
| Hierarchy detection | `backend/app/services/hierarchy_detection/` |
| Deep analysis | `backend/app/routers/contracts.py` (`_run_deep_analysis`) |
| Clause agent | `backend/app/agents/clause_extraction.py` |
| Obligation agent | `backend/app/agents/obligation_tracking.py` |
| SLA agent | `backend/app/agents/sla_extraction.py` |
| Renewal agent | `backend/app/agents/renewal_monitoring.py` |
| Schema extractor | `backend/app/schemas/extractor.py` |
| Compliance detector | `backend/app/services/compliance_gap_detector.py` |
| Industry detector | `backend/app/services/industry_detector.py` |
| Regulatory agent | `backend/app/agents/regulatory_extraction.py` |
| Governance bridge | `backend/app/services/governance_bridge.py` |
