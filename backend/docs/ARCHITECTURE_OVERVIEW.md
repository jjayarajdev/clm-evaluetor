# CLM Backend Architecture Overview

> Quick reference architecture documentation for the Contract Lifecycle Management system.

---

## System Architecture (ASCII)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│  ┌─────────────────────┐    ┌─────────────────────┐                         │
│  │   React Frontend    │    │   API Clients       │                         │
│  │   (TypeScript)      │    │   (Mobile/External) │                         │
│  └──────────┬──────────┘    └──────────┬──────────┘                         │
└─────────────┼───────────────────────────┼───────────────────────────────────┘
              │                           │
              ▼                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API LAYER (FastAPI)                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   Auth      │ │  Contracts  │ │   Query     │ │  Dashboard  │           │
│  │   Router    │ │   Router    │ │   Router    │ │   Router    │           │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ Obligations │ │    SLA      │ │  Scheduler  │ │ Master Data │           │
│  │   Router    │ │   Router    │ │   Admin     │ │   Admin     │           │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘           │
│  + 15 more routers (renewals, amendments, vendors, alerts, etc.)            │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            SERVICE LAYER                                     │
│  ┌───────────────────────────────────────────────────────────────────┐      │
│  │                    Document Processing Pipeline                     │      │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐         │      │
│  │  │ Upload  │───▶│ Parser  │───▶│ Chunker │───▶│ Indexer │         │      │
│  │  └─────────┘    └─────────┘    └─────────┘    └─────────┘         │      │
│  └───────────────────────────────────────────────────────────────────┘      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │Orchestrator │ │  Scheduler  │ │ Notification│ │SLA Compare  │           │
│  │  Service    │ │  Service    │ │  Service    │ │  Engine     │           │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘           │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AI LAYER                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         Agent Orchestrator                           │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │    │
│  │  │Contract  │ │Metadata  │ │ Clause   │ │Obligation│ │  Risk    │  │    │
│  │  │  Q&A     │ │Extraction│ │Extraction│ │ Tracking │ │Detection │  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                            │    │
│  │  │ Renewal  │ │   SLA    │ │  Schema  │                            │    │
│  │  │Monitoring│ │Extraction│ │Extraction│   (8 Specialized Agents)   │    │
│  │  └──────────┘ └──────────┘ └──────────┘                            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                   │                                          │
│                                   ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │              OpenAI GPT-4o  ◀───────▶  Langfuse (Observability)     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐    │
│  │     PostgreSQL      │ │      ChromaDB       │ │    File Storage     │    │
│  │  ┌───────────────┐  │ │  ┌───────────────┐  │ │  ┌───────────────┐  │    │
│  │  │  50+ Tables   │  │ │  │ Vector Store  │  │ │  │   Uploads     │  │    │
│  │  │  Contracts    │  │ │  │ Embeddings    │  │ │  │   Processed   │  │    │
│  │  │  Obligations  │  │ │  │ Similarity    │  │ │  │   Documents   │  │    │
│  │  │  SLAs         │  │ │  │ Search        │  │ │  │               │  │    │
│  │  │  Users        │  │ │  │               │  │ │  │               │  │    │
│  │  │  Audit Logs   │  │ │  │               │  │ │  │               │  │    │
│  │  └───────────────┘  │ │  └───────────────┘  │ │  └───────────────┘  │    │
│  └─────────────────────┘ └─────────────────────┘ └─────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL INTEGRATIONS                                 │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐                │
│  │   ServiceNow    │ │   Salesforce    │ │   SMTP Server   │                │
│  │   (ITSM Data)   │ │   (CRM Data)    │ │   (Email)       │                │
│  │   Stub/Real     │ │   Stub/Real     │ │                 │                │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Data Flows

### 1. Contract Upload Flow
```
User Upload ──▶ FastAPI ──▶ UploadService ──▶ FileStorage
                                   │
                                   ▼
                            ParserService (PDF/DOCX)
                                   │
                                   ▼
                            ChunkerService (Semantic)
                                   │
                                   ├──▶ ChromaDB (Embeddings)
                                   │
                                   ▼
                            AI Agents (Parallel)
                                   │
                     ┌─────────────┼─────────────┐
                     ▼             ▼             ▼
                 Metadata      Clauses      Obligations
                     │             │             │
                     └─────────────┼─────────────┘
                                   ▼
                            PostgreSQL (Structured)
```

### 2. Q&A Query Flow
```
User Question ──▶ QueryRouter ──▶ Orchestrator
                                      │
                                      ▼
                              ContractQAAgent
                                      │
                                      ├──▶ ChromaDB (Similarity Search)
                                      │
                                      ▼
                                  OpenAI GPT-4o
                                      │
                                      ▼
                              Answer + Citations + Follow-ups
```

### 3. SLA Monitoring Flow
```
SchedulerService (Every 15 min)
        │
        ▼
SLAComparisonJob ──▶ Get Active Contracts
        │
        ▼
For Each Contract:
    ├──▶ ServiceNow Connector (Get Actual Performance)
    │
    ▼
SLAComparisonEngine (Calculate Variance)
        │
        ├─── Breach Detected? ───▶ SLAAlertService
        │                                 │
        │                                 ▼
        │                         NotificationService
        │                                 │
        │                                 ▼
        │                           Email/Slack
        ▼
PostgreSQL (Store Results)
```

