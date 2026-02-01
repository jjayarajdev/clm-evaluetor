# Product Requirements Document: Contract Intelligence MVP

## 1. Introduction/Overview

### Problem Statement

Enterprise Legal and Procurement teams manage thousands of contracts stored as static PDFs and Word documents across shared drives, email, and legacy systems. These "dormant" contracts contain critical business intelligence—obligations, risks, renewal dates, spend commitments—that remains inaccessible without manual review. Legal teams waste hours searching for specific clauses, miss renewal deadlines, and fail to identify unfavorable terms until disputes arise.

### Solution

The **Contract Intelligence MVP** is a local, standalone platform that transforms static contracts into actionable intelligence using AI. It provides:

- **Intelligent ingestion** that automatically parses, classifies, and indexes contracts
- **AI-powered skills** for clause extraction, risk detection, and obligation tracking
- **Role-specific dashboards** that surface insights for Legal and Procurement users
- **Proactive alerts** for renewals, risks, and obligation breaches

This MVP is designed for **enterprise demos and early pilots**, showcasing the value of AI-native contract intelligence to prospective clients.

### Target Users

| Role | Primary Needs |
|------|---------------|
| **Admin** | User management, system configuration, global metrics |
| **Legal User** | Risk identification, clause analysis, compliance monitoring |
| **Procurement User** | Vendor obligations, spend tracking, SLA monitoring |

---

## 2. Goals

| # | Goal | Success Indicator |
|---|------|-------------------|
| G1 | Demonstrate AI-powered contract intelligence in under 30 minutes | Demo script completes successfully with sample contracts |
| G2 | Reduce time to find specific contract clauses from hours to seconds | Search returns relevant clauses in <3 seconds |
| G3 | Surface high-risk clauses and obligations automatically | System identifies 90%+ of known risks in test contracts |
| G4 | Provide role-specific views that feel tailored, not generic | Legal and Procurement users see different, relevant dashboards |
| G5 | Enable proactive contract management through alerts | System generates accurate renewal/risk alerts |

---

## 3. User Stories

### Admin Stories

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-A1 | As an Admin, I want to create and manage user accounts so that I can control platform access | Admin can create users with username/password, assign roles, deactivate accounts |
| US-A2 | As an Admin, I want to configure alert thresholds so that notifications are relevant | Admin can set days-before-renewal, risk score thresholds |
| US-A3 | As an Admin, I want to see global metrics so that I understand platform usage | Dashboard shows total contracts, users, alerts sent, queries made |
| US-A4 | As an Admin, I want to upload contracts in bulk so that I can onboard client data quickly | Drag-and-drop folder upload, progress indicator, success/failure summary |

### Legal User Stories

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-L1 | As a Legal User, I want to see high-risk clauses across my contract portfolio so that I can prioritize reviews | Dashboard widget shows contracts ranked by risk score with drill-down |
| US-L2 | As a Legal User, I want to ask natural language questions about contracts so that I don't have to read entire documents | Chat interface returns answers with source clause citations |
| US-L3 | As a Legal User, I want to see upcoming renewals and expirations so that I can take timely action | Calendar/list view of contracts expiring in 30/60/90 days |
| US-L4 | As a Legal User, I want to compare contract language to our standard templates so that I can identify deviations | Side-by-side comparison highlighting non-standard language |
| US-L5 | As a Legal User, I want to see termination and liability exposure so that I can assess contractual risk | Extracted termination clauses and liability caps displayed per contract |

### Procurement User Stories

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-P1 | As a Procurement User, I want to see total spend commitments by vendor so that I can manage budgets | Dashboard shows vendor list with committed spend amounts |
| US-P2 | As a Procurement User, I want to track SLA obligations so that I can hold vendors accountable | SLA terms extracted and displayed with compliance status |
| US-P3 | As a Procurement User, I want to identify auto-renewal risks so that I don't get locked into unwanted renewals | Contracts with auto-renewal flagged with notice period deadlines |
| US-P4 | As a Procurement User, I want to see upcoming vendor obligations so that I can ensure compliance | Timeline view of obligations with responsible parties |
| US-P5 | As a Procurement User, I want to ask questions about vendor terms so that I can negotiate better | Chat interface for vendor-specific contract queries |

---

## 4. Functional Requirements

### 4.1 Document Ingestion

