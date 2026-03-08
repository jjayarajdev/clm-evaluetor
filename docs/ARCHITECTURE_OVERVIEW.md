# CLM Architecture Overview

> Comprehensive architecture documentation for the Contract Lifecycle Management (Evaluetor) platform.

---

## System Architecture

```
+-----------------------------------------------------------------------------+
|                              CLIENT LAYER                                    |
|  +---------------------+    +---------------------+    +-----------------+  |
|  |   React Frontend    |    |   External Portal   |    |  API Clients    |  |
|  |   (TypeScript)      |    |   (Token-based)     |    |  (Mobile/Ext)   |  |
|  +----------+----------+    +----------+----------+    +--------+--------+  |
+-------------|--------------------------|-----------------------|------------+
              |                          |                       |
              v                          v                       v
+-----------------------------------------------------------------------------+
|                         API LAYER (FastAPI - 40 Routers)                      |
|                                                                              |
|  +-- Contract Intelligence --+  +-- Post-Signing Management ----+           |
|  | auth         contracts    |  | obligations   sla             |           |
|  | users        amendments   |  | renewals      vendors         |           |
|  | tenants      query        |  | milestones    postsigning     |           |
|  | audit        schemas      |  | alerts        compliance      |           |
|  | clients      reports      |  | monitor       connectors      |           |
|  +---------------------------+  +-------------------------------+           |
|                                                                              |
|  +-- Admin & Configuration --+  +-- Relationship Governance ---+            |
|  | dashboard    metrics      |  | organizations relationships  |            |
|  | admin_settings            |  | kpis          improvements   |            |
|  | workflow_admin            |  | surveys                      |            |
|  | scheduler_admin           |  +------------------------------+            |
|  | master_data_admin         |                                              |
|  | custom_fields             |  +-- Multi-Tenant & Access -----+            |
|  | notification_rules        |  | business_units               |            |
|  | notifications             |  | external_users               |            |
|  +---------------------------+  | external_portal              |            |
|                                 +------------------------------+            |
|  +-- Chat --------------------+                                            |
|  | chat (sessions + messages) |                                            |
|  +----------------------------+                                            |
|                                                                              |
|  +-- Discovery & Graph ------+                                              |
|  | knowledge_graph           |                                              |
|  | suggested_links           |                                              |
|  +---------------------------+                                              |
+-------------------------------------+---------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
|                         SERVICE LAYER (35 Services)                          |
|  +-------------------------------------------------------------------+     |
|  |                    Document Processing Pipeline                     |     |
|  |  +---------+    +---------+    +----------+    +---------+         |     |
|  |  | Upload  +--->| Parser  +--->| Chunker  +--->| Indexer |         |     |
|  |  +---------+    +---------+    +----------+    +---------+         |     |
|  |                                                    |               |     |
|  |                    +-------------------------------+               |     |
|  |                    v                                               |     |
|  |            Section Classifier (layout-aware)                       |     |
|  +-------------------------------------------------------------------+     |
|                                                                             |
|  +-- Core Services -----------+  +-- Analysis Services ----------+         |
|  | orchestrator    contracts  |  | sla_comparison  sla_alert     |         |
|  | scheduler       upload    |  | sla_benchmark   calculation   |         |
|  | notification    users     |  | compliance_gap_detector       |         |
|  | audit           tenant    |  | compliance_alert_service      |         |
|  | langfuse        parser    |  | industry_detector             |         |
|  | schema_sync    vector_store| | metric_snapshot_service       |         |
|  | progress_tracker          |  | auto_link_detector            |         |
|  +---------------------------+  +--------------------------------+         |
|                                                                             |
|  +-- Extraction Services -----+  +-- Knowledge Services ---------+         |
|  | definition_extraction     |  | knowledge_graph_extractor     |          |
|  | process_extraction        |  | knowledge_graph_service       |          |
|  | preamble_extraction       |  +-------------------------------+          |
|  | exhibit_extraction        |                                             |
|  | custom_field_extraction   |  +-- Data Services ---------------+         |
|  | custom_field_validator    |  | master_data_repository        |          |
|  | excel_sla_parser          |  | chunker    indexer            |          |
|  +---------------------------+  +-------------------------------+          |
+-------------------------------------+--------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
|                           AI LAYER (9 Agents)                                |
|  +-------------------------------------------------------------------+     |
|  |                      Agent Squad Orchestrator                       |     |
|  |  +------------+ +------------+ +------------+ +------------+       |     |
|  |  | Contract   | | Metadata   | |  Clause    | | Obligation |       |     |
|  |  |   Q&A      | | Extraction | | Extraction | |  Tracking  |       |     |
|  |  +------------+ +------------+ +------------+ +------------+       |     |
|  |  +------------+ +------------+ +------------+ +------------+       |     |
|  |  |   Risk     | |  Renewal   | |    SLA     | | Regulatory |       |     |
|  |  | Detection  | | Monitoring | | Extraction | | Extraction |       |     |
|  |  +------------+ +------------+ +------------+ +------------+       |     |
|  +-------------------------------------------------------------------+     |
|                                      |                                      |
|                                      v                                      |
|  +-------------------------------------------------------------------+     |
|  |           OpenAI GPT-4o  <-------->  Langfuse (Observability)      |     |
|  +-------------------------------------------------------------------+     |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
|                              DATA LAYER                                      |
|  +---------------------+ +---------------------+ +---------------------+   |
|  |     PostgreSQL      | |      ChromaDB       | |    File Storage     |   |
|  |  +---------------+  | |  +---------------+  | |  +---------------+  |   |
|  |  | 50+ Tables    |  | |  | Vector Store  |  | |  |   Uploads     |  |   |
|  |  | Multi-tenant  |  | |  | Embeddings    |  | |  |   Processed   |  |   |
|  |  | 31 Migrations |  | |  | Similarity    |  | |  |   Documents   |  |   |
|  |  |               |  | |  | Search        |  | |  |               |  |   |
|  |  +---------------+  | |  +---------------+  | |  +---------------+  |   |
|  +---------------------+ +---------------------+ +---------------------+   |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
|                        EXTERNAL INTEGRATIONS                                 |
|  +-----------------+ +-----------------+ +-----------------+                |
|  |   ServiceNow   | |   Salesforce    | |   SMTP Server   |                |
|  |   (ITSM Data)  | |   (CRM Data)   | |   (Email)       |                |
|  +-----------------+ +-----------------+ +-----------------+                |
|  +-----------------+                                                        |
|  | Microsoft Teams |                                                        |
|  | (Webhooks)      |                                                        |
|  +-----------------+                                                        |
+-----------------------------------------------------------------------------+
```

