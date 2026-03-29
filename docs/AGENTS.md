# Agentic AI Architecture

This document describes the multi-agent AI system powering the CLM platform's contract intelligence capabilities.

## Overview

The CLM platform uses a **multi-agent architecture** where specialized AI agents handle distinct contract analysis tasks. All agents are powered by **OpenAI GPT-4o** and orchestrated through a central service with **Langfuse** observability.

Key characteristics:

- **9 specialized agents** registered at startup via `register_all_agents()` plus the Intent Router
- **Intent-based routing** via LLM classification in the orchestrator and structured-query detection in the Intent Router
- **Dual invocation paths**: interactive Q&A and batch pipeline extraction
- **RAG retrieval** using ChromaDB vector search with RBAC filtering
- **Structured JSON output** parsed from LLM responses with fallback extraction
- **Automatic tracing** of all LLM calls via Langfuse OpenTelemetry integration
- **Governance Bridge** automation service runs after deep analysis to populate relationship governance data

## Architecture Diagram

```
                                    CLM Agent Architecture
                                    =====================

  ┌─────────────┐
  │ User/Upload │
  └──────┬──────┘
         │
         ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │                         FastAPI Application                      │
  │                                                                  │
  │  ┌──────────────────┐         ┌────────────────────────────┐    │
  │  │  Query Router     │         │   Contracts Router          │    │
  │  │  (Interactive)    │         │   (Upload Pipeline)         │    │
  │  │                   │         │                             │    │
  │  │  POST /query      │         │  POST /contracts (upload)   │    │
  │  │  POST /analyze    │         │  POST /contracts/{id}/      │    │
  │  └────────┬──────────┘         │        process              │    │
  │           │                    └─────────────┬───────────────┘    │
  │           │                                  │                    │
  │           ▼                                  ▼                    │
  │  ┌──────────────────────────────────────────────────────────┐    │
  │  │                  Orchestrator Service                     │    │
  │  │                  (Singleton)                              │    │
  │  │                                                          │    │
  │  │  ┌──────────────────┐    ┌────────────────────────────┐  │    │
  │  │  │ Intent Classifier │    │     Agent Registry          │  │    │
  │  │  │ (LLM, temp=0.0)  │───▶│                            │  │    │
  │  │  └──────────────────┘    │  metadata_extraction       │  │    │
  │  │                          │  clause_extraction          │  │    │
  │  │  ┌──────────────────┐    │  obligation_tracking        │  │    │
  │  │  │ route_request()  │    │  risk_detection             │  │    │
  │  │  │ (retry: 3x)     │    │  renewal_monitoring         │  │    │
  │  │  └──────────────────┘    │  contract_qa (default)      │  │    │
  │  │                          │  sla_extraction             │  │    │
  │  │  ┌──────────────────┐    │  schema_extractor_*         │  │    │
  │  │  │ invoke_agent()   │    │  intent_router              │  │    │
  │  │  │ (direct call)    │    └────────────────────────────┘  │    │
  │  │  └──────────────────┘                                    │    │
  │  └───────────────────────────┬──────────────────────────────┘    │
  │                              │                                    │
  │                              ▼                                    │
  │            ┌─────────────────────────────────┐                   │
  │            │    OpenAI GPT-4o (via Langfuse   │                   │
  │            │    LangfuseAsyncOpenAI wrapper)   │                   │
  │            └─────────────────────────────────┘                   │
  │                              │                                    │
  │               ┌──────────────┼──────────────┐                    │
  │               ▼              ▼              ▼                     │
  │          ┌─────────┐  ┌──────────┐  ┌───────────┐               │
  │          │ChromaDB  │  │PostgreSQL│  │ Langfuse   │               │
  │          │(vectors) │  │(entities)│  │(traces)    │               │
  │          └─────────┘  └──────────┘  └───────────┘               │
  └──────────────────────────────────────────────────────────────────┘
```

## Core Components

Shared infrastructure defined in `backend/app/agents/base.py`.

### AgentConfig

Dataclass holding the configuration for each agent:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | required | Unique agent identifier |
| `description` | `str` | required | Description used for intent routing |
| `system_prompt` | `str` | required | System prompt sent to the LLM |
| `model_id` | `str` | `settings.openai_model` | OpenAI model ID |
| `temperature` | `float` | `0.1` | LLM temperature |
| `max_tokens` | `int` | `2000` | Maximum response tokens |
| `streaming` | `bool` | `False` | Reserved for streaming support |
| `tools` | `list` | `[]` | Tool definitions for function calling |

### ContractSearchTool

ChromaDB vector search tool used for RAG context injection. Supports:

- **RBAC filtering** via `user_id` and `user_role` parameters
- **Contract scoping** via optional `contract_id`
- **Configurable result count** (`n_results`, default 10)
- **Formatted context output** with contract ID, section, page, and relevance score
- **OpenAI function tool definition** for agent tool-use integration

