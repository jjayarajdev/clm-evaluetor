# Contract Intelligence Platform - Product Vision and Feature Roadmap

## Core Vision

**"Making your contracts Transparent, Measurable and ACTIONABLE"**

### Key Differentiator
Most CLM products focus on **pre-execution** (creation, negotiation, e-signatures) and **passive storage**.

This platform focuses on **post-execution operational management**:
- Are contracted obligations being met?
- Are SLAs being achieved?
- Are milestones on track?
- Are pricing/COLA adjustments being applied correctly?
- Are business relationships healthy?

> "There is more business value ($) in optimising the **execution of the intent** of contracts by ensuring the commitments and obligations are best managed."

---

## Architecture Components

| Component | Purpose | Status |
|-----------|---------|--------|
| **Storage Access** | Connect to signed contract storage | Complete |
| **INTAKE** | Upload, analyze, determine management scope | Complete |
| **CONNECTORS** | Link to external "Real World" data sources | Complete (Stub) |
| **GOVERNANCE** | Manage execution, autonomous actions, inform responsible persons | Complete |
| **ORCHESTRATOR** | Structure and oversight across functions | Complete |
| **RELATIONSHIP** | Business relationship and KPI perception management | Complete |

---

## Feature Status

### 1. Contract Upload & Storage

| Feature | Status |
|---------|--------|
| Local/S3 file upload (PDF, DOCX) | Complete |
| Batch upload of related documents | Complete |
| ZIP archive upload with auto-extraction | Complete |
| Client-based organization | Complete |
| Document deduplication (hash-based) | Complete |
| Amendment/version linking | Complete |

---

### 2. Contract Intake & Analysis (AI Extraction)

| Feature | Status |
|---------|--------|
| Clause extraction (17+ types) | Complete |
| Obligation extraction with deadlines and parties | Complete |
| SLA extraction (metrics, targets, penalties) | Complete |
| Metadata extraction (parties, dates, type, value) | Complete |
| Risk assessment (10 risk categories) | Complete |
| Schema-based extraction library (15 contract types, 1,235 fields) | Complete |
| Definition extraction | Complete |
| Process/procedure extraction | Complete |
| Preamble/exhibit extraction | Complete |
| Renewal monitoring (auto-renewal, notice periods) | Complete |

---

### 3. Connectors (External Data Sources)

| Feature | Status |
|---------|--------|
| ServiceNow integration (SLA sync, incident mapping, snow_sla_mappings) | Complete (Stub) |
| Milestone tracking integration | Complete (Stub) |
| FX rate feeds (COLA adjustments) | Complete (Stub) |
| Incident metrics | Complete (Stub) |
| Salesforce integration | Complete (Stub) |
| Microsoft Teams webhook notifications | Complete |
| Email/SMTP integration | Complete |

---

### 4. Governance (Monitoring & Actions)

| Feature | Status |
|---------|--------|
| Compare contracted vs actual SLA performance | Complete |
| Detect threshold breaches with severity levels | Complete |
| Calculate service credits and penalties | Complete |
| Milestone status tracking with health dashboard | Complete |
| Alert management (acknowledge, resolve, escalate, dismiss) | Complete |
| Bulk alert actions | Complete |
| Email notifications with templates | Complete |
| Workflow engine (event detection, automated actions) | Complete |
| Approval workflows | Complete |
| Audit trail of all actions | Complete |
| Scheduled background job execution | Complete |

---

### 5. Dashboard & Reporting

| Feature | Status |
|---------|--------|
| Contract list view with filters and search | Complete |
| Contract detail view with intelligence | Complete |
| Clause breakdown view | Complete |
| Obligation list with RAG status | Complete |
| SLA compliance dashboard | Complete |
| Portfolio risk dashboard | Complete |
| Obligation status tracker with compliance rates | Complete |
| Vendor performance scorecards | Complete |
| Renewal calendar and at-risk view | Complete |
| Milestone health dashboard | Complete |
| Post-signing comprehensive dashboard | Complete |
| Admin dashboard (system metrics) | Complete |
| Legal dashboard (risk overview) | Complete |
| Procurement dashboard (spend, vendors) | Complete |
| Compliance reports with date ranges | Complete |
| Compliance trend analysis | Complete |
| CSV/Excel export | Complete |
| Alert trends and statistics | Complete |

