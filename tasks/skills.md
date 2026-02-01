# Contract Intelligence MVP - AI Skills Definition

This file defines the AI skills (agents) supported by the Contract Intelligence platform using **Agent Squad** with **OpenAI** and **Langfuse** for observability. It serves as a **product + engineering contract** specifying what each agent does, its inputs/outputs, and implementation requirements.

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Agentic Framework** | [Agent Squad](https://github.com/awslabs/agent-squad) (Apache 2.0) | Multi-agent orchestration |
| **LLM Provider** | OpenAI GPT-4o | Language model |
| **Observability** | [Langfuse](https://langfuse.com) via OpenTelemetry | Tracing, debugging, monitoring |
| **Vector Store** | ChromaDB | Semantic search for RAG |
| **Storage** | PostgreSQL / In-Memory | Conversation and agent state |

---

## Installation & Setup

### Dependencies

```bash
pip install agent-squad openai chromadb langfuse opentelemetry-api opentelemetry-sdk
```

### Environment Variables

```bash
# OpenAI Configuration
export OPENAI_API_KEY="sk-..."

# Langfuse Observability
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."
export LANGFUSE_HOST="https://cloud.langfuse.com"  # or self-hosted URL

# OpenTelemetry for Agent Squad → Langfuse
export OTEL_EXPORTER_OTLP_ENDPOINT="${LANGFUSE_HOST}/api/public/otel"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic $(echo -n ${LANGFUSE_PUBLIC_KEY}:${LANGFUSE_SECRET_KEY} | base64)"
```

---

## Orchestrator Setup

```python
from agent_squad import AgentSquad, OpenAIAgent, OpenAIAgentOptions, OpenAIClassifier, InMemoryChatStorage
from agent_squad.types import ConversationMessage, ParticipantRole
import os

# Initialize the orchestrator with OpenAI classifier (no AWS required)
orchestrator = AgentSquad(
    options={
        "storage": InMemoryChatStorage(),  # or PostgreSQLChatStorage for persistence
        "classifier": OpenAIClassifier(
            model_id="gpt-4o",
            inference_config={"temperature": 0.0}
        ),
        "default_agent": "contract_qa_agent",
        "trace": True  # Enable OpenTelemetry tracing
    }
)

# Register all contract intelligence agents
orchestrator.add_agent(metadata_extraction_agent)
orchestrator.add_agent(clause_extraction_agent)
orchestrator.add_agent(obligation_tracking_agent)
orchestrator.add_agent(risk_detection_agent)
orchestrator.add_agent(renewal_monitoring_agent)
orchestrator.add_agent(contract_qa_agent)
orchestrator.add_agent(deviation_detection_agent)
```

---

## Skills (Agents) Overview

| Agent ID | Name | Purpose | Roles |
|----------|------|---------|-------|
| SK-001 | Metadata Extraction Agent | Extract structured contract attributes | All |
| SK-002 | Clause Extraction Agent | Identify and extract specific clause types | All |
| SK-003 | Obligation Tracking Agent | Extract obligations with parties and deadlines | All |
| SK-004 | Risk Detection Agent | Identify high-risk language and score contracts | Legal |
| SK-005 | Renewal Monitoring Agent | Extract renewal terms and auto-renewal flags | All |
| SK-006 | Contract Q&A Agent | Answer natural language questions | All |
| SK-007 | Deviation Detection Agent | Compare contract language to playbooks | Legal |

---

## Agent Definitions

### SK-001: Metadata Extraction Agent

**Purpose:**
Automatically extract structured metadata from contracts during ingestion to enable filtering, search, and dashboard displays without manual data entry.

**Agent Definition:**

```python
from agent_squad import OpenAIAgent, OpenAIAgentOptions
from pydantic import BaseModel
from typing import Optional, List

# Output Schema
class PartyInfo(BaseModel):
    name: str
    role: str  # Party A | Party B | Vendor | Client | Employer | Employee
    confidence: float

class MetadataOutput(BaseModel):
    contract_type: str  # NDA | MSA | SOW | Amendment | Vendor Agreement | Employment Contract
    contract_type_confidence: float
    counterparty: str
    counterparty_confidence: float
    effective_date: Optional[str]  # ISO date YYYY-MM-DD
    effective_date_confidence: float
    expiration_date: Optional[str]  # ISO date or null if perpetual
    expiration_date_confidence: float
    contract_value: Optional[float]
    currency: Optional[str]
    value_confidence: float
    jurisdiction: Optional[str]
    jurisdiction_confidence: float
    parties: List[PartyInfo]

# Agent Configuration
metadata_extraction_agent = OpenAIAgent(OpenAIAgentOptions(
    name="Metadata Extraction Agent",
    description="""You are a legal document analyst specializing in contract metadata extraction.
    When given contract text, extract: contract type, counterparty name, effective date,
    expiration date, contract value, jurisdiction, and all parties involved.

    Supported contract types: NDA, MSA, SOW, Amendment, Vendor Agreement, Employment Contract.

    Return structured JSON with confidence scores (0.0-1.0) for each field.
    Flag fields with confidence below 0.7 for human review.""",
    model_id="gpt-4o",
    streaming=False,
    inference_config={
        "maxTokens": 2000,
        "temperature": 0.1  # Low temperature for consistent extraction
    },
    tool_config={
        "tool": [
            {
                "type": "function",
                "function": {
                    "name": "extract_metadata",
                    "description": "Extract structured metadata from contract",
                    "parameters": MetadataOutput.model_json_schema()
                }
            }
        ],
        "toolChoice": {"type": "function", "function": {"name": "extract_metadata"}}
    }
))
```

**Inputs:**

```json
{
  "document_text": "string - Full text of the contract",
  "document_type": "string - File type (pdf/docx)",
  "filename": "string - Original filename"
}
```

**Outputs:**

```json
{
  "contract_type": {"value": "string", "confidence": "float"},
  "counterparty": {"value": "string", "confidence": "float"},
  "effective_date": {"value": "string - ISO date", "confidence": "float"},
  "expiration_date": {"value": "string - ISO date or null", "confidence": "float"},
  "contract_value": {"value": "float", "currency": "string", "confidence": "float"},
  "jurisdiction": {"value": "string", "confidence": "float"},
  "parties": [{"name": "string", "role": "string", "confidence": "float"}]
}
```

**Confidence Threshold:** 0.7

**Role Access:** Admin, Legal User, Procurement User

---

### SK-002: Clause Extraction Agent

**Purpose:**
Identify and extract specific clause types from contracts, preserving the exact text and location for reference and analysis.

**Agent Definition:**

```python
from agent_squad import OpenAIAgent, OpenAIAgentOptions

SUPPORTED_CLAUSE_TYPES = [
    "indemnification", "limitation_of_liability", "termination", "confidentiality",
    "intellectual_property", "payment_terms", "warranty", "force_majeure",
    "non_compete", "non_solicitation", "data_protection", "dispute_resolution",
    "assignment", "notice", "governing_law", "sla", "auto_renewal"
]

clause_extraction_agent = OpenAIAgent(OpenAIAgentOptions(
    name="Clause Extraction Agent",
    description=f"""You are a legal clause identification specialist.
    When given contract text, identify and extract specific clause types.

    Supported clause types: {', '.join(SUPPORTED_CLAUSE_TYPES)}

    For each clause found, extract:
    - Exact text of the clause
    - Section number or article reference (e.g., '5.2' or 'Article VII')
    - Page number if available
    - Key terms or values within the clause (e.g., liability cap amount)
    - Confidence score (0.0-1.0)

    Also report which expected clause types are missing from the document.""",
    model_id="gpt-4o",
    streaming=False,
    inference_config={
        "maxTokens": 4000,
        "temperature": 0.1
    }
))
```

**Inputs:**

```json
{
  "document_text": "string - Full text of the contract",
  "clause_types": ["string - Array of clause types to extract"],
  "extract_all": "boolean - If true, extract all identifiable clauses"
}
```

**Supported Clause Types:**
- `indemnification`, `limitation_of_liability`, `termination`, `confidentiality`
- `intellectual_property`, `payment_terms`, `warranty`, `force_majeure`
- `non_compete`, `non_solicitation`, `data_protection`, `dispute_resolution`
- `assignment`, `notice`, `governing_law`, `sla`, `auto_renewal`

**Outputs:**

```json
{
  "clauses": [
    {
      "clause_type": "string",
      "text": "string - Exact text of the clause",
      "section_number": "string",
      "page_number": "int",
      "confidence": "float",
      "sub_clauses": [{"label": "string", "value": "string", "confidence": "float"}]
    }
  ],
  "missing_clauses": ["string - Clause types not found"]
}
```

**Confidence Threshold:** 0.75

**Role Access:** Admin, Legal User, Procurement User

---

### SK-003: Obligation Tracking Agent

**Purpose:**
Extract contractual obligations including responsible parties, deadlines, conditions, and compliance requirements to enable proactive obligation management.

**Agent Definition:**

```python
obligation_tracking_agent = OpenAIAgent(OpenAIAgentOptions(
    name="Obligation Tracking Agent",
    description="""You are a contract obligation analyst.
    Extract all contractual obligations from the document, identifying:

    - Description of each obligation in plain language
    - Original contract text for the obligation
    - Obligated party (who must perform)
    - Beneficiary party (who benefits)
    - Obligation type: Payment | Delivery | Reporting | Compliance | Notification | Other
    - Deadline: Fixed Date | Recurring | Relative | Ongoing
    - Triggering conditions
    - Consequences of non-compliance
    - Section reference

    Provide a summary with total obligations count, breakdown by party, and upcoming deadlines.""",
    model_id="gpt-4o",
    streaming=False,
    inference_config={
        "maxTokens": 4000,
        "temperature": 0.2
    }
))
```

**Inputs:**

```json
{
  "document_text": "string - Full text of the contract",
  "contract_id": "string - Reference to stored contract",
  "focus_party": "string - Optional: extract for specific party only"
}
```

**Outputs:**

```json
{
  "obligations": [
    {
      "id": "string",
      "description": "string - Plain language description",
      "original_text": "string - Exact contract language",
      "obligated_party": "string",
      "beneficiary_party": "string",
      "obligation_type": "string",
      "deadline": {
        "type": "string - Fixed Date | Recurring | Relative | Ongoing",
        "value": "string",
        "parsed_date": "string - ISO date if applicable"
      },
      "conditions": ["string"],
      "consequences": "string",
      "section_reference": "string",
      "confidence": "float"
    }
  ],
  "summary": {
    "total_obligations": "int",
    "by_party": {"party_name": "int"},
    "upcoming_deadlines": "int"
  }
}
```

**Confidence Threshold:** 0.7

**Role Access:** Admin, Legal User, Procurement User

---

### SK-004: Risk Detection Agent

**Purpose:**
Identify high-risk clauses, unfavorable terms, and potential legal exposure. Assign risk scores to contracts and flag specific concerns for legal review.

**Agent Definition:**

```python
RISK_CATEGORIES = [
    "unlimited_liability", "broad_indemnification", "weak_termination",
    "auto_renewal_trap", "unfavorable_ip", "weak_confidentiality",
    "missing_limitation", "one_sided_terms", "regulatory_risk", "ambiguous_language"
]

risk_detection_agent = OpenAIAgent(OpenAIAgentOptions(
    name="Risk Detection Agent",
    description=f"""You are a legal risk analyst specializing in contract risk assessment.
    Analyze the contract for potential legal and business risks.

    Risk categories to evaluate: {', '.join(RISK_CATEGORIES)}

    For each risk found:
    - Category from the list above
    - Severity: Low | Medium | High | Critical
    - Plain language explanation
    - Exact clause text that creates the risk
    - Section reference
    - Recommendation for negotiation or mitigation
    - Confidence score

    Calculate an overall risk score (0-100) and risk level:
    - Low: 0-25
    - Medium: 26-50
    - High: 51-75
    - Critical: 76-100

    Provide an executive summary of key risks in 2-3 sentences.""",
    model_id="gpt-4o",
    streaming=False,
    inference_config={
        "maxTokens": 4000,
        "temperature": 0.2
    }
))
```

**Inputs:**

```json
{
  "document_text": "string - Full text of the contract",
  "contract_type": "string - Type of contract for context",
  "risk_profile": "string - Conservative | Moderate | Aggressive"
}
```

**Risk Categories:**
- `unlimited_liability` - No cap on liability
- `broad_indemnification` - One-sided indemnification
- `weak_termination` - Limited termination rights
- `auto_renewal_trap` - Auto-renewal with short notice period
- `unfavorable_ip` - IP ownership retained by counterparty
- `weak_confidentiality` - Inadequate confidentiality protection
- `missing_limitation` - Missing limitation of liability clause
- `one_sided_terms` - Significantly imbalanced terms
- `regulatory_risk` - Potential compliance issues
- `ambiguous_language` - Vague terms that could be disputed

**Outputs:**

```json
{
  "overall_risk_score": "int - 0-100",
  "risk_level": "string - Low | Medium | High | Critical",
  "risk_factors": [
    {
      "category": "string",
      "severity": "string",
      "description": "string",
      "clause_text": "string",
      "section_reference": "string",
      "recommendation": "string",
      "confidence": "float"
    }
  ],
  "risk_summary": "string - Executive summary",
  "comparison_to_standard": {
    "deviations_count": "int",
    "favorable_terms": "int",
    "unfavorable_terms": "int"
  }
}
```

**Confidence Threshold:** 0.8 (higher for risk assessments)

**Role Access:** Admin, Legal User

---

### SK-005: Renewal Monitoring Agent

**Purpose:**
Extract renewal-related terms including expiration dates, auto-renewal clauses, notice periods, and renewal conditions to prevent unwanted renewals and ensure timely action.

**Agent Definition:**

```python
from datetime import date

renewal_monitoring_agent = OpenAIAgent(OpenAIAgentOptions(
    name="Renewal Monitoring Agent",
    description="""You are a contract renewal specialist.
    Extract all renewal-related terms from the contract:

    Contract Term:
    - Type: Fixed | Perpetual | Evergreen
    - Duration (e.g., '12 months', '3 years')
    - Start and end dates

    Auto-Renewal:
    - Whether enabled
    - Renewal term duration
    - Maximum renewals (if any)
    - Exact clause text

    Notice Period:
    - Days before expiration required
    - Calculate the notice deadline based on current date
    - Days remaining until notice deadline

    Termination for Convenience:
    - Whether allowed
    - Notice days required
    - Conditions

    Generate alerts for:
    - Upcoming expirations
    - Notice deadlines
    - Auto-renewal triggers

    Classify urgency: Immediate (<7 days) | Soon (7-30 days) | Upcoming (30-90 days) | Future (>90 days)""",
    model_id="gpt-4o",
    streaming=False,
    inference_config={
        "maxTokens": 2000,
        "temperature": 0.1
    }
))
```

**Inputs:**

```json
{
  "document_text": "string - Full text of the contract",
  "current_date": "string - ISO date for calculating deadlines"
}
```

**Outputs:**

```json
{
  "renewal_profile": {
    "contract_term": {
      "type": "string - Fixed | Perpetual | Evergreen",
      "duration": "string",
      "start_date": "string - ISO date",
      "end_date": "string - ISO date or null"
    },
    "auto_renewal": {
      "enabled": "boolean",
      "renewal_term": "string",
      "max_renewals": "int or null",
      "clause_text": "string"
    },
    "notice_period": {
      "days": "int",
      "notice_deadline": "string - ISO date",
      "days_remaining": "int",
      "clause_text": "string"
    },
    "termination_for_convenience": {
      "allowed": "boolean",
      "notice_days": "int",
      "conditions": "string"
    }
  },
  "alerts": [
    {
      "type": "string - Expiration | Notice Deadline | Auto-Renewal",
      "date": "string - ISO date",
      "days_until": "int",
      "urgency": "string - Immediate | Soon | Upcoming | Future",
      "recommended_action": "string"
    }
  ],
  "confidence": "float"
}
```

**Confidence Threshold:** 0.75

**Role Access:** Admin, Legal User, Procurement User

---

### SK-006: Contract Q&A Agent

**Purpose:**
Answer natural language questions about contracts using RAG, providing accurate answers with source citations and confidence scores.

**Agent Definition:**

```python
from agent_squad import OpenAIAgent, OpenAIAgentOptions
from agent_squad.tools import Tool

# Custom tool for vector search
class ContractSearchTool(Tool):
    def __init__(self, vector_store):
        self.vector_store = vector_store

    @property
    def name(self) -> str:
        return "search_contracts"

    @property
    def description(self) -> str:
        return "Search contract repository for relevant clauses and sections"

    async def execute(self, query: str, contract_ids: list = None, top_k: int = 10):
        filters = {"contract_id": {"$in": contract_ids}} if contract_ids else None
        results = self.vector_store.query(query, n_results=top_k, where=filters)
        return results

contract_qa_agent = OpenAIAgent(OpenAIAgentOptions(
    name="Contract Q&A Agent",
    description="""You are a contract intelligence assistant.
    Answer natural language questions about contracts using retrieved context.

    For every answer:
    - Provide a direct, accurate response
    - Cite specific sources (contract name, section, page)
    - Include a confidence score based on source quality
    - Suggest relevant follow-up questions

    If the question is ambiguous, ask for clarification.
    If you cannot find relevant information, say so clearly.

    Tailor responses based on user role:
    - Legal: Focus on risk, liability, compliance
    - Procurement: Focus on costs, SLAs, vendor obligations""",
    model_id="gpt-4o",
    streaming=True,  # Enable streaming for better UX
    inference_config={
        "maxTokens": 2000,
        "temperature": 0.3
    }
))

# Add the search tool to the agent
contract_qa_agent.add_tool(ContractSearchTool(vector_store))
```

**Inputs:**

```json
{
  "question": "string - Natural language question",
  "contract_ids": ["string - Optional: limit to specific contracts"],
  "conversation_history": [{"role": "string", "content": "string"}],
  "user_role": "string - For role-appropriate responses"
}
```

**Outputs:**

```json
{
  "answer": "string - Natural language answer",
  "confidence": "float",
  "sources": [
    {
      "contract_id": "string",
      "contract_name": "string",
      "clause_text": "string",
      "section_reference": "string",
      "page_number": "int",
      "relevance_score": "float"
    }
  ],
  "follow_up_questions": ["string"],
  "clarification_needed": "boolean",
  "clarification_prompt": "string"
}
```

**Example Questions by Role:**

| User Role | Example Questions |
|-----------|-------------------|
| Legal | "What is our liability exposure under the Acme contract?" |
| Legal | "Which contracts have non-standard indemnification language?" |
| Legal | "What termination rights do we have with TechCorp?" |
| Procurement | "What are the SLA penalties in our AWS agreement?" |
| Procurement | "How much are we committed to spend with Vendor X this year?" |
| Procurement | "Which vendor contracts are up for renewal in Q2?" |

**Confidence Threshold:** 0.6 (lower threshold, but must cite sources)

**Role Access:** Admin, Legal User, Procurement User

---

### SK-007: Deviation Detection Agent

**Purpose:**
Compare contract language against standard playbooks/templates to identify deviations, non-standard terms, and negotiation points.

**Agent Definition:**

```python
deviation_detection_agent = OpenAIAgent(OpenAIAgentOptions(
    name="Deviation Detection Agent",
    description="""You are a contract compliance analyst.
    Compare contract language against standard playbooks to identify deviations.

    For each deviation found:
    - Clause type
    - Standard/expected playbook language
    - Actual contract language
    - Deviation type: Missing | Modified | Added | Weakened | Strengthened
    - Severity: Low | Medium | High
    - Semantic similarity score (0-1)
    - Business/legal impact of the deviation
    - Recommendation: Accept | Negotiate | Reject
    - Confidence score

    Also identify:
    - Missing required clauses from the playbook
    - Additional clauses not in the playbook (assess if favorable/unfavorable)

    Calculate overall deviation score (0.0 = identical, 1.0 = completely different)
    and compliance level: Compliant | Minor Deviations | Significant Deviations | Non-Compliant""",
    model_id="gpt-4o",
    streaming=False,
    inference_config={
        "maxTokens": 4000,
        "temperature": 0.2
    }
))
```

**Inputs:**

```json
{
  "document_text": "string - Full text of the contract",
  "contract_type": "string - To select appropriate playbook",
  "playbook_id": "string - Optional: specific playbook",
  "deviation_threshold": "float - Minimum difference to flag (default 0.3)"
}
```

**Outputs:**

```json
{
  "overall_deviation_score": "float - 0.0 to 1.0",
  "compliance_level": "string - Compliant | Minor Deviations | Significant Deviations | Non-Compliant",
  "deviations": [
    {
      "clause_type": "string",
      "standard_text": "string",
      "actual_text": "string",
      "deviation_type": "string",
      "severity": "string",
      "similarity_score": "float",
      "impact": "string",
      "recommendation": "string",
      "confidence": "float"
    }
  ],
  "missing_clauses": [
    {"clause_type": "string", "standard_text": "string", "importance": "string"}
  ],
  "added_clauses": [
    {"text": "string", "assessment": "string", "recommendation": "string"}
  ],
  "summary": "string - Executive summary"
}
```

**Confidence Threshold:** 0.75

**Role Access:** Admin, Legal User

---

## Agent Orchestration

### Supervisor Agent (Multi-Agent Coordination)

For complex queries that require multiple agents, use the SupervisorAgent:

```python
from agent_squad import SupervisorAgent, SupervisorAgentOptions

# Create a supervisor that coordinates specialized agents
contract_supervisor = SupervisorAgent(SupervisorAgentOptions(
    name="Contract Intelligence Supervisor",
    description="""You coordinate a team of specialized contract analysis agents.

    Available specialists:
    - Metadata Extraction: For extracting contract attributes
    - Clause Extraction: For finding specific clauses
    - Obligation Tracking: For identifying obligations and deadlines
    - Risk Detection: For assessing contract risks
    - Renewal Monitoring: For tracking renewals and expirations
    - Contract Q&A: For answering questions
    - Deviation Detection: For comparing against playbooks

    Analyze the user's request and delegate to the appropriate specialist(s).
    Coordinate their outputs into a unified response.""",
    model_id="gpt-4o",
    team=[
        metadata_extraction_agent,
        clause_extraction_agent,
        obligation_tracking_agent,
        risk_detection_agent,
        renewal_monitoring_agent,
        contract_qa_agent,
        deviation_detection_agent
    ],
    parallel_processing=True  # Run independent agents in parallel
))
```

### Routing Logic

```python
async def route_request(user_input: str, user_id: str, session_id: str):
    """Route incoming requests through the orchestrator."""

    response = await orchestrator.route_request(
        user_input=user_input,
        user_id=user_id,
        session_id=session_id
    )

    return {
        "agent_id": response.metadata.agent_id,
        "agent_name": response.metadata.agent_name,
        "output": response.output,
        "streaming": response.streaming
    }
```

---

## Execution Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                Agent Squad Execution Flow                        │
└─────────────────────────────────────────────────────────────────┘

1. Request Received
   └─> Validate user role has access
   └─> Log to Langfuse (trace start)

2. Intent Classification (OpenAI Classifier)
   └─> Analyze user query
   └─> Route to appropriate agent(s)
   └─> Log classification decision

3. Context Retrieval (if needed)
   └─> Query ChromaDB for relevant chunks
   └─> Apply metadata filters
   └─> Return top-k results

4. Agent Execution
   └─> Load agent configuration
   └─> Inject retrieved context
   └─> Execute OpenAI GPT-4o call
   └─> Parse structured output
   └─> Log tokens, latency, response

5. Validation
   └─> Check confidence thresholds
   └─> Validate output schema
   └─> Flag low-confidence results

6. Response
   └─> Format JSON response
   └─> Include source citations
   └─> Log to Langfuse (trace end)
   └─> Return to user
```

---

## Langfuse Observability

### What Gets Traced

| Event | Data Captured |
|-------|---------------|
| Agent Invocation | Agent name, input, user_id, session_id |
| LLM Call | Model, tokens (input/output), latency, cost |
| Tool Execution | Tool name, inputs, outputs, duration |
| Vector Search | Query, filters, results count, latency |
| Agent Response | Output, confidence, sources |
| Errors | Exception type, message, stack trace |

### Viewing Traces

Access Langfuse dashboard at your configured `LANGFUSE_HOST` to:
- View hierarchical traces of agent execution
- Debug slow or failing requests
- Monitor token usage and costs
- Analyze confidence score distributions
- Track agent performance over time

---

## Confidence Score Guidelines

| Score Range | Interpretation | UI Display |
|-------------|----------------|------------|
| 0.9 - 1.0 | High confidence, likely accurate | Green badge |
| 0.75 - 0.89 | Good confidence, review recommended | Blue badge |
| 0.6 - 0.74 | Moderate confidence, verification needed | Yellow badge |
| Below 0.6 | Low confidence, flag for human review | Red badge + warning |

---

## Error Handling

Each agent must handle:

| Error Type | Response |
|------------|----------|
| `insufficient_context` | Return partial results with explanation |
| `ambiguous_input` | Return clarifying questions |
| `confidence_below_threshold` | Return results flagged for review |
| `agent_not_applicable` | Suggest alternative agent |
| `rate_limit` | Queue request, return estimated wait time |
| `llm_error` | Retry with exponential backoff, then fail gracefully |

---

## Adding a New Agent

To add a new agent, follow this template:

```python
from agent_squad import OpenAIAgent, OpenAIAgentOptions

new_agent = OpenAIAgent(OpenAIAgentOptions(
    name="New Agent Name",
    description="""Clear description of what this agent does.
    Include:
    - What inputs it expects
    - What outputs it produces
    - Any specific instructions or constraints""",
    model_id="gpt-4o",
    streaming=False,  # or True for chat-like responses
    inference_config={
        "maxTokens": 2000,
        "temperature": 0.2  # Lower for extraction, higher for creative
    }
))

# Register with orchestrator
orchestrator.add_agent(new_agent)
```

**That's it - 10-15 lines of code per agent.**

---

## Versioning

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-31 | Initial skill definitions (DSPy) |
| 2.0 | 2025-02-01 | Migrated to Agent Squad + OpenAI + Langfuse |

---

*This document is the authoritative source for AI agent specifications. Any implementation must conform to these interfaces.*