### Response Models

- **`SourceCitation`** - Pydantic model for source references: contract_id, filename, section_number, page range, relevance_score, excerpt
- **`AgentOutput`** - Structured agent output: response text, confidence score, source citations, follow-up questions, metadata

### Utility Functions

| Function | Purpose |
|----------|---------|
| `run_agent()` | Core execution function. Sends system prompt + user message to OpenAI, with Langfuse tracing via `@observe` decorator. Supports Langfuse prompt management with config fallback. |
| `inject_context()` | RAG context injection. Uses `ContractSearchTool` to retrieve relevant chunks, truncates to `max_context_length` (default 8000 chars), formats into a structured prompt. |
| `extract_json_from_response()` | Parses JSON from LLM responses. Tries markdown code fences first, then raw JSON object detection. |
| `extract_confidence()` | Extracts confidence scores from response text using regex patterns (e.g., "confidence: 85%"). |

## Orchestrator Service

Defined in `backend/app/services/orchestrator.py`. The `OrchestratorService` is a **singleton** that manages agent registration, intent classification, and request routing.

### Agent Registry

Agents register themselves at startup. The registry maps agent names to `AgentConfig` objects:

```python
# In main.py lifespan handler:
initialize_default_agents()   # Registers defaults in orchestrator
register_all_agents()         # Registers all 9 specialized agents
```

### Intent Classification

The `_classify_intent()` method routes user queries to the appropriate agent:

1. Builds a classification prompt listing all registered agents and their descriptions
2. Calls GPT-4o with `temperature=0.0` and `max_tokens=50`
3. Validates the returned agent name exists in the registry
4. Falls back to `contract_qa` (the default agent) if classification fails

### Request Routing

**`route_request()`** - Auto-routes requests with retry logic:
- Classifies intent to select the agent
- Creates a Langfuse trace with `user_id`, `session_id`, `contract_id`
- Calls OpenAI with the agent's configuration
- Retries up to 3 times on `RateLimitError` or `APIError` (exponential backoff: 4-60s)
- Returns `AgentResponseModel` with response, agent_name, confidence, sources, session_id

**`invoke_agent()`** - Direct agent invocation (bypasses intent classification):
- Used when the caller already knows which agent to use
- Creates its own Langfuse trace
- Supports optional context dict injection

### Health Check

The `health_check()` method reports:
- OpenAI API connectivity
- Langfuse connectivity (if configured)
- Number of registered agents

## Agent Details

### 1. Metadata Extraction Agent (SK-001)

**File:** `backend/app/agents/metadata_extraction.py`
**Agent ID:** `metadata_extraction`
**Temperature:** 0.0 | **Max Tokens:** 1500

**Purpose:** Extracts structured contract metadata from document text.

**Extracted Fields:**
- `contract_type` - NDA, MSA, SOW, AMENDMENT, VENDOR, EMPLOYMENT, OTHER
- `counterparty` - Legal entity name of the other contracting party
- `effective_date` - Contract start date (ISO format)
- `expiration_date` - Contract end date (ISO format)
- `contract_value` - Monetary value (numeric)
- `currency` - Currency code (USD, EUR, GBP, etc.)
- `jurisdiction` - Governing law jurisdiction
- `parties` - List of all party names

**Pydantic Models:**
- `MetadataField` - Single field with value, confidence (0.0-1.0), and raw_text
- `ExtractedMetadata` - All fields plus parties list and overall_confidence

**Key Features:**
- **Smart text preparation** - Includes first 6000 chars (preamble) plus term/expiration sections found via regex
- **LLM counterparty cleaning** - Uses `gpt-4o-mini` to strip addresses and validate entity names
- **Filename fallback** - Extracts counterparty from filename patterns (e.g., `NDA_CompanyA_CompanyB.pdf`)
- **Regex fallback** - `extract_metadata_regex()` provides rule-based extraction when AI confidence is below 0.6
- **Merged extraction** - `extract_metadata_with_fallback()` merges AI and regex results, preferring AI when confident
- **Confidence threshold** - Fields are only applied to the contract if confidence >= 0.7

**Key Functions:**
| Function | Description |
|----------|-------------|
| `extract_metadata()` | AI-based extraction via orchestrator |
| `extract_metadata_regex()` | Regex-based fallback extraction |
| `extract_metadata_with_fallback()` | Merges AI + regex results |
| `update_contract_metadata()` | Applies extracted metadata to Contract model |
| `register_metadata_extraction_agent()` | Registers with orchestrator |

---

### 2. Clause Extraction Agent (SK-002)

**File:** `backend/app/agents/clause_extraction.py`
**Agent ID:** `clause_extraction`
**Temperature:** 0.1 | **Max Tokens:** 4000