---

### 6. Relationship Governance (Evaluetor)

| Feature | Status |
|---------|--------|
| Organization management (CRUD, types, sizes) | Complete |
| Business relationship tracking with health scores | Complete |
| Relationship team management | Complete |
| KPI definitions with targets and thresholds | Complete |
| Internal perception scoring | Complete |
| External perception scoring | Complete |
| Perception gap calculation and severity classification | Complete |
| Improvement point tracking (auto-generated from gaps) | Complete |
| Improvement action items | Complete |
| Survey template management | Complete |
| Survey instance lifecycle | Complete |
| External survey portal (token-based, no auth) | Complete |

---

### 7. Industry-Aware Compliance & Gap Detection

| Feature | Status |
|---------|--------|
| Industry detection for contracts | Complete |
| Industry compliance rule management | Complete |
| Automated compliance gap detection against rules | Complete |
| Compliance gap severity and remediation | Complete |
| Regulatory obligation tracking | Complete |
| Regulatory extraction agent | Complete |
| Compliance statistics and dashboards | Complete |

---

### 8. Knowledge Graph & Discovery

| Feature | Status |
|---------|--------|
| Entity extraction (parties, clauses, obligations) | Complete |
| Relationship mapping between entities | Complete |
| Graph visualization data | Complete |
| Auto-detected contract links (suggested links) | Complete |
| Established contract links (parent-child, 16 link types) | Complete |
| Link acceptance/rejection workflow | Complete |
| Multi-signal auto-link scoring (counterparty, type, semantic, filename, date) | Complete |

---

### 9. Multi-Tenancy & Access Control

| Feature | Status |
|---------|--------|
| Multi-tenant data isolation (TenantMixin) | Complete |
| Tenant provisioning and plan management | Complete |
| Plan-based contract limits (free/starter/pro/enterprise) | Complete |
| Super Admin cross-tenant access | Complete |
| Business unit hierarchy | Complete |
| External user management | Complete |
| Contract sharing with external users (token-based) | Complete |
| External portal for read-only contract access | Complete |
| External user commenting on shared contracts | Complete |

---

### 10. Custom Fields & Notifications

| Feature | Status |
|---------|--------|
| Custom field definitions (admin) | Complete |
| AI-powered custom field extraction | Complete |
| Custom field validation | Complete |
| Configurable notification rules (contract events) | Complete |
| Microsoft Teams webhook integration | Complete |
| Email notification templates | Complete |
| Portfolio metrics and trend tracking | Complete |
| Metric snapshots for historical analysis | Complete |

---

### 11. Chat & Intelligent Query

| Feature | Status |
|---------|--------|
| Persistent chat sessions with full message history | Complete |
| Sessions grouped by date in sidebar (Today, Yesterday, Previous 7 days, etc.) | Complete |
| Auto-titling from first user message | Complete |
| Multi-tenant isolated, contract-scoped sessions | Complete |
| Intent router with 5 structured query handlers (renewals, obligations, risk, portfolio, SLA) | Complete |
| Concise executive summary answers (3-5 sentences) | Complete |
| LLM-enhanced adaptive visualizations via GPT-4o-mini | Complete |
| Rich visualization pipeline with 4 chart types (stat_cards, bar, pie, table) | Complete |
| Auto-generated visualizations from query context | Complete |
| Visualization persistence integrated into chat messages | Complete |

---

### 12. Schema Extraction Library

| Feature | Status |
|---------|--------|
| Pre-built schemas for 15 contract types (MSA, NDA, SOW, Employment, Vendor, License, Lease, SLA, Amendment, Consulting, Distribution, Franchise, Joint Venture, Partnership, Supply) | Complete |
| 1,235 extractable fields across 133 sections | Complete |
| Auto-loading schema registry from JSON definitions | Complete |
| Competitive with enterprise CLM vendors (Sirion: 1,400 fields) | Complete |

---

### 13. Contract Relationship Detection