| # | Requirement |
|---|-------------|
| FR-1.1 | The system must accept PDF and DOCX file uploads (single file or batch) |
| FR-1.2 | The system must extract text from uploaded documents using OCR when necessary |
| FR-1.3 | The system must parse documents into logical chunks: clauses, sections, and paragraphs |
| FR-1.4 | The system must auto-classify contracts by type: NDA, MSA, SOW, Amendment, Vendor Agreement, Employment Contract |
| FR-1.5 | The system must extract metadata: contract type, counterparty name, effective date, expiration date, contract value, jurisdiction |
| FR-1.6 | The system must store document chunks in ChromaDB with metadata for semantic search |
| FR-1.7 | The system must store structured contract data in PostgreSQL |
| FR-1.8 | The system must display ingestion progress and report success/failure per document |
| FR-1.9 | The system must allow re-processing of failed documents |

### 4.2 RAG + Intelligence Layer (Agent Squad)

| # | Requirement |
|---|-------------|
| FR-2.1 | The system must implement an Agent Squad-based multi-agent pipeline with OpenAI GPT-4o and Langfuse observability |
| FR-2.2 | The system must use intelligent intent classification to route queries to specialized agents |
| FR-2.3 | The system must support natural language queries across the contract repository |
| FR-2.4 | The system must return answers with source clause citations (contract name, section, page) |
| FR-2.5 | The system must provide confidence scores (0-100%) for all AI-generated outputs |
| FR-2.6 | The system must support follow-up questions with conversation context |
| FR-2.7 | The system must implement the AI skills defined in `skills.md` (see Section 4.3) |

### 4.3 AI Skills (Defined in skills.md)

| # | Requirement |
|---|-------------|
| FR-3.1 | The system must implement **Clause Extraction** skill: identify and extract specific clause types |
| FR-3.2 | The system must implement **Obligation Tracking** skill: extract obligations with parties, deadlines, conditions |
| FR-3.3 | The system must implement **Risk Detection** skill: identify high-risk language and score contracts |
| FR-3.4 | The system must implement **Renewal Monitoring** skill: extract renewal terms, auto-renewal flags, notice periods |
| FR-3.5 | The system must implement **Metadata Extraction** skill: extract structured contract attributes |
| FR-3.6 | The system must implement **Contract Q&A** skill: answer natural language questions about contracts |
| FR-3.7 | The system must implement **Deviation Detection** skill: compare contract language to standard playbooks |
| FR-3.8 | Each skill must have defined inputs, outputs (JSON), confidence thresholds, and role access |

### 4.4 User Management & RBAC

| # | Requirement |
|---|-------------|
| FR-4.1 | The system must support three roles: Admin, Legal User, Procurement User |
| FR-4.2 | The system must authenticate users via username and password |
| FR-4.3 | The system must hash and salt passwords before storage |
| FR-4.4 | The system must enforce role-based access to features and dashboards |
| FR-4.5 | Admin must be able to create, edit, and deactivate user accounts |
| FR-4.6 | Admin must be able to assign and change user roles |
| FR-4.7 | The system must log user actions for audit purposes |

### 4.5 Dashboards

#### 4.5.1 Admin Dashboard

| # | Requirement |
|---|-------------|
| FR-5.1 | Display total contracts ingested (by type, by status) |
| FR-5.2 | Display total users (by role, active/inactive) |
| FR-5.3 | Display system activity: queries made, alerts sent, documents uploaded (last 7/30 days) |
| FR-5.4 | Display ingestion queue status and recent failures |
| FR-5.5 | Provide quick actions: add user, upload contracts, configure alerts |

#### 4.5.2 Legal Dashboard

| # | Requirement |
|---|-------------|
| FR-5.6 | **Risk Overview Widget**: Contracts ranked by risk score with color coding (High/Medium/Low) |
| FR-5.7 | **Expiration Timeline Widget**: Calendar view of contracts expiring in 30/60/90 days |
| FR-5.8 | **High-Risk Clauses Widget**: List of flagged clauses (indemnification, liability, termination) with contract links |
| FR-5.9 | **Deviation Alerts Widget**: Contracts with non-standard language flagged |
| FR-5.10 | **Contract Q&A Widget**: Chat interface for natural language queries |
| FR-5.11 | **Recent Activity Widget**: Recent searches, viewed contracts, alerts |

#### 4.5.3 Procurement Dashboard

| # | Requirement |
|---|-------------|
| FR-5.12 | **Spend Commitments Widget**: Total committed spend by vendor, sortable |
| FR-5.13 | **Vendor Obligations Widget**: Upcoming obligations with deadlines and status |
| FR-5.14 | **SLA Tracker Widget**: SLA terms by vendor with compliance indicators |
| FR-5.15 | **Auto-Renewal Risks Widget**: Contracts with auto-renewal, notice period countdown |
| FR-5.16 | **Contract Q&A Widget**: Chat interface for procurement-focused queries |
| FR-5.17 | **Vendor Summary Widget**: Click vendor to see all contracts, terms, obligations |