---

## Key Data Flows

### 1. Contract Upload & Processing Flow
```
User Upload --> FastAPI --> UploadService --> FileStorage
                                  |
                                  v
                           ParserService (PDF/DOCX)
                                  |
                                  v
                           ChunkerService (Semantic)
                                  |
                                  +---> ChromaDB (Embeddings)
                                  |
                                  v
                           SectionClassifier (Layout-Aware)
                                  |
                                  v
                           AI Agents (Parallel)
                                  |
                    +-------------+-------------+
                    v             v             v
                Metadata      Clauses      Obligations
                    |             |             |
                    v             v             v
                  Risk        Renewals       SLAs
                    |             |             |
                    +-------------+-------------+
                                  v
                           PostgreSQL (Structured)
                                  |
                                  v
                    +-------------+-------------+
                    |             |             |
                    v             v             v
               Compliance    Knowledge     Auto-Link
               Gap Detect    Graph Extract  Detection
```

### 2. Q&A Query Flow (RAG)
```
User Question --> QueryRouter --> Orchestrator
                                     |
                                     v
                             ContractQAAgent
                                     |
                                     +---> ChromaDB (Similarity Search)
                                     |
                                     v
                                 OpenAI GPT-4o
                                     |
                                     v
                             Answer + Citations + Follow-ups
```

### 3. Intent Router & Visualization Pipeline
```
User Query --> detect_intent() --> Intent Classification
                                       |
              +------------------------+------------------------+
              |            |           |           |            |
              v            v           v           v            v
          renewals   obligations    risk      portfolio       sla
              |            |           |           |            |
              v            v           v           v            v
         Structured Handler (PostgreSQL query + executive summary)
                                       |
                                       v
                              data_summary (counts, distributions, detail_rows)
                                       |
                                       v
                          _enhance_with_llm() (GPT-4o-mini)
                                       |
                        +--------------+--------------+
                        |                             |
                        v                             v
                  Visualizations               Follow-up Questions
                  (stat_cards, bar,
                   pie, table)
```