| Feature | Status |
|---------|--------|
| AutoLinkDetector with 6 weighted matching signals | Complete |
| Counterparty matching (exact + fuzzy) | Complete |
| Contract type hierarchy detection (MSA→SOW, Vendor→Amendment) | Complete |
| Semantic similarity via ChromaDB embeddings | Complete |
| Filename pattern recognition | Complete |
| Established links (approved parent-child relationships, 16 link types) | Complete |
| Batch approve/reject workflow for suggested links | Complete |

---

### 14. Enhanced Metadata Extraction

| Feature | Status |
|---------|--------|
| Semantic text selection via ChromaDB (vs dumb truncation) | Complete |
| Template detection (brackets, blanks, generic roles) | Complete |
| Garbage counterparty filtering (sentence fragments, addresses, generic terms) | Complete |
| LLM-powered counterparty cleaning with validation | Complete |
| Filename-based fallback extraction | Complete |

---

### 15. Governance Bridge (Contract-to-Governance Automation)

| Feature | Status |
|---------|--------|
| Auto-create organizations from contract counterparties | Complete |
| Auto-create business relationships from contracts | Complete |
| Auto-create KPIs from SLA extraction | Complete |
| 7 automations connecting contract intelligence to governance | Complete |
| Seamless bridge between contract upload and relationship management | Complete |

---

### 16. SLA Benchmarking

| Feature | Status |
|---------|--------|
| Compare SLA performance across contracts | Complete |
| Industry standard benchmarking | Complete |
| Performance trend analysis | Complete |

---

### 17. Contract Sharing & External Portal

| Feature | Status |
|---------|--------|
| Share contracts with external users via secure tokens | Complete |
| External user portal for read-only access | Complete |
| External user commenting on shared contracts | Complete |
| Token-based authentication (no account required) | Complete |

---

### 18. ServiceNow Integration

| Feature | Status |
|---------|--------|
| SLA sync between platform and ServiceNow | Complete (Stub) |
| Incident mapping | Complete (Stub) |
| snow_sla_mappings table | Complete |
| ServiceNow admin configuration page | Complete |

---

## API Coverage Summary (~405 Endpoints)

| Category | Endpoints | Status |
|----------|-----------|--------|
| Authentication | 4 | Complete |
| Tenants | 5 | Complete |
| Users | 5 | Complete |
| Audit Logs | 2 | Complete |
| Clients | 5 | Complete |
| Contracts | 32 | Complete |
| Amendments | 6 | Complete |
| Contract Documents | 5 | Complete |
| Schemas | 5 | Complete |
| Obligations | 12 | Complete |
| SLA Tracking | 14 | Complete |
| SLA Benchmarking | 6 | Complete |
| Renewals | 8 | Complete |
| Vendors | 4 | Complete |
| Milestones | 6 | Complete |
| Dashboard | 24 | Complete |
| Chat Sessions | 8 | Complete |
| Query & AI | 5 | Complete |
| Reports | 8 | Complete |
| Metrics | 5 | Complete |
| Alerts | 14 | Complete |
| Monitor & Events | 6 | Complete |
| Compliance | 20 | Complete |
| Connectors | 8 | Complete |
| Notifications | 6 | Complete |
| Notification Rules | 6 | Complete |
| Post-Signing | 3 | Complete |
| Settings | 3 | Complete |
| Custom Fields | 5 | Complete |
| Workflow Admin | 22 | Complete |
| Scheduler Admin | 10 | Complete |
| Master Data Admin | 8 | Complete |
| Knowledge Graph | 12 | Complete |
| Suggested Links | 8 | Complete |
| Organizations | 6 | Complete |
| Relationships | 10 | Complete |
| KPIs & Perception | 10 | Complete |
| Improvements | 8 | Complete |
| Surveys | 22 | Complete |
| Service Portfolio | 6 | Complete |
| ServiceNow Integration | 8 | Complete |
| Business Units | 8 | Complete |
| External Users | 6 | Complete |
| External Portal | 6 | Complete |
| Contract Sharing | 5 | Complete |
| Health & System | 3 | Complete |
| **Total** | **~405** | |

> See [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) for full endpoint documentation.

---

## Demo Testcases

### Primary Testcase
1. Upload IT outsourcing contracts
2. AI extracts major elements (clauses, SLAs, obligations, metadata, risks)
3. Stub connectors simulate external data (ServiceNow, milestones, FX)
4. Agent compares contracted vs actual performance
5. Automated notifications to governance body
6. Track improvements from perception gaps