**Purpose:** Identifies and extracts specific clause types from contract text with risk assessment.

**30 Supported Clause Types:**

*Legal/Risk (17):*
INDEMNIFICATION, LIMITATION_OF_LIABILITY, TERMINATION, CONFIDENTIALITY, INTELLECTUAL_PROPERTY, PAYMENT_TERMS, WARRANTY, FORCE_MAJEURE, NON_COMPETE, NON_SOLICITATION, DATA_PROTECTION, DISPUTE_RESOLUTION, ASSIGNMENT, NOTICE, GOVERNING_LAW, SLA, AUTO_RENEWAL

*IT Service/Outsourcing (13):*
SERVICE_DESCRIPTION, SERVICE_LEVEL, DELIVERABLE, GOVERNANCE, TRANSITION, CHANGE_MANAGEMENT, SUPPORT, SECURITY, PERSONNEL, PRICING, RISK_MITIGATION, SCOPE, ACCEPTANCE

**Pydantic Models:**
- `ExtractedClause` - clause_type, text, section_number, page_number, risk_level, confidence, key_terms, notes
- `ClauseExtractionResult` - extracted_clauses list, missing_clauses list, overall_confidence

**Key Features:**
- **Chunked extraction** - Splits long documents into overlapping chunks (15000 chars, 500 char overlap)
- **Deduplication** - Removes duplicate clauses by type + first 200 chars of text, keeping highest confidence
- **Missing clause detection** - Reports expected standard clauses not found in the contract
- **Risk assessment** - Each clause rated LOW/MEDIUM/HIGH based on favorability
- **Text truncation** - Clause text capped at 2000 characters

**Key Functions:**
| Function | Description |
|----------|-------------|
| `extract_clauses()` | Main extraction with chunking support |
| `store_extracted_clauses()` | Persists clauses to PostgreSQL |
| `register_clause_extraction_agent()` | Registers with orchestrator |

---

### 3. Obligation Tracking Agent (SK-003)

**File:** `backend/app/agents/obligation_tracking.py`
**Agent ID:** `obligation_tracking`
**Temperature:** 0.1 | **Max Tokens:** 4000

**Purpose:** Extracts contractual obligations with responsible parties, deadlines, and consequences.

**7 Obligation Types:**
| Type | Description |
|------|-------------|
| PAYMENT | Monetary payment obligations |
| DELIVERY | Delivery of goods or services |
| REPORTING | Reporting or notification requirements |
| COMPLIANCE | Regulatory or contractual compliance |
| NOTIFICATION | Notice requirements |
| PERFORMANCE | Performance or service obligations |
| OTHER | Other contractual obligations |

**4 Deadline Types:**
| Type | Description |
|------|-------------|
| FIXED | Specific date (e.g., January 1, 2025) |
| RECURRING | Repeating schedule (e.g., monthly, quarterly) |
| RELATIVE | Relative to an event (e.g., 30 days after signing) |
| ONGOING | Continuous obligation with no specific deadline |

**Pydantic Models:**
- `ExtractedObligation` - description, obligation_type, obligated_party, beneficiary_party, deadline_type, deadline_value, deadline_date, recurrence_pattern, triggering_condition, consequences, section_number, source_quote, confidence
- `ObligationExtractionResult` - obligations list, party_summary (count per party), overall_confidence

**Key Features:**
- **Party tracking** - Identifies both obligated party and beneficiary for each obligation
- **Source quotes** - Captures exact contract text (up to 500 chars) for traceability
- **Party summary** - Aggregates obligation count per party
- **Text limit** - Processes up to 20000 characters of contract text

**Key Functions:**
| Function | Description |
|----------|-------------|
| `extract_obligations()` | Main extraction via orchestrator |
| `store_extracted_obligations()` | Persists obligations to PostgreSQL |
| `register_obligation_tracking_agent()` | Registers with orchestrator |

---

### 4. Risk Detection Agent (SK-004)

**File:** `backend/app/agents/risk_detection.py`
**Agent ID:** `risk_detection`
**Temperature:** 0.1 | **Max Tokens:** 3000

**Purpose:** Identifies contract risks and calculates an overall risk score with actionable recommendations.

**10 Risk Categories (with weights):**

| Category | Weight | Severity | Description |
|----------|--------|----------|-------------|
| `unlimited_liability` | 15 | HIGH | No cap on liability exposure |
| `missing_limitation` | 15 | HIGH | Missing limitation of liability clause |
| `broad_indemnification` | 12 | HIGH | Overly broad indemnification obligations |
| `unfavorable_ip` | 12 | HIGH | Unfavorable intellectual property terms |
| `weak_termination` | 10 | MEDIUM | Limited or no termination for convenience |
| `auto_renewal_trap` | 10 | MEDIUM | Auto-renewal with difficult opt-out |
| `one_sided_terms` | 10 | HIGH | Significantly one-sided contractual terms |
| `weak_confidentiality` | 8 | MEDIUM | Inadequate confidentiality protections |
| `regulatory_risk` | 8 | MEDIUM | Potential regulatory compliance issues |
| `ambiguous_language` | 5 | LOW | Ambiguous or unclear language in key provisions |