- Intent router classifies user queries into 5 structured categories: renewals, obligations, risk, portfolio, SLA
- Unmatched queries fall through to `document_qa` for RAG-based answering
- Each structured handler queries PostgreSQL and produces a concise executive summary (3-5 sentences) plus a `data_summary` dict
- LLM enhancement via GPT-4o-mini generates adaptive visualizations (stat_cards, bar charts, pie charts, data tables) and contextual follow-up questions
- Heuristic fallback generates basic visualizations when LLM is unavailable

### 4. Chat Conversation History
```
Frontend Chat UI --> /api/chat/sessions (CRUD)
                          |
                          v
                    ChatSession (tenant_id + user_id scoped)
                          |
                          v
                    /api/chat/sessions/:id/messages
                          |
                          v
                    ChatMessage (role, content, sources, visualizations)
                          |
                          +---> Auto-title from first user message
                          |
                          v
                    PostgreSQL (persistent storage)
```

- `ChatSession` and `ChatMessage` models provide persistent conversation storage
- Multi-tenant isolated via `tenant_id` + `user_id` scoping on all queries
- Sessions can optionally be scoped to a specific contract via `contract_id`
- Auto-titling: session title is set from the first user message (truncated to 60 chars)
- Messages store role (user/assistant), content, sources, follow-ups, and visualization data
- Full CRUD via `/api/chat/*` endpoints: list sessions, create, get with messages, update title, delete, add messages

### 5. SLA Monitoring Flow
```
SchedulerService (Every 15 min)
       |
       v
SLAComparisonJob --> Get Active Contracts
       |
       v
For Each Contract:
   +---> ServiceNow Connector (Get Actual Performance)
   |
   v
SLAComparisonEngine (Calculate Variance)
       |
       +--- Breach Detected? ---> SLAAlertService
       |                                |
       |                                v
       |                        NotificationService
       |                                |
       |                                v
       |                          Email / Teams
       v
PostgreSQL (Store Results)
```

### 6. Compliance Monitoring Flow
```
Contract Upload / Periodic Scan
       |
       v
IndustryDetector --> Identify Regulated Industry
       |
       v
ComplianceGapDetector --> Check Against Industry Rules
       |
       v
ComplianceAlertService --> Generate Compliance Gaps
       |
       v
PostgreSQL (Store Gaps + Severity)
```

### 7. External Portal Flow
```
Admin Creates Share --> Token Generated
       |
       v
External User Receives Link
       |
       v
/external/contracts/:token --> Token Validation
       |
       v
Read-Only Contract View + Comment Submission
(No JWT required)
```

---

## Directory Structure