### 4.6 Alerts & Notifications

| # | Requirement |
|---|-------------|
| FR-6.1 | The system must send email alerts via Outlook/SMTP integration |
| FR-6.2 | Alert types: Renewal Approaching, Obligation Due, High-Risk Clause Detected, Auto-Renewal Notice Period |
| FR-6.3 | Each alert must include: contract name, clause text, reason, confidence score, link to contract |
| FR-6.4 | Admin must be able to configure alert thresholds (e.g., days before renewal) |
| FR-6.5 | Users must be able to subscribe/unsubscribe from alert types |
| FR-6.6 | The system must log all sent alerts |

### 4.7 Contract Viewer

| # | Requirement |
|---|-------------|
| FR-7.1 | Display contract with original formatting preserved |
| FR-7.2 | Highlight extracted clauses and metadata in-context |
| FR-7.3 | Show AI-extracted metadata in sidebar (type, parties, dates, value) |
| FR-7.4 | Enable clause-level Q&A from viewer |
| FR-7.5 | Show risk indicators on flagged clauses |
| FR-7.6 | Allow download of original document |

---

## 4.8 Post-Signing Contract Management

This section covers features for managing contracts after execution, focusing on obligation compliance, SLA tracking, renewals, and performance monitoring. These capabilities differentiate the platform from basic contract repositories.

### 4.8.1 Obligation Compliance Workflow

| # | Requirement |
|---|-------------|
| FR-8.1 | The system must allow users to update obligation status (pending, in_progress, completed, overdue) |
| FR-8.2 | The system must support RAG status (Red/Amber/Green) with compliance notes |
| FR-8.3 | The system must allow assignment of obligation owners |
| FR-8.4 | The system must auto-generate recurring obligations based on frequency |
| FR-8.5 | The system must calculate and display compliance rates by contract, owner, and category |
| FR-8.6 | The system must support compliance evidence upload and attachment |

### 4.8.2 SLA Tracking & Breach Detection

| # | Requirement |
|---|-------------|
| FR-8.7 | The system must extract SLA terms from contracts (response times, uptime, resolution times) |
| FR-8.8 | The system must track SLA performance against targets |
| FR-8.9 | The system must detect and flag SLA breaches with severity levels |
| FR-8.10 | The system must calculate SLA compliance percentages per vendor/contract |
| FR-8.11 | The system must generate proactive alerts before SLA deadlines |

### 4.8.3 Renewal Management

| # | Requirement |
|---|-------------|
| FR-8.12 | The system must display a renewal calendar with 90/60/30 day advance notifications |
| FR-8.13 | The system must flag auto-renewal contracts with notice period countdowns |
| FR-8.14 | The system must track notice period deadlines and generate alerts |
| FR-8.15 | The system must support renewal forecasting based on contract terms |
| FR-8.16 | The system must provide renewal strategy recommendations based on performance data |

### 4.8.4 Amendment & Version Tracking

| # | Requirement |
|---|-------------|
| FR-8.17 | The system must link amendments to parent contracts |
| FR-8.18 | The system must track amendment history with version numbering |
| FR-8.19 | The system must show change summary between contract versions |
| FR-8.20 | The system must maintain audit trail of who made changes and when |
| FR-8.21 | The system must support supersedes relationships (new contract replaces old) |

### 4.8.5 Vendor/Counterparty Performance

| # | Requirement |
|---|-------------|
| FR-8.22 | The system must calculate vendor performance scores based on obligation compliance |
| FR-8.23 | The system must track vendor SLA compliance rates over time |
| FR-8.24 | The system must aggregate spend and exposure per vendor |
| FR-8.25 | The system must identify at-risk vendor relationships (missed SLAs, overdue obligations) |
| FR-8.26 | The system must provide vendor comparison dashboards |

### 4.8.6 Milestone Health Dashboard

| # | Requirement |
|---|-------------|
| FR-8.27 | The system must display milestone status across all contracts (upcoming, at-risk, missed, completed) |
| FR-8.28 | The system must auto-detect at-risk contracts based on milestone health |
| FR-8.29 | The system must provide portfolio-level milestone compliance metrics |
| FR-8.30 | The system must support milestone owner assignment and notifications |

### 4.8.7 Compliance Reporting

| # | Requirement |
|---|-------------|
| FR-8.31 | The system must generate compliance reports by time period |
| FR-8.32 | The system must export obligation fulfillment data for audits |
| FR-8.33 | The system must provide compliance trend analysis |
| FR-8.34 | The system must support scheduled report generation |