**Score Thresholds:**
| Level | Score Range |
|-------|-------------|
| LOW | 0-25 |
| MEDIUM | 26-50 |
| HIGH | 51-75 |
| CRITICAL | 76-100 |

**Pydantic Models:**
- `RiskFactor` - category, description, severity, score (0-100), clause_reference, recommendation, confidence
- `RiskAssessmentResult` - risk_factors list, overall_score, risk_level, summary, top_recommendations, overall_confidence

**Key Functions:**
| Function | Description |
|----------|-------------|
| `assess_risk()` | Main risk assessment via orchestrator |
| `update_contract_risk()` | Updates Contract model with risk_score and risk_level |
| `register_risk_detection_agent()` | Registers with orchestrator |

---

### 5. Renewal Monitoring Agent (SK-005)

**File:** `backend/app/agents/renewal_monitoring.py`
**Agent ID:** `renewal_monitoring`
**Temperature:** 0.0 | **Max Tokens:** 1500

**Purpose:** Extracts renewal terms and calculates notice deadlines with urgency assessment.

**Pydantic Models:**
- `RenewalTerms` - has_auto_renewal, auto_renewal_term_months, notice_period_days, notice_deadline, expiration_date, effective_date, initial_term_months, termination_for_convenience, termination_notice_days, renewal_clause_text, confidence
- `RenewalMonitoringResult` - terms, days_until_expiration, days_until_notice_deadline, urgency_level, action_required, recommendations

**Urgency Levels:**
| Level | Condition |
|-------|-----------|
| IMMEDIATE | Notice deadline passed or < 7 days away |
| SOON | Notice deadline < 30 days away |
| UPCOMING | Notice deadline < 90 days away |
| FUTURE | Notice deadline >= 90 days away |

**Key Features:**
- **Deadline calculation** - Computes notice deadline from expiration date minus notice period
- **Urgency assessment** - Categorizes contracts by renewal urgency
- **Actionable recommendations** - Generates specific recommendations (e.g., "URGENT: Review contract within N days")
- **Termination analysis** - Detects termination for convenience rights

**Key Functions:**
| Function | Description |
|----------|-------------|
| `analyze_renewal_terms()` | Main renewal analysis via orchestrator |
| `update_contract_renewal()` | Updates Contract model with renewal fields |
| `register_renewal_monitoring_agent()` | Registers with orchestrator |

---

### 6. Contract Q&A Agent (SK-006)

**File:** `backend/app/agents/contract_qa.py`
**Agent ID:** `contract_qa`
**Temperature:** 0.2 | **Max Tokens:** 2000

**Purpose:** RAG-based question answering over the contract corpus. This is the **default agent** for the orchestrator.

**Pydantic Models:**
- `QAResponse` - answer, confidence (0.0-1.0), sources (list of SourceCitation), follow_up_questions, clarification_needed, clarification_prompt

**Key Features:**
- **RAG pipeline** - Uses `ContractSearchTool` to retrieve relevant chunks from ChromaDB, then injects them as context
- **RBAC-aware search** - Search results filtered by user_id and user_role
- **Source citations** - Top 5 search results included as SourceCitation objects with relevance scores
- **Follow-up extraction** - Parses suggested follow-up questions from LLM response using regex
- **Clarification detection** - Detects when the LLM asks for clarification (phrases like "could you clarify", "please specify")
- **Confidence estimation** - Estimates confidence from response indicators:
  - High (0.9): "according to section", "the contract states"
  - Medium (0.6): neutral response
  - Low (0.3): "not found", "cannot determine", "unclear"
- **Suggested questions** - `suggest_questions()` provides default starter questions for any contract

**Key Functions:**
| Function | Description |
|----------|-------------|
| `ask_question()` | Main Q&A function with RAG retrieval |
| `suggest_questions()` | Returns default suggested questions |
| `register_contract_qa_agent()` | Registers with orchestrator |

---

### 7. SLA Extraction Agent (SK-007)

**File:** `backend/app/agents/sla_extraction.py`
**Agent ID:** `sla_extraction`
**Temperature:** 0.1 | **Max Tokens:** 4000

**Purpose:** Extracts Service Level Agreements including metrics, targets, warning thresholds, and penalty descriptions.

**9 Metric Types:**
UPTIME_PERCENTAGE, RESPONSE_TIME, RESOLUTION_TIME, DELIVERY_TIME, THROUGHPUT, ERROR_RATE, AVAILABILITY, QUALITY_SCORE, CUSTOM