```
backend/
|-- app/
|   |-- main.py                 # FastAPI entry point + lifespan
|   |-- config.py               # Pydantic settings
|   |-- database.py             # SQLAlchemy async setup
|   |
|   |-- routers/                # API Endpoints (40 routers)
|   |   |-- auth.py             # Authentication (login, logout, me, refresh)
|   |   |-- users.py            # User management (CRUD, roles)
|   |   |-- tenants.py          # Tenant management (multi-tenancy)
|   |   |-- audit.py            # Audit log viewing
|   |   |-- clients.py          # Client organization management
|   |   |-- contracts.py        # Contract CRUD + upload + processing
|   |   |-- amendments.py       # Amendment/version management
|   |   |-- schemas.py          # Extraction schema management
|   |   |-- obligations.py      # Obligation tracking + status
|   |   |-- sla.py              # SLA management + compliance
|   |   |-- renewals.py         # Renewal tracking + calendar
|   |   |-- vendors.py          # Vendor performance scoring
|   |   |-- milestones.py       # Milestone tracking
|   |   |-- query.py            # Q&A endpoint (RAG)
|   |   |-- dashboard.py        # Analytics + metrics + role-based views
|   |   |-- postsigning.py      # Post-signing comprehensive view
|   |   |-- reports.py          # Compliance reports + exports
|   |   |-- metrics.py          # Portfolio metrics + trends
|   |   |-- alerts.py           # SLA breach alert management
|   |   |-- monitor.py          # System event monitoring
|   |   |-- compliance.py       # Industry compliance + gap detection
|   |   |-- connectors.py       # External connector management
|   |   |-- notifications.py    # Notification delivery
|   |   |-- notification_rules.py # Notification rule management
|   |   |-- admin_settings.py   # Application settings
|   |   |-- custom_fields.py    # Custom field definitions (admin + public)
|   |   |-- workflow_admin.py   # Workflow definitions + actions + approvals
|   |   |-- scheduler_admin.py  # Background job management
|   |   |-- master_data_admin.py# SLA/Milestone master configs
|   |   |-- knowledge_graph.py  # Entity/relationship graph
|   |   |-- suggested_links.py  # Auto-detected contract links
|   |   |-- organizations.py    # Organization CRUD (Evaluetor)
|   |   |-- relationships.py    # Business relationships + teams (Evaluetor)
|   |   |-- kpis.py             # KPI definitions + perception scores (Evaluetor)
|   |   |-- improvements.py     # Improvement point tracking (Evaluetor)
|   |   |-- surveys.py          # Survey templates + instances (Evaluetor)
|   |   |-- chat.py              # Chat sessions + messages (persistent history)
|   |   |-- business_units.py   # Business unit hierarchy
|   |   |-- external_users.py   # External user management
|   |   +-- external_portal.py  # External portal (no auth)
|   |
|   |-- services/               # Business Logic (35 services)
|   |   |-- orchestrator.py     # Agent routing + intent classification
|   |   |-- indexer.py          # Document processing pipeline
|   |   |-- parser.py           # PDF/DOCX text extraction
|   |   |-- chunker.py          # Semantic chunking
|   |   |-- section_classifier.py # Layout-aware section classification
|   |   |-- upload.py           # File upload handling
|   |   |-- contracts.py        # Contract CRUD operations
|   |   |-- vector_store.py     # ChromaDB operations
|   |   |-- schema_sync.py      # Schema synchronization
|   |   |-- scheduler_service.py# Background job management
|   |   |-- notification_service.py # Email/notification delivery
|   |   |-- tenant_service.py   # Tenant provisioning + management
|   |   |-- sla_comparison.py   # SLA performance analysis
|   |   |-- sla_alert_service.py# Breach detection + alerts
|   |   |-- sla_benchmark_service.py # SLA benchmarking
|   |   |-- calculation_service.py # Metrics calculation
|   |   |-- compliance_gap_detector.py # Industry compliance gap detection
|   |   |-- compliance_alert_service.py # Compliance alert generation
|   |   |-- industry_detector.py  # Regulated industry identification
|   |   |-- knowledge_graph_extractor.py # KG entity/relationship extraction
|   |   |-- knowledge_graph_service.py # KG CRUD operations
|   |   |-- auto_link_detector.py # Automatic contract link detection
|   |   |-- metric_snapshot_service.py # Portfolio metric snapshots
|   |   |-- progress_tracker.py # Processing progress tracking
|   |   |-- custom_field_extraction.py # Custom field AI extraction
|   |   |-- custom_field_validator.py # Custom field validation
|   |   |-- excel_sla_parser.py # Excel SLA data import
|   |   |-- master_data_repository.py # Master data seeding
|   |   |-- langfuse_service.py # LLM observability
|   |   |-- users.py            # User operations
|   |   |-- audit.py            # Audit logging
|   |   |-- definition_extraction.py # Definition extraction
|   |   |-- process_extraction.py    # Process/procedure extraction
|   |   |-- preamble_extraction.py   # Preamble extraction
|   |   +-- exhibit_extraction.py    # Exhibit extraction
|   |
|   |-- agents/                 # AI Agents (9 agents) + Intent Router
|   |   |-- __init__.py         # Agent registration
|   |   |-- base.py             # Base utilities + ContractSearchTool
|   |   |-- intent_router.py    # Intent classification + structured query handlers + LLM visualization
|   |   |-- contract_qa.py      # Q&A with RAG + citations
|   |   |-- metadata_extraction.py  # Party, date, value extraction
|   |   |-- clause_extraction.py    # Clause classification (17+ types)
|   |   |-- obligation_tracking.py  # Obligation + deadline extraction
|   |   |-- risk_detection.py       # Risk assessment (10 categories)
|   |   |-- renewal_monitoring.py   # Auto-renewal + notice periods
|   |   |-- sla_extraction.py       # SLA metric + target extraction
|   |   +-- regulatory_extraction.py # Regulatory compliance extraction
|   |
|   |-- models/                 # Database Models (46 model files, 50+ tables)
|   |   |-- base.py             # Base mixins (UUID, Timestamp, Tenant)
|   |   |-- tenant.py           # Tenant + plans + contract limits
|   |   |-- user.py             # User accounts + roles
|   |   |-- contract.py         # Contract + status + risk level
|   |   |-- clause.py           # Clause records + types
|   |   |-- clause_indicator.py # Clause presence indicators
|   |   |-- obligation.py       # Obligations with deadlines
|   |   |-- sla.py              # SLA definitions + performance
|   |   |-- sla_alert.py        # SLA breach alerts
|   |   |-- party.py            # Contract parties
|   |   |-- key_date.py         # Contract key dates
|   |   |-- financial.py        # Contract financials + liabilities
|   |   |-- definition.py       # Contract definitions
|   |   |-- process_step.py     # Process/procedure steps
|   |   |-- preamble.py         # Contract preambles + party details
|   |   |-- exhibit.py          # Contract exhibits + fee items
|   |   |-- contract_link.py    # Contract parent/child links
|   |   |-- suggested_link.py   # AI-suggested contract links
|   |   |-- client.py           # Client organizations
|   |   |-- audit.py            # Audit log entries
|   |   |-- alert.py            # Alert configurations
|   |   |-- event.py            # System events
|   |   |-- workflow.py         # Workflow definitions + steps
|   |   |-- approval.py         # Approval requests
|   |   |-- notification.py     # Notification records
|   |   |-- notification_rule.py # Notification rule definitions
|   |   |-- scheduler.py        # Job definitions + history
|   |   |-- master_data.py      # SLA/Milestone master configs
|   |   |-- integration.py      # External integrations
|   |   |-- project_task.py     # Project task tracking
|   |   |-- metric_snapshot.py  # Portfolio metric snapshots
|   |   |-- industry.py         # Industry types + compliance enums
|   |   |-- compliance_rule.py  # Industry compliance rules
|   |   |-- compliance_gap.py   # Compliance gap records
|   |   |-- regulatory_obligation.py # Regulatory obligations
|   |   |-- knowledge_graph.py  # KG entities + relationships
|   |   |-- organization.py     # Organizations (Evaluetor)
|   |   |-- relationship.py     # Business relationships + teams
|   |   |-- kpi.py              # KPIs + perception scores + gaps
|   |   |-- improvement.py      # Improvement points + actions
|   |   |-- survey.py           # Survey templates + instances
|   |   |-- chat_session.py     # Chat sessions + messages (conversation history)
|   |   |-- external_access.py  # External portal tokens
|   |   |-- business_unit.py    # Business unit hierarchy
|   |   |-- external_user.py    # External user accounts
|   |   |-- contract_share.py   # Contract sharing tokens
|   |   +-- contract_comment.py # External user comments
|   |
|   |-- schemas/                # Pydantic Schemas (30 schema files)
|   |   |-- auth.py             # Login/token schemas
|   |   |-- user.py             # User CRUD schemas
|   |   |-- audit.py            # Audit log schemas
|   |   |-- contract.py         # Contract request/response models
|   |   |-- amendment.py        # Amendment schemas
|   |   |-- obligation.py       # Obligation schemas
|   |   |-- sla.py              # SLA schemas
|   |   |-- renewal.py          # Renewal schemas
|   |   |-- vendor.py           # Vendor scoring schemas
|   |   |-- milestone.py        # Milestone schemas
|   |   |-- postsigning.py      # Post-signing dashboard schemas
|   |   |-- report.py           # Report schemas
|   |   |-- compliance.py       # Compliance gap/rule schemas
|   |   |-- scheduler.py        # Scheduler schemas
|   |   |-- master_data.py      # Master data schemas
|   |   |-- custom_fields.py    # Custom field schemas
|   |   |-- knowledge_graph.py  # KG entity/relationship schemas
|   |   |-- suggested_link.py   # Suggested link schemas
|   |   |-- organization.py     # Organization schemas
|   |   |-- relationship.py     # Relationship schemas
|   |   |-- kpi.py              # KPI + perception schemas
|   |   |-- improvement.py      # Improvement schemas
|   |   |-- survey.py           # Survey schemas
|   |   |-- business_unit.py    # Business unit schemas
|   |   |-- external_user.py    # External user schemas
|   |   |-- contract_share.py   # Contract sharing schemas
|   |   |-- contract_comment.py # Contract comment schemas
|   |   |-- models.py           # Shared model definitions
|   |   |-- registry.py         # Schema registry
|   |   +-- extractor.py        # Extraction schemas
|   |
|   |-- connectors/             # External System Stubs
|   |   |-- base.py             # Base connector interface
|   |   |-- servicenow_stub.py  # ServiceNow ITSM data (stub)
|   |   |-- milestone_stub.py   # Milestone tracking (stub)
|   |   +-- fx_stub.py          # FX rate feeds (stub)
|   |
|   |-- integrations/           # External Service Integrations
|   |   |-- base.py             # Base integration interface
|   |   |-- email.py            # SMTP email delivery
|   |   |-- servicenow.py       # ServiceNow integration
|   |   |-- salesforce.py       # Salesforce integration
|   |   +-- teams.py            # Microsoft Teams webhooks
|   |
|   |-- workflows/              # Workflow Engine
|   |   |-- event_detector.py   # Event detection (expiry, breaches)
|   |   |-- monitor.py          # Workflow monitoring
|   |   +-- orchestrator.py     # Workflow execution orchestration
|   |
|   |-- actions/                # Workflow Action Handlers
|   |   +-- handlers.py         # Action execution (notify, task, status)
|   |
|   |-- generators/             # Test Data Generation
|   |   +-- synthetic_data.py   # Synthetic contract data generator
|   |
|   +-- core/                   # Core Utilities
|       |-- security.py         # JWT + bcrypt authentication
|       |-- deps.py             # FastAPI dependencies (auth, db, tenant)
|       |-- audit.py            # Audit logging utilities
|       |-- logging.py          # Structured logging configuration
|       +-- middleware.py        # Request logging middleware
|
|-- alembic/                    # Database migrations (31 versions)
|-- data/                       # Sample contracts for testing
|-- storage/                    # Uploaded contract files
|-- scripts/                    # Utility scripts
+-- pyproject.toml              # Dependencies (UV)

frontend/
|-- src/
|   |-- App.tsx                 # Route definitions (15+ pages)
|   |-- contexts/               # React contexts (Auth, Sidebar)
|   |-- components/
|   |   |-- layout/             # MainLayout, Sidebar, Header
|   |   |-- ui/                 # Reusable UI components
|   |   +-- contracts/          # Contract-specific components
|   |-- pages/
|   |   |-- LoginPage.tsx
|   |   |-- ModernDashboardPage.tsx
|   |   |-- ContractsPage.tsx
|   |   |-- ContractViewPage.tsx
|   |   |-- ObligationDetailPage.tsx
|   |   |-- ClauseDetailPage.tsx
|   |   |-- UploadPage.tsx
|   |   |-- QueryPage.tsx
|   |   |-- UsersPage.tsx
|   |   |-- SettingsPage.tsx
|   |   |-- PostSigningPage.tsx
|   |   |-- RenewalsPage.tsx
|   |   |-- VendorsPage.tsx
|   |   |-- ReportsPage.tsx
|   |   |-- ExternalContractPage.tsx
|   |   |-- admin/
|   |   |   |-- SLAConfigPage.tsx
|   |   |   |-- MilestoneConfigPage.tsx
|   |   |   |-- SchedulerPage.tsx
|   |   |   |-- BusinessUnitsPage.tsx
|   |   |   +-- ExternalUsersPage.tsx
|   |   +-- super-admin/
|   |       |-- SuperAdminDashboardPage.tsx
|   |       |-- TenantManagementPage.tsx
|   |       |-- TenantDetailPage.tsx
|   |       |-- GlobalUsersPage.tsx
|   |       +-- CustomFieldsPage.tsx
|   |-- lib/
|   |   +-- api.ts              # API client (Axios)
|   +-- types/
|       |-- index.ts            # Core TypeScript types
|       |-- business-unit.ts    # Business unit types
|       +-- contract-share.ts   # Contract sharing types
+-- vite.config.ts              # Vite build configuration
```