---

## 5. Non-Goals (Out of Scope)

| # | Exclusion | Rationale |
|---|-----------|-----------|
| NG-1 | Contract authoring/editing | MVP focuses on intelligence, not document creation |
| NG-2 | E-signature integration | Not needed for demo/pilot phase |
| NG-3 | Multi-tenant cloud deployment | MVP is local/standalone |
| NG-4 | Workflow automation (approvals, routing) | Adds complexity without demo value |
| NG-5 | Invoice reconciliation | Requires financial system integration |
| NG-6 | Real-time collaboration | Not needed for demo scenarios |
| NG-7 | Mobile application | Desktop-first for enterprise demos |
| NG-8 | ~~Compliance/audit reporting~~ | ~~Future enterprise feature~~ **Now in scope (FR-8.31-34)** |
| NG-9 | SSO/SAML integration | Simple auth sufficient for MVP |
| NG-10 | Multiple LLM providers | GPT-4 only for MVP simplicity |

---

## 6. Design Considerations

### 6.1 UI/UX Principles

- **Summaries over raw text**: Users should see extracted insights first, drill down to source text
- **Visual risk indicators**: Color-coded badges, progress bars, and icons for quick scanning
- **Minimal clicks to insight**: Dashboard → Widget → Contract → Clause in 3 clicks max
- **Clean, modern aesthetic**: Inspired by Legitt AI but less cluttered
- **Demo-friendly**: Large fonts, clear labels, impressive at a glance

### 6.2 UI Components

| Component | Description |
|-----------|-------------|
| **Navigation** | Left sidebar with role-based menu items |
| **Dashboard Grid** | Responsive widget layout (2-3 columns) |
| **Contract List** | Sortable, filterable table with key metadata columns |
| **Contract Viewer** | Split view: document left, metadata/AI panel right |
| **Chat Interface** | Floating or embedded Q&A with message history |
| **Alert Banner** | Top-of-page notification for critical alerts |

### 6.3 Color Coding