**7 Measurement Units:**
PERCENTAGE, HOURS, MINUTES, DAYS, BUSINESS_DAYS, COUNT, SCORE

**Pydantic Models:**
- `ExtractedSLA` - sla_name, sla_description, metric_type, metric_unit, target_value, target_operator, warning_threshold, severity, has_penalty, penalty_type, penalty_value, penalty_description, max_penalty_cap, measurement_period, section_reference, source_text, confidence
- `SLAExtractionResult` - slas list, has_sla_section, has_penalty_mechanism, overall_confidence

**Key Features:**
- **Smart section detection** - For documents over 100K chars, uses keyword search ("service level", "sla", "uptime", "penalty", etc.) to find relevant chunks
- **Data preprocessing** - `preprocess_sla_data()` handles common AI response format issues (string-to-float conversion, range clamping, missing fields)
- **Penalty tracking** - Captures penalty type (fixed, percentage, credit, tiered), value, and caps
- **Severity classification** - CRITICAL, HIGH, MEDIUM, LOW based on business impact
- **Direct invocation** - Uses `orchestrator.invoke_agent()` instead of `route_request()` (bypasses intent classification)

**Key Functions:**
| Function | Description |
|----------|-------------|
| `extract_slas()` | Main SLA extraction |
| `store_extracted_slas()` | Persists SLAs to PostgreSQL |
| `register_sla_extraction_agent()` | Registers with orchestrator |

---

### 8. Intent Router (SK-008)

**File:** `backend/app/agents/intent_router.py`
**Agent ID:** `intent_router`
**Temperature:** 0.3 (for LLM enhancement) | **Max Tokens:** 2000

**Purpose:** Routes user questions to either structured database queries (PostgreSQL) or document-based RAG retrieval (ChromaDB). Generates rich LLM-powered visualizations for structured query results.

The Intent Router is not a standard orchestrator agent — it is invoked by the Contract Q&A agent (`ask_question()`) before the Q&A pipeline runs. If a question matches a structured intent, it bypasses RAG entirely and returns data with chart visualizations.

**5 Structured Intents:**

| Intent | Keywords | Data Source |
|--------|----------|-------------|
| `renewals` | renewal, expiring, auto-renewal, notice period | Contracts (expiration dates, notice periods) |
| `obligations` | obligation, deadline, overdue, compliance | Obligations (deadlines, status, parties) |
| `risk` | risk summary, risk score, high risk | Contracts (risk_score, risk_level) |
| `portfolio` | how many contracts, total value, overview | Contracts (aggregate stats) |
| `sla` | sla performance, sla breach, service level | KG SLA Metric entities |

**4 Visualization Types:**

| Chart Type | Format | Use Case |
|------------|--------|----------|
| `stat_cards` | KPI cards with labels and colors | Always first — headline numbers |
| `pie` | Donut chart segments | Proportional breakdowns (2-7 segments) |
| `bar` | Horizontal bars | Comparisons, rankings |
| `table` | Columns + rows | Detailed item listings (5-8 rows max) |

**Key Features:**
- **Keyword-based detection** - `detect_intent()` scores questions against keyword lists per intent
- **Clause analysis bypass** - Questions prefixed with `[CLAUSE ANALYSIS]` always route to RAG
- **LLM visualization enhancement** - Uses `gpt-4o-mini` to generate contextual follow-up questions and adaptive chart specifications from structured data
- **Heuristic fallback** - `_fallback_enhancement()` provides charts/follow-ups when LLM is unavailable
- **Color semantics** - Red for danger, green for safe, blue for informational, etc.
- **Counterparty deduplication** - Deduplicates by filename + tenant_id with garbage-name sanitization

**Key Functions:**
| Function | Description |
|----------|-------------|
| `detect_intent()` | Classifies question as structured intent or `document_qa` |
| `handle_structured_query()` | Dispatches to intent handler, enhances with LLM |
| `_enhance_with_llm()` | Generates follow-ups and visualizations via GPT-4o-mini |
| `_handle_renewals()` | Renewal query with urgency bucketing |
| `_handle_obligations()` | Obligation query with overdue detection |
| `_handle_risk()` | Risk summary with value-at-risk calculation |
| `_handle_portfolio()` | Portfolio overview with aggregate stats |
| `_handle_sla()` | SLA metric query from knowledge graph |

---

### 9. Schema Extraction Agent

**File:** `backend/app/schemas/extractor.py`
**Agent ID:** Dynamic (`schema_extractor_{schema_id}`)
**Temperature:** Per-schema | **Max Tokens:** Per-schema

**Purpose:** Custom extraction using user-defined schemas for different contract types (MSA, NDA, SOW, etc.).

Unlike the other agents, Schema Extraction agents are **dynamically registered** at extraction time based on the schema definition. The `SchemaExtractor` class:

1. Loads the schema from the `SchemaRegistry`
2. Builds a custom system prompt from the schema's sections, fields, and extraction hints
3. Registers a temporary agent with the orchestrator
4. Routes the extraction request through the orchestrator
5. Validates the response against the schema structure

**Key Features:**
- **Schema-driven prompts** - System prompts are generated from schema definitions, not hardcoded
- **Section-level extraction** - Can extract individual sections for large contracts
- **Validation** - Checks for required sections and fields, calculates per-section confidence
- **Auto-selection** - Can auto-select schema based on contract type
- **Quality metrics** - Returns missing fields, extraction warnings, and timing

**Key Functions:**
| Function | Description |
|----------|-------------|
| `extract()` | Full schema-based extraction |
| `extract_section()` | Single section extraction |
| `extract_with_schema()` | Convenience wrapper function |

## Agent Invocation Patterns

### Upload Pipeline (Two Phases)

Contract processing is split into two phases: fast indexing (synchronous) and deep analysis (background).

**Phase 1 — Indexing** (`IndexingService.index_contract()`):

```
Upload → Parse → Chunk → Index in ChromaDB
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   IndexingService.index_contract()
                    │                               │
                    │   1. extract_metadata_with_fallback()
                    │      └─ AI extraction + regex fallback
                    │      └─ LLM counterparty cleaning
                    │      └─ update_contract_metadata()
                    │                               │
                    │   2. assess_risk()             │
                    │      └─ update_contract_risk() │
                    │                               │
                    │   3. Flush metadata            │
                    │   4. Mark contract COMPLETED   │
                    │   5. Auto-link detection       │
                    └───────────────────────────────┘
```

**Phase 2 — Deep Analysis** (`_run_deep_analysis()` in background):

Triggered as a background task after upload. Runs the full extraction pipeline:

```
_run_deep_analysis()
    │
    ├─ 1. Clause Extraction
    │     └─ extract_clauses() → store_extracted_clauses()
    │
    ├─ 2. Obligation Extraction
    │     └─ extract_obligations() → store_extracted_obligations()
    │
    ├─ 3. SLA Extraction
    │     └─ extract_slas() → store_extracted_slas()
    │
    ├─ 4. Reclassify SLA Chunks
    │     └─ reclassify_sla_chunks() — promotes uncategorized chunks
    │        containing SLA patterns to SERVICE_LEVEL type
    │
    ├─ 5. Renewal Monitoring
    │     └─ analyze_renewal_terms() → update_contract_renewal()
    │
    ├─ 6. Schema-Based Extraction (if schema available)
    │     └─ extract_with_schema() → sync_schema_to_db()
    │
    ├─ 7. Auto-Link Detection
    │     └─ AutoLinkDetector.detect_links() → SuggestedContractLink
    │
    ├─ 8. Compliance Analysis
    │     ├─ IndustryDetector.detect_industry()
    │     ├─ ComplianceGapDetector.check_compliance()
    │     ├─ create_compliance_alerts_for_gaps()
    │     └─ extract_regulatory_obligations() (regulated industries)
    │
    └─ 9. Governance Bridge
          └─ GovernanceBridgeService.bridge_contract_to_governance()
              ├─ Auto-create organization from counterparty
              ├─ Auto-create business relationship
              ├─ Convert SLAs → KPIs
              ├─ Create improvement points from high-risk clauses
              ├─ Calculate health score
              └─ Link SOW services to service portfolio
```

### Process Endpoint

`POST /api/contracts/{id}/process` triggers the same deep analysis pipeline manually for a contract that has already been indexed.

### Q&A Flow (Interactive)

```
User Question
     │
     ▼
  Intent Router: detect_intent()
     │
     ├─▶ Structured intent (renewals/obligations/risk/portfolio/sla)
     │      │
     │      ▼
     │   handle_structured_query()  ──▶  PostgreSQL (direct queries)
     │      │
     │      ▼
     │   _enhance_with_llm()  ──▶  GPT-4o-mini (visualizations + follow-ups)
     │      │
     │      ▼
     │   Return: answer + stat_cards + charts + tables
     │
     └─▶ document_qa
            │
            ▼
       ContractSearchTool.search()  ──▶  ChromaDB (vector similarity)
            │
            ▼
       inject_context()  ──▶  Format search results as context
            │
            ▼
       Orchestrator.route_request()
            │
            ├─▶ _classify_intent()  ──▶  Selects "contract_qa"
            │
            ▼
       OpenAI GPT-4o  ──▶  Answer with source citations
            │
            ▼
       _parse_qa_response()  ──▶  QAResponse with confidence + follow-ups
```

### Re-analysis Endpoint

`POST /api/query/analyze` triggers a full re-extraction of all analysis types:
1. Metadata extraction
2. Clause extraction
3. Obligation extraction
4. Risk assessment
5. Renewal analysis
6. SLA extraction
7. Compliance analysis
8. Governance bridge