---

## Key Technologies

| Layer | Technology | Purpose |
|-------|------------|---------|
| API | FastAPI | Async REST API framework |
| Database | PostgreSQL + asyncpg | Relational data storage (multi-tenant) |
| Vector Store | ChromaDB | Semantic search / RAG |
| AI/LLM | OpenAI GPT-4o | Text generation & extraction |
| Agent Framework | Agent Squad (AWS) | Multi-agent orchestration |
| Observability | Langfuse | LLM tracing & cost monitoring |
| Auth | JWT + bcrypt | Authentication & password hashing |
| Task Queue | asyncio | Background job processing |
| File Parsing | PyMuPDF, python-docx | Document text extraction |
| Frontend | React + TypeScript | Single-page application |
| Build Tool | Vite | Frontend bundler |
| Package Manager | UV (backend), npm (frontend) | Dependency management |

---

## API Endpoint Summary (~315 Endpoints)

| # | Category | Prefix | Endpoints | Key Operations |
|---|----------|--------|-----------|----------------|
| 1 | Auth | `/api/auth` | 4 | login, logout, me, refresh |
| 2 | Tenants | `/api/tenants` | 5 | CRUD, provisioning |
| 3 | Users | `/api/users` | 5 | CRUD, role management |
| 4 | Audit | `/api/audit` | 2 | log viewing, filtering |
| 5 | Clients | `/api/clients` | 5 | client organization CRUD |
| 6 | Contracts | `/api/contracts` | 28 | upload, process, CRUD, search, sharing, comments |
| 7 | Amendments | `/api/amendments` | 6 | version linking, diffs |
| 8 | Schemas | `/api/schemas` | 5 | extraction schema management |
| 9 | Obligations | `/api/obligations` | 9 | CRUD, status, compliance |
| 10 | SLA | `/api/sla` | 12 | SLA management, compliance, benchmarks |
| 11 | Renewals | `/api/renewals` | 7 | calendar, at-risk, recommendations |
| 12 | Vendors | `/api/vendors` | 4 | performance scoring, rankings |
| 13 | Milestones | `/api/milestones` | 4 | tracking, health dashboard |
| 14 | Dashboard | `/api/dashboard` | 21 | analytics, role-based views, cockpit |
| 15 | Query | `/api/query` | 3 | Q&A with RAG + citations |
| 16 | Reports | `/api/reports` | 6 | compliance reports, CSV/Excel export |
| 17 | Metrics | `/api/metrics` | 3 | portfolio metrics, trends |
| 18 | Alerts | `/api/alerts` | 12 | breach alerts, acknowledge, resolve |
| 19 | Monitor | `/api/monitor` | 5 | system events, health |
| 20 | Compliance | `/api/compliance` | 17 | industry rules, gap detection |
| 21 | Connectors | `/api/connectors` | 6 | external system management |
| 22 | Notifications | `/api/notifications` | 6 | delivery, templates |
| 23 | Notification Rules | `/api/notification-rules` | 5 | rule management |
| 24 | Post-Signing | `/api/postsigning` | 3 | comprehensive dashboard |
| 25 | Settings | `/api/admin/settings` | 3 | application configuration |
| 26 | Custom Fields | `/api/admin/custom-fields` | 5 | field definitions |
| 27 | Workflows | `/api/admin/workflows` | 19 | definitions, actions, approvals |
| 28 | Scheduler | `/api/admin/scheduler` | 9 | job management, history |
| 29 | Master Data | `/api/admin/master-data` | 6 | SLA/Milestone configs |
| 30 | Knowledge Graph | `/api/knowledge-graph` | 9 | entity/relationship graph |
| 31 | Suggested Links | `/api/suggested-links` | 6 | auto-detected links, established links |
| 32 | Organizations | `/api/organizations` | 5 | organization CRUD (Evaluetor) |
| 33 | Relationships | `/api/relationships` | 8 | business relationships, teams |
| 34 | KPIs | `/api/kpis` | 8 | KPI definitions, perception, gaps |
| 35 | Improvements | `/api/improvements` | 7 | improvement points, actions |
| 36 | Surveys | `/api/surveys` | 20 | templates, instances, external |
| 37 | Business Units | `/api/business-units` | 6 | hierarchy management |
| 38 | External Users | `/api/external-users` | 5 | external user CRUD |
| 39 | External Portal | `/api/external` | 5 | token-based access (no auth) |
| 40 | Chat | `/api/chat` | 6 | session CRUD, message history, auto-titling |
| - | Health | `/api/health`, `/api/system-health` | 2 | system health checks |

