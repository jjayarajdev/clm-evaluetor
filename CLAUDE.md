# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLM (Contract Lifecycle Management) is a strategic initiative to build an AI-native contract management platform positioned as an "AI Legal Engineer." The platform combines contract intelligence (AI-powered extraction and analysis) with relationship governance (Evaluetor-style KPI perception scoring and business relationship management). It aims to disrupt legacy CLM vendors (DocuSign, Icertis, Ironclad, Sirion, Agiloft) through rapid time-to-value, agentic AI workflows, and modern architecture.

**Current State:** Backend complete (Phases 0-4). Frontend and extended features in progress.

## Implementation Progress

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Project Setup (Docker, PostgreSQL, ChromaDB, Agent Squad) | ✅ Complete |
| 1 | Core Backend Infrastructure (Auth, RBAC, Audit) | ✅ Complete |
| 2 | Document Ingestion Pipeline (Upload, Parse, Chunk, Index) | ✅ Complete |
| 3 | AI Skills (6 Agents: Metadata, Clause, Obligation, Risk, Renewal, Q&A) | ✅ Complete |
| 4 | Backend API Endpoints (Contracts, Dashboards, Query) | ✅ Complete |
| 5 | Frontend Foundation (React, Routing, Auth UI, Components) | ✅ Complete |
| 6 | Frontend Features (Upload, Contract Viewer, Dashboards, Chat) | ✅ Complete |
| 7 | Integration & Delivery (Docker, Seed Data, Docs) | ⬜ Not Started |
| 8 | Post-Signing Management (Compliance, SLA, Renewals, Vendor Scoring) | ✅ Complete |
| 9 | Relationship Governance (Evaluetor: KPIs, Perception, Improvements) | ✅ Complete |
| 10 | Surveys (External Portal, Satisfaction Surveys) | ✅ Complete |

**Total:** 54 parent tasks, ~250 sub-tasks across 11 phases.

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

# Database Seeding
cd backend && python -m scripts.seed_data                        # Seed core data (users, contracts)
cd backend && python -m scripts.seed_relationship_governance     # Seed relationship governance data

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
3. **Risk Detection Agent:** Identify and score contractual risks (10 risk categories)
4. **Obligation Tracking Agent:** Extract obligations with deadlines, parties, consequences
5. **Clause Extraction Agent:** Identify and classify 17 clause types
6. **Renewal Monitoring Agent:** Detect auto-renewal, notice periods, calculate deadlines
7. **SLA Extraction Agent:** Extract SLA metrics, targets, and penalty terms
8. **Schema Extraction Agent:** Custom extraction based on user-defined schemas

## Strategic Differentiators

### Contract Intelligence (AI-Native)
- **Fast onboarding:** Hours-to-value vs months for incumbents
- **Unlimited-users pricing:** Asset-based (contract volume/value) not per-seat
- **Browser-native editor:** Track changes with perfect Word round-trip
- **AI Migration Wizard:** Autonomous ingestion as the primary wedge

### Relationship Governance (Evaluetor Features)
- **KPI Perception Scoring:** Compare internal vs external perception of KPI performance
- **Business Relationship Management:** Organization-to-organization relationship tracking
- **Improvement Point Analysis:** Track improvement initiatives linked to perception gaps
- **Multi-party Satisfaction Surveys:** Collect stakeholder satisfaction ratings
- **Governance Structure Visualization:** Team hierarchies and escalation paths

## Security Requirements

- SOC 2 Type II compliance
- GDPR/data residency with regional sharding (US/EU)
- Attribute-Based Access Control (ABAC)

## Reference Documents

- `research/CLM Investigations.md` - Comprehensive market analysis, competitive landscape, and technical blueprint
- `tasks/prd-contract-intelligence-mvp.md` - Product Requirements Document for MVP
- `tasks/tasks-contract-intelligence-mvp.md` - Implementation task list (54 tasks, ~250 sub-tasks)
- `tasks/skills.md` - Agent Squad agent definitions and orchestration setup
- `docs/ARCHITECTURE_DIAGRAMS.md` - System architecture and sequence diagrams (Mermaid)
- `docs/PRODUCT_VISION_AND_ROADMAP.md` - Product vision and feature roadmap
- `backend/docs/ARCHITECTURE_OVERVIEW.md` - Backend architecture quick reference

## Data Model Summary

### Core Entities (Contract Intelligence)
- **Contract** - Document metadata, parties, dates, risk scores
- **Clause** - Extracted clauses with type classification
- **Obligation** - Contractual obligations with deadlines and status
- **ContractSLA** - SLA metrics and targets
- **SLAPerformance** - Actual performance tracking

### Relationship Governance Entities (Phase 9)
- **Organization** - Party profiles (customer, vendor, partner)
- **BusinessRelationship** - Links between organizations with health scores
- **RelationshipTeam** - Team members assigned to relationships
- **KPI** - Key performance indicators per relationship
- **PerceptionScore** - Internal/external perception scores per KPI
- **PerceptionGap** - Calculated gaps between perceptions
- **ImprovementPoint** - Improvement initiatives linked to KPI gaps
- **SurveyTemplate/Instance/Response** - Multi-party satisfaction surveys

### Relationship Governance API Endpoints (Phase 9-10)
- `GET/POST /organizations` - Organization CRUD with filtering
- `GET/POST /relationships` - Business relationship management with team support
- `GET/POST /relationships/{id}/team` - Team member management
- `GET/POST /kpis` - KPI definition and management
- `POST /kpis/perception-scores` - Submit internal/external perception scores
- `GET /kpis/{id}/gaps` - Calculate perception gaps with severity
- `GET/POST /improvements` - Improvement point tracking
- `POST /improvements/generate-from-gaps` - Auto-generate improvements from gaps
- `GET/POST /surveys/templates` - Survey template management
- `GET/POST /surveys/instances` - Survey instance lifecycle
- `POST /surveys/instances/{id}/send` - Send survey to respondents
- `GET/POST /surveys/external/{token}` - External survey completion (no auth)