## Auto-Link Detection

**File:** `backend/app/services/auto_link_detector.py`

The `AutoLinkDetector` uses multi-signal scoring to suggest parent/child and related contract relationships. It runs twice: once in the indexer (after marking contract completed) and again in deep analysis.

### 6 Weighted Signals

| Signal | Weight | Description |
|--------|--------|-------------|
| `counterparty_match` | 0.30 | Exact case-insensitive counterparty name match |
| `counterparty_fuzzy` | 0.20 | Partial or fuzzy counterparty name match |
| `type_hierarchy` | 0.25 | Contract type parent/child relationship (e.g., MSA → SOW, SOW → Amendment) |
| `semantic_similarity` | 0.20 | ChromaDB vector similarity between contract chunks |
| `filename_pattern` | 0.15 | Filename regex matching (amendment, renewal, SOW, schedule patterns) |
| `same_batch` | 0.15 | Uploaded together in the same batch |
| `date_proximity` | 0.10 | Effective dates within proximity window |

**Contract Type Hierarchy:**
- MSA is parent of SOW, Amendment
- NDA is parent of Amendment
- SOW is parent of Amendment
- Vendor Agreement is parent of SOW, Amendment

Suggestions are stored as `SuggestedContractLink` records with a confidence score (sum of matching signals, capped at 1.0) and human-readable reasoning.

---

## Governance Bridge

**File:** `backend/app/services/governance_bridge.py`

The `GovernanceBridgeService` is not an AI agent but a critical automation service that runs as the final step of deep analysis. It bridges contract intelligence (AI-extracted data) to relationship governance (organizations, relationships, KPIs, improvements).

Each automation is independent and fault-tolerant: one failure does not block others. Employment contracts are skipped (no B2B governance).

### 6 Automations

**Automation 1 — Counterparty to Organization:**
- Matches counterparty name to existing `Organization` (exact then fuzzy)
- If no match, auto-creates a new Organization with type inferred from contract type (MSA/SOW → Customer, Vendor Agreement → Vendor, NDA → Partner)
- Generates a short org code from the counterparty name

**Automation 2 — Contract to Business Relationship:**
- Finds or creates a `BusinessRelationship` between the tenant's internal org and the counterparty org
- Infers relationship type from org type (Customer, Supplier, Partner)
- Links the contract to the relationship via `business_relationship_id`

**Automation 3 — SLA to KPI:**
- Loads extracted `ContractSLA` records for the contract
- Creates `KPI` records on the business relationship, mapping metric types to KPI categories:
  - Uptime/Availability → Service Delivery (Percentage)
  - Response/Resolution/Delivery Time → Timeliness (Hours/Days)
  - Error Rate → Quality (Percentage)
  - Compliance/Success Rate → Compliance (Percentage)
- Carries over target values and warning thresholds
- Deduplicates by KPI name on the relationship

**Automation 4 — Risk to Improvement Points:**
- Loads HIGH and CRITICAL risk clauses for the contract
- Creates `ImprovementPoint` records on the business relationship with source `CONTRACT_RISK`
- Maps 8 high-risk clause types to human-readable labels (e.g., "Broad Indemnification", "IP Ownership Risk", "Auto-Renewal Trap")
- Priority mapped from clause risk level (CRITICAL → Critical, HIGH → High)
- Includes clause excerpt in the improvement description

**Automation 5 — Health Score Calculation:**
- Computes a composite health score (0-100) for the relationship using three weighted components:
  - **Contract Risk (30%)** — inverted risk score (low risk = high health)
  - **SLA Compliance (40%)** — average `current_compliance_rate` across all active SLAs
  - **Obligation Health (30%)** — weighted by RAG status (green=100, amber=50, red=0)
- Weights are normalized to sum to 1.0 when components are missing
- Falls back to 75 (neutral) when no data is available

**Automation 6 — SOW Services to Portfolio:**
- Only runs for SOW contracts
- Extracts service names from `schema_data.services.line_items` or SERVICE_DESCRIPTION clauses
- Fuzzy-matches against existing `ServicePortfolio` entries (does not auto-create portfolios)
- Creates `RelationshipService` links between the relationship and matched portfolio entries

### Governance Bridge Summary Return

The bridge returns a summary dict for each contract:
```python
{
    "org_matched": "<uuid>",
    "org_created": True/False,
    "relationship_matched": "<uuid>",
    "relationship_created": True/False,
    "kpis_created": 3,
    "improvements_created": 2,
    "health_score": 82,
    "services_linked": 1,
    "errors": []
}
```

---

## Observability

The platform uses **Langfuse** for full LLM observability:

### Automatic Tracing