> See [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) for full endpoint details with request/response examples.

---

## Multi-Tenancy Architecture

```
JWT Token --> Extract tenant_id
                  |
                  v
          TenantMixin on all models
                  |
                  v
     Query filters: WHERE tenant_id = :tenant_id
                  |
                  v
         Data isolation per tenant
```

- All data models inherit `TenantMixin` providing automatic `tenant_id` column
- JWT tokens include `tenant_id` claim, extracted via `get_current_user` dependency
- Super Admin role can access cross-tenant data
- Tenant plans (free/starter/professional/enterprise) control contract limits

---

## AI Agent Architecture

| Agent | Purpose | Input | Output |
|-------|---------|-------|--------|
| Metadata Extraction | Extract parties, dates, values | Contract text | Structured metadata |
| Clause Extraction | Identify and classify clauses | Contract text | 17+ clause types |
| Obligation Tracking | Extract obligations with deadlines | Contract text | Obligations + deadlines |
| Risk Detection | Identify contractual risks | Contract text | 10 risk categories + scores |
| Renewal Monitoring | Detect auto-renewal terms | Contract text | Renewal dates + notice periods |
| Contract Q&A | Answer questions over corpus | User question | Answer + citations + follow-ups |
| SLA Extraction | Extract SLA metrics and targets | Contract text | SLA definitions + penalties |
| Regulatory Extraction | Extract regulatory compliance clauses (FDA, HIPAA, GMP, GDPR, SOC2, etc.) across 10 obligation categories | Contract text + industry context | Regulatory obligations + regulation references + compliance categories |
| Schema Extraction | Extract fields using 15 pre-built contract type schemas (1,235 fields total) | Contract text + schema definition | Structured field values per schema sections |

