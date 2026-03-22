# Agentic AI Architecture

This document describes the multi-agent AI system powering the CLM platform's contract intelligence capabilities.

## Overview

The CLM platform uses a **multi-agent architecture** where specialized AI agents handle distinct contract analysis tasks. All agents are powered by **OpenAI GPT-4o** and orchestrated through a central service with **Langfuse** observability.

Key characteristics:

- **8 specialized agents** registered at startup via `register_all_agents()`
- **Intent-based routing** via LLM classification in the orchestrator
- **Dual invocation paths**: interactive Q&A and batch pipeline extraction
- **RAG retrieval** using ChromaDB vector search with RBAC filtering
- **Structured JSON output** parsed from LLM responses with fallback extraction
- **Automatic tracing** of all LLM calls via Langfuse OpenTelemetry integration

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
  │  │  │ invoke_agent()   │    └────────────────────────────┘  │    │
  │  │  │ (direct call)    │                                    │    │
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
register_all_agents()         # Registers all 7 specialized agents
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

### 7. SLA Extraction Agent

**File:** `backend/app/agents/sla_extraction.py`
**Agent ID:** `sla_extraction`
**Temperature:** 0.1 | **Max Tokens:** 4000

**Purpose:** Extracts Service Level Agreements including metrics, targets, thresholds, and penalty terms.

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

### 8. Schema Extraction Agent

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

### Upload Pipeline

When a contract is uploaded (`POST /api/contracts`), the indexing service triggers agents sequentially:

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
                    └───────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   contracts.py process endpoint │
                    │                               │
                    │   3. extract_clauses()         │
                    │      └─ store_extracted_clauses()
                    │                               │
                    │   4. extract_obligations()     │
                    │      └─ store_extracted_obligations()
                    │                               │
                    │   5. extract_slas()            │
                    │      └─ store_extracted_slas() │
                    └───────────────────────────────┘
```

### Process Endpoint

`POST /api/contracts/{id}/process` triggers the same clause/obligation/SLA extraction pipeline manually for a contract that has already been indexed.

### Q&A Flow (Interactive)

```
User Question
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
    "agents_registered": 10
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
    register_all_agents()         # Registers all 7 specialized agents
    get_schema_registry().load_schemas()  # Loads schema definitions
    ...
```

### Agent Configuration Summary

| Agent | Temperature | Max Tokens | Invocation |
|-------|-------------|------------|------------|
| Metadata Extraction | 0.0 | 1500 | Pipeline (indexer) |
| Clause Extraction | 0.1 | 4000 | Pipeline (process) |
| Obligation Tracking | 0.1 | 4000 | Pipeline (process) |
| Risk Detection | 0.1 | 3000 | Pipeline (indexer) |
| Renewal Monitoring | 0.0 | 1500 | Re-analysis |
| Contract Q&A | 0.2 | 2000 | Interactive (query) |
| SLA Extraction | 0.1 | 4000 | Pipeline (process) |
| Schema Extraction | Per-schema | Per-schema | On-demand |

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
| `backend/app/agents/sla_extraction.py` | SLA extraction agent |
| `backend/app/schemas/extractor.py` | Schema-driven extraction agent |
| `backend/app/services/orchestrator.py` | Orchestrator service (routing, registry) |
| `backend/app/services/indexer.py` | Document processing pipeline |
| `backend/app/services/langfuse_service.py` | Langfuse integration and prompt management |
| `backend/app/main.py` | Application startup (agent registration) |