| Risk Level | Color | Usage |
|------------|-------|-------|
| High Risk | Red (#DC2626) | High-risk clauses, critical alerts |
| Medium Risk | Yellow (#F59E0B) | Warnings, approaching deadlines |
| Low Risk | Green (#10B981) | Compliant, no issues |
| Neutral | Gray (#6B7280) | Informational, no risk assessed |

---

## 7. Technical Considerations

### 7.1 Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Frontend** | React + TypeScript | Component-based, type-safe, widely adopted |
| **Backend** | Python + FastAPI | AI/ML ecosystem, async support, fast APIs |
| **Database** | PostgreSQL | Robust, relational, production-ready |
| **Vector Store** | ChromaDB | Simple, local, good for MVP |
| **Agentic Framework** | Agent Squad | Multi-agent orchestration, open source (Apache 2.0) |
| **LLM** | OpenAI GPT-4o | Best-in-class reasoning |
| **Observability** | Langfuse | LLM tracing, debugging, cost monitoring |
| **Document Parsing** | PyMuPDF, python-docx, Tesseract | PDF/DOCX extraction with OCR fallback |
| **Deployment** | Docker Compose | Single-command local deployment |

### 7.2 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │  Admin   │  │  Legal   │  │  Procure │  │   Contract   │   │
│  │Dashboard │  │Dashboard │  │Dashboard │  │    Viewer    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │ REST API
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │   Auth   │  │ Ingestion│  │  Skills  │  │    Alerts    │   │
│  │ Service  │  │  Service │  │  Engine  │  │   Service    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼───────┐    ┌───────▼───────┐    ┌───────▼───────┐
│  PostgreSQL   │    │   ChromaDB    │    │ Agent Squad   │
│  (Structured) │    │   (Vectors)   │    │ + Langfuse    │
└───────────────┘    └───────────────┘    └───────────────┘
```

### 7.3 Database Schema (Core Tables)

```sql
-- Users & Auth
users (id, username, email, password_hash, role, is_active, created_at, updated_at)
roles (id, name, permissions)
audit_log (id, user_id, action, resource, timestamp)

-- Contracts
contracts (id, filename, file_path, contract_type, counterparty, effective_date,
           expiration_date, value, jurisdiction, risk_score, status,
           uploaded_by, created_at, updated_at)

-- Extracted Data
clauses (id, contract_id, clause_type, text, section_number, page_number,
         risk_level, confidence_score, created_at)
obligations (id, contract_id, clause_id, description, responsible_party,
             deadline, status, created_at)
metadata_extractions (id, contract_id, field_name, field_value, confidence_score)

-- Alerts
alerts (id, user_id, contract_id, clause_id, alert_type, message,
        confidence_score, is_read, sent_at, created_at)
alert_configs (id, user_id, alert_type, threshold_days, is_enabled)
```

### 7.4 Agent Squad Pipeline Structure

```
Ingestion Pipeline:
  Document → Parse → Chunk → Metadata Agent → Clause Agent → Index (ChromaDB + PostgreSQL)

Query Pipeline:
  User Query → OpenAI Classifier → Route to Agent → Retrieve Context → Execute → Validate → Response

Agent Execution:
  Request → Intent Classification → Select Agent(s) → Execute with Langfuse Tracing → Return JSON
```

### 7.5 API Endpoints (Key)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | User authentication |
| POST | `/api/contracts/upload` | Upload contracts (single/batch) |
| GET | `/api/contracts` | List contracts with filters |
| GET | `/api/contracts/{id}` | Get contract details |
| POST | `/api/query` | Natural language query |
| POST | `/api/skills/{skill_name}/execute` | Execute specific skill |
| GET | `/api/dashboard/legal` | Legal dashboard data |
| GET | `/api/dashboard/procurement` | Procurement dashboard data |
| GET | `/api/alerts` | Get user alerts |
| POST | `/api/alerts/config` | Configure alert settings |

---

## 8. Success Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Demo completion rate | 100% | Demo script executes without errors |
| Query response time | <3 seconds | API latency monitoring |
| Clause extraction accuracy | >90% | Manual review of test contracts |
| Risk detection precision | >85% | Comparison to legal review |
| User satisfaction (demo) | >4/5 rating | Post-demo feedback survey |
| Ingestion success rate | >95% | Successful uploads / total uploads |
| Alert accuracy | >90% | Relevant alerts / total alerts |

---

## 9. Open Questions

| # | Question | Impact | Owner |
|---|----------|--------|-------|
| OQ-1 | What sample contracts will be used for demos? | Affects skill tuning and test cases | Product |
| OQ-2 | Should we include a "standard playbook" for deviation detection? | Requires creating baseline templates | Legal SME |
| OQ-3 | What Outlook/SMTP configuration is needed for alerts? | Affects alert service implementation | Engineering |
| OQ-4 | Are there specific clause types beyond common ones to extract? | May require additional skill definitions | Legal SME |
| OQ-5 | What is the expected contract volume for demos (10s, 100s, 1000s)? | Affects performance requirements | Product |
| OQ-6 | Should extracted data be editable by users? | Affects UI and data model | Product |

---

## 10. Deliverables Checklist

| # | Deliverable | Status |
|---|-------------|--------|
| D-1 | `skills.md` - AI skill definitions | Pending |
| D-2 | System architecture document | Pending |
| D-3 | Database schema (PostgreSQL) | Pending |
| D-4 | Agent Squad pipeline implementation | Pending |
| D-5 | React frontend with dashboards | Pending |
| D-6 | FastAPI backend services | Pending |
| D-7 | Docker Compose configuration | Pending |
| D-8 | Demo script and sample contracts | Pending |
| D-9 | User documentation | Pending |

---

## 11. Assumptions & MVP Limitations

### Assumptions

- Users have Docker installed and can run Docker Compose
- OpenAI API key is available and configured
- Sample contracts are in English
- Outlook/SMTP credentials available for email alerts
- Demo environment has 8GB+ RAM for running all services

### MVP Limitations

- **Local only**: No cloud deployment, no remote access
- **Single LLM**: GPT-4 only, no fallback or model switching in UI
- **No fine-tuning**: Using base GPT-4 with prompt engineering only
- **Limited contract types**: 6 types supported (NDA, MSA, SOW, Amendment, Vendor Agreement, Employment Contract)
- **English only**: No multi-language support
- **No version control**: Contract versions not tracked
- **No integrations**: Standalone system, no CRM/ERP connections
- **Basic auth**: No MFA, SSO, or advanced security
- **Single tenant**: No data isolation between users (all users see all contracts)

---

*Document Version: 1.2*
*Created: 2025-01-31*
*Last Updated: 2026-02-01*
*Changes:*
- *v1.1 (2025-02-01): Migrated from DSPy to Agent Squad + OpenAI + Langfuse*
- *v1.2 (2026-02-01): Added Section 4.8 - Post-Signing Contract Management (FR-8.1 to FR-8.34) based on Sirion Labs and Legitt AI competitive analysis*