All 9 agents use the Agent Squad framework with OpenAI GPT-4o and are orchestrated via intent-based routing through `OpenAIClassifier`. The Regulatory Extraction agent is invoked automatically for contracts in regulated industries and covers 10 obligation categories. The Schema Extraction agent supports 15 pre-built contract type schemas with 1,235 extractable fields across 133 sections, providing competitive parity with enterprise CLM vendors.

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

# Logging
LOG_LEVEL=INFO
LOG_JSON=false

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]

# Microsoft Teams (optional)
TEAMS_WEBHOOK_URL=https://...

# SMTP (optional)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
```

---

## Frontend Routes

| Path | Page | Auth Required |
|------|------|---------------|
| `/login` | LoginPage | No |
| `/dashboard` | ModernDashboardPage | Yes |
| `/contracts` | ContractsPage | Yes |
| `/contracts/:id` | ContractViewPage | Yes |
| `/obligations/:id` | ObligationDetailPage | Yes |
| `/clauses/:id` | ClauseDetailPage | Yes |
| `/compliance` | PostSigningPage | Yes |
| `/renewals` | RenewalsPage | Yes |
| `/vendors` | VendorsPage | Yes |
| `/reports` | ReportsPage | Yes |
| `/upload` | UploadPage | Yes |
| `/query` | QueryPage | Yes |
| `/users` | UsersPage | Yes |
| `/settings` | SettingsPage | Yes |
| `/admin/sla-config` | SLAConfigPage | Yes |
| `/admin/milestone-config` | MilestoneConfigPage | Yes |
| `/admin/scheduler` | SchedulerPage | Yes |
| `/admin/business-units` | BusinessUnitsPage | Yes |
| `/admin/external-users` | ExternalUsersPage | Yes |
| `/super-admin` | SuperAdminDashboardPage | Yes (Super Admin) |
| `/super-admin/tenants` | TenantManagementPage | Yes (Super Admin) |
| `/super-admin/tenants/:id` | TenantDetailPage | Yes (Super Admin) |
| `/super-admin/users` | GlobalUsersPage | Yes (Super Admin) |
| `/super-admin/custom-fields` | CustomFieldsPage | Yes (Super Admin) |
| `/external/contracts/:token` | ExternalContractPage | No (token-based) |

---

*Last updated: 2026-03-07*
*Verified against actual codebase: 41 routers, 36 services, 9 agents, 48 model files, 30 schema files + 15 extraction schemas, 31 migrations, 5 integrations*