### Specific Obligations Demonstrated

| Obligation Type | Extraction | Comparison | Alert |
|----------------|------------|------------|-------|
| Service Level Agreements | Complete | Complete | Complete |
| Service Credits (Critical SLA breach) | Complete | Complete | Complete |
| Milestone Status | Complete | Complete | Complete |
| COLA/FX Adjustments | Complete | Complete | Complete |
| Obligation Compliance | Complete | Complete | Complete |
| Vendor Performance | Complete | Complete | Complete |
| Renewal Deadlines | Complete | Complete | Complete |

---

## Key Principles

> "Agentic AI is not a product decision. It is an **operating model decision**."

### Governance Requirements for Agentic System:
- Clear decision boundaries
- Traceability of actions and outcomes
- Explicit escalation paths
- Reversal and rollback mechanisms
- Cost and capacity controls
- Defined ownership across agents

### Risk to Avoid:
> "The highest risk is not hallucination. It is **silent failure** - Systems that act, change state, and cannot explain why."

---

## Codebase Summary (March 2026)

| Component | Count |
|-----------|-------|
| API Routers | 44 |
| SQLAlchemy Models | 53 |
| Service Modules | 38 |
| AI Agent Files | 11 (9+ functional agents) |
| API Endpoints | ~405 |
| Alembic Migrations | 38 |
| Database Tables | ~77 |
| Frontend Pages | 37 |
| Frontend Components | 28 |
| Backend Scripts | 25 |

### AI Agents (11 files)

| # | Agent | Purpose |
|---|-------|---------|
| 1 | Metadata Extraction | Parties, dates, values, contract type |
| 2 | Contract Q&A | RAG-powered answers via ChromaDB |
| 3 | Risk Detection | 10 risk categories |
| 4 | Obligation Tracking | Deadlines, parties, consequences |
| 5 | Clause Extraction | 17 clause types |
| 6 | Renewal Monitoring | Auto-renewal, notice periods |
| 7 | SLA Extraction | Metrics, targets, penalties |
| 8 | Schema/Custom Field Extraction | 15 contract types, 1,235 fields |
| 9 | Intent Router | Query routing with LLM visualization |
| 10 | Regulatory Extraction | Regulatory obligations and compliance |
| - | base.py | Shared agent base class |
| - | __init__.py | Agent registry |

---

## Completed Phases (0-10)

| Phase | Focus | Status |
|-------|-------|--------|
| 0 | Foundation (FastAPI, PostgreSQL, Auth, Multi-tenancy) | Complete |
| 1 | Contract Upload & AI Extraction Pipeline | Complete |
| 2 | SLA Monitoring, Obligations, Milestones | Complete |
| 3 | Alerts, Workflows, Notifications | Complete |
| 4 | Dashboards & Reporting | Complete |
| 5 | Relationship Governance (Evaluetor) | Complete |
| 6 | Compliance, Knowledge Graph, Schema Library | Complete |
| 7 | Integration & Delivery (Docker, AWS, Seeding) | Complete |
| 8 | Chat, Intent Router, Visualizations | Complete |
| 9 | Auto-Link Detection, Enhanced Metadata, Custom Fields | Complete |
| 10 | Governance Bridge, Business Units, External Users, Contract Sharing | Complete |

---

## Remaining Work

### In Progress
- [ ] End-to-end integration testing (Playwright)
- [ ] Performance optimization
- [ ] Production hardening

### Future Enhancements
- [ ] Real ServiceNow/Salesforce connector implementations
- [ ] Browser-native contract editor (ProseMirror/Slate.js)
- [ ] AI-powered contract redlining
- [ ] Mobile/PWA support
- [ ] SSO/SAML authentication
- [ ] Advanced analytics and ML predictions
- [ ] Real-time collaboration on contract reviews
- [ ] AI contract comparison (clause-level diff)
- [ ] Automated contract generation from templates
- [ ] Multi-language contract support
- [ ] AI-powered negotiation assistance

---

*Last Updated: 2026-03-29*
*Document Owner: Development Team*