---

## Directory Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI entry point + lifespan
│   ├── config.py               # Pydantic settings
│   ├── database.py             # SQLAlchemy async setup
│   │
│   ├── routers/                # API Endpoints (32+ routers)
│   │   ├── auth.py             # Authentication
│   │   ├── contracts.py        # Contract CRUD + upload
│   │   ├── query.py            # Q&A endpoint
│   │   ├── dashboard.py        # Analytics
│   │   ├── scheduler_admin.py  # Job management
│   │   ├── master_data_admin.py# SLA/Milestone configs
│   │   ├── organizations.py    # Organization management
│   │   ├── relationships.py    # Business relationships
│   │   ├── kpis.py             # KPI definitions
│   │   ├── perception.py       # Perception scoring
│   │   ├── improvements.py     # Improvement tracking
│   │   ├── surveys.py          # Survey management
│   │   ├── external.py         # External portal
│   │   └── ...
│   │
│   ├── services/               # Business Logic (23 services)
│   │   ├── orchestrator.py     # Agent routing
│   │   ├── indexer.py          # Document pipeline
│   │   ├── parser.py           # PDF/DOCX extraction
│   │   ├── chunker.py          # Semantic chunking
│   │   ├── vector_store.py     # ChromaDB operations
│   │   ├── scheduler_service.py# Background jobs
│   │   ├── sla_comparison.py   # SLA analysis
│   │   └── ...
│   │
│   ├── agents/                 # AI Agents (8 agents)
│   │   ├── base.py             # Base utilities + SearchTool
│   │   ├── contract_qa.py      # Q&A with RAG
│   │   ├── metadata_extraction.py
│   │   ├── clause_extraction.py
│   │   ├── obligation_tracking.py
│   │   ├── risk_detection.py
│   │   ├── renewal_monitoring.py
│   │   └── sla_extraction.py
│   │
│   ├── models/                 # Database Models (50+ tables)
│   │   ├── contract.py
│   │   ├── obligation.py
│   │   ├── scheduler.py
│   │   ├── master_data.py
│   │   └── ...
│   │
│   ├── schemas/                # Pydantic Schemas
│   │   ├── contract.py
│   │   ├── scheduler.py
│   │   └── ...
│   │
│   ├── connectors/             # External System Stubs
│   │   ├── servicenow_stub.py
│   │   ├── milestone_stub.py
│   │   └── base.py
│   │
│   └── core/                   # Core Utilities
│       ├── security.py         # JWT + bcrypt
│       ├── deps.py             # FastAPI dependencies
│       └── audit.py            # Audit logging
│
├── alembic/                    # Database migrations
├── tasks/                      # Documentation
│   ├── COMPLETED.md
│   ├── TODO.md
│   └── DATA_MODEL.md
└── pyproject.toml              # Dependencies (UV)
```

---

## Key Technologies

| Layer | Technology | Purpose |
|-------|------------|---------|
| API | FastAPI | Async REST API framework |
| Database | PostgreSQL + asyncpg | Relational data storage |
| Vector Store | ChromaDB | Semantic search / RAG |
| AI/LLM | OpenAI GPT-4o | Text generation & extraction |
| Observability | Langfuse | LLM tracing & cost monitoring |
| Auth | JWT + bcrypt | Authentication & password hashing |
| Task Queue | asyncio | Background job processing |
| File Parsing | PyMuPDF, python-docx | Document text extraction |

---

## API Endpoint Summary

| Category | Prefix | Key Endpoints |
|----------|--------|---------------|
| Auth | `/api/auth` | login, logout, me, refresh |
| Contracts | `/api/contracts` | upload, process, CRUD, search |
| Query | `/api/query` | Q&A with RAG |
| Obligations | `/api/obligations` | CRUD, status updates |
| SLA | `/api/sla` | SLA management, compliance |
| Dashboard | `/api/dashboard` | Analytics, metrics |
| Admin | `/api/admin/*` | Scheduler, master data |
| Alerts | `/api/alerts` | Alert management |
| Renewals | `/api/renewals` | Renewal tracking |
| Organizations | `/api/organizations` | Organization CRUD |
| Relationships | `/api/relationships` | Business relationships, teams |
| KPIs | `/api/kpis` | KPI definitions, perception scores |
| Perception | `/api/perception` | Perception scoring, gap analysis |
| Improvements | `/api/improvements` | Improvement point tracking |
| Surveys | `/api/surveys` | Survey templates, instances, responses |
| External | `/api/external` | External portal (token-based) |

---

## Configuration (Environment Variables)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/clm

# ChromaDB
CHROMA_HOST=localhost
CHROMA_PORT=8000

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Langfuse
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...

# JWT
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

---

*Last updated: 2026-02-14*
*Added: Relationship governance endpoints (Organizations, Relationships, KPIs, Perception, Improvements, Surveys, External Portal)*
