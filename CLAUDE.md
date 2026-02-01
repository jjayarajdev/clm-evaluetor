# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLM (Contract Lifecycle Management) is a strategic initiative to build an AI-native contract management platform positioned as an "AI Legal Engineer." The platform aims to disrupt legacy CLM vendors (DocuSign, Icertis, Ironclad, Sirion, Agiloft) through rapid time-to-value, agentic AI workflows, and modern architecture.

**Current State:** PRD complete, implementation tasks generated. Ready to begin development.

## Technical Stack

- **Backend:** Python 3.11+ with FastAPI (async, real-time APIs)
- **Package Manager:** UV (fast Python package manager by Astral)
- **Frontend:** React with TypeScript
- **Editor:** ProseMirror or Slate.js (rich-text with track-changes and Word round-trip)
- **Database:** PostgreSQL (structured entities) + ChromaDB (local vector store for embeddings)
- **AI/ML:** OpenAI GPT-4o for all LLM operations
- **Agent Orchestration:** Agent Squad (AWS open-source, Apache 2.0) with OpenAI integration
- **Observability:** Langfuse via OpenTelemetry for tracing, debugging, and cost monitoring
- **Deployment:** Docker Compose for local development

## Common Commands

```bash
# Backend
cd backend && uv sync          # Install dependencies
cd backend && uv run pytest    # Run tests
cd backend && uv run uvicorn app.main:app --reload  # Run dev server

# Frontend
cd frontend && npm install     # Install dependencies
cd frontend && npm test        # Run tests
cd frontend && npm run dev     # Run dev server

# Docker
docker-compose up              # Start all services
docker-compose down            # Stop all services
```

## Architecture Principles

### Data Model
- **Data-first, not file-first:** Contracts are modeled as clause/obligation graphs with documents as attachments
- **Clause-level granularity:** Documents chunked into clauses and logical sections using layout-aware parsing (LayoutLM/Textract)
- **Hybrid semantic search:** Vector similarity + keyword matches + structured filters with re-ranking

### AI Architecture (Agent Squad)
- **Multi-agent orchestration:** Agent Squad with OpenAIClassifier for intent-based routing
- **RAG pipeline:** ChromaDB vector search + ContractSearchTool for semantic retrieval
- **Observability:** Langfuse integration via OpenTelemetry for full trace visibility
- **Minimal code per agent:** ~10-15 lines using OpenAIAgent/OpenAIAgentOptions pattern

### Implemented Agents (see `tasks/skills.md`)
1. **Metadata Extraction Agent:** Extract parties, dates, values, terms from contracts
2. **Contract Q&A Agent:** RAG-powered question answering over contract corpus
3. **Risk Assessment Agent:** Identify and score contractual risks
4. **Obligation Extraction Agent:** Extract and structure obligations with deadlines
5. **Clause Comparison Agent:** Compare clauses against standard templates
6. **Contract Summarization Agent:** Generate executive summaries
7. **Compliance Check Agent:** Verify regulatory compliance (GDPR, SOC 2, industry-specific)

## Strategic Differentiators

- **Fast onboarding:** Hours-to-value vs months for incumbents
- **Unlimited-users pricing:** Asset-based (contract volume/value) not per-seat
- **Browser-native editor:** Track changes with perfect Word round-trip
- **AI Migration Wizard:** Autonomous ingestion as the primary wedge

## Security Requirements

- SOC 2 Type II compliance
- GDPR/data residency with regional sharding (US/EU)
- Attribute-Based Access Control (ABAC)

## Reference Documents

- `research/CLM Investigations.md` - Comprehensive market analysis, competitive landscape, and technical blueprint
- `tasks/prd-contract-intelligence-mvp.md` - Product Requirements Document for MVP
- `tasks/tasks-contract-intelligence-mvp.md` - Implementation task list (35 tasks, 127 sub-tasks)
- `tasks/skills.md` - Agent Squad agent definitions and orchestration setup