- The `LangfuseAsyncOpenAI` wrapper (from `langfuse.openai`) automatically traces all OpenAI API calls
- Initialized at module level in `base.py` when Langfuse credentials are configured
- Falls back to standard `AsyncOpenAI` client when Langfuse is unavailable

### Per-Request Traces

Every orchestrator request creates a Langfuse trace with:
- `user_id` - Who made the request
- `session_id` - Groups related requests (e.g., all extractions for one contract)
- `contract_id` - Links traces to specific contracts
- `agent_name` - Which agent handled the request

### Prompt Management

The `PromptManager` (`langfuse_service.py`) provides centralized prompt management:
- **Langfuse-first** - Fetches prompts from Langfuse if available
- **Local fallback** - Uses hardcoded prompts when Langfuse is unavailable
- **Caching** - Prompt cache with version tracking
- **Sync** - `sync_to_langfuse()` can push local prompts to Langfuse

### Decorator-Based Tracing

The `run_agent()` function is decorated with `@observe(name="run_agent")` from Langfuse for automatic span creation, with graceful fallback if decorators are unavailable.

### Health Monitoring

The `/api/health` endpoint reports:
```json
{
  "status": "healthy",
  "services": {
    "chromadb": "healthy",
    "openai": "healthy",
    "langfuse": "healthy",
    "agents_registered": 9
  }
}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | required | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | Model used by all agents |
| `LANGFUSE_PUBLIC_KEY` | optional | Enables Langfuse tracing |
| `LANGFUSE_SECRET_KEY` | optional | Enables Langfuse tracing |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Langfuse server URL |

### Startup Registration

In `backend/app/main.py`, the lifespan handler registers all agents:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_default_agents()   # Registers orchestrator defaults (contract_qa, metadata, risk)
    register_all_agents()         # Registers all 9 specialized agents
    get_schema_registry().load_schemas()  # Loads schema definitions
    auto_seed_master_data(db)     # Auto-seeds master data if needed
    start_scheduler()             # Starts background scheduler (with file lock)
    ...
```

### Agent Configuration Summary

| Agent | Temperature | Max Tokens | Invocation |
|-------|-------------|------------|------------|
| Metadata Extraction | 0.0 | 1500 | Pipeline (indexer) |
| Clause Extraction | 0.1 | 4000 | Pipeline (deep analysis) |
| Obligation Tracking | 0.1 | 4000 | Pipeline (deep analysis) |
| Risk Detection | 0.1 | 3000 | Pipeline (indexer) |
| Renewal Monitoring | 0.0 | 1500 | Pipeline (deep analysis) |
| Contract Q&A | 0.2 | 2000 | Interactive (query) |
| SLA Extraction | 0.1 | 4000 | Pipeline (deep analysis) |
| Schema Extraction | Per-schema | Per-schema | On-demand |
| Intent Router | 0.3 | 2000 | Interactive (query, via contract_qa) |

## Source Files

| File | Description |
|------|-------------|
| `backend/app/agents/__init__.py` | Agent registry, exports, `register_all_agents()` |
| `backend/app/agents/base.py` | Shared infrastructure (AgentConfig, ContractSearchTool, run_agent) |
| `backend/app/agents/metadata_extraction.py` | Metadata extraction agent (SK-001) |
| `backend/app/agents/clause_extraction.py` | Clause extraction agent (SK-002) |
| `backend/app/agents/obligation_tracking.py` | Obligation tracking agent (SK-003) |
| `backend/app/agents/risk_detection.py` | Risk detection agent (SK-004) |
| `backend/app/agents/renewal_monitoring.py` | Renewal monitoring agent (SK-005) |
| `backend/app/agents/contract_qa.py` | Contract Q&A agent (SK-006) |
| `backend/app/agents/sla_extraction.py` | SLA extraction agent (SK-007) |
| `backend/app/agents/intent_router.py` | Intent router for structured vs. RAG queries (SK-008) |
| `backend/app/agents/regulatory_extraction.py` | Regulatory obligation extraction for regulated industries |
| `backend/app/schemas/extractor.py` | Schema-driven extraction agent |
| `backend/app/services/orchestrator.py` | Orchestrator service (routing, registry) |
| `backend/app/services/indexer.py` | Document processing pipeline (Phase 1) |
| `backend/app/services/auto_link_detector.py` | Multi-signal contract relationship detection |
| `backend/app/services/governance_bridge.py` | Contract intelligence to relationship governance bridge |
| `backend/app/services/industry_detector.py` | Industry detection for compliance analysis |
| `backend/app/services/compliance_gap_detector.py` | Compliance gap detection and alerting |
| `backend/app/services/langfuse_service.py` | Langfuse integration and prompt management |
| `backend/app/routers/contracts.py` | Upload endpoint and `_run_deep_analysis()` (Phase 2) |
| `backend/app/main.py` | Application startup (agent registration) |
