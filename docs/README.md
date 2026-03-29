# CLM Platform - Functionality Guide

**Contract Intelligence + Relationship Governance**

> "Making your contracts Transparent, Measurable and ACTIONABLE"

The CLM platform is an AI-native contract lifecycle management system that goes beyond document storage. It combines **contract intelligence** (AI-powered extraction and analysis) with **relationship governance** (KPI perception scoring and business relationship management) to deliver post-execution operational management.

### Platform Statistics

| Component | Count |
|-----------|-------|
| **API Routers** | 44 |
| **API Endpoints** | ~405 |
| **SQLAlchemy Models** | 53 |
| **Database Tables** | ~77 |
| **Services** | 38 |
| **AI Agent Files** | 11 (9+ functional agents) |
| **Frontend Pages** | 37 |
| **Frontend Components** | 28 |
| **Scripts** | 25 |

### Demo Credentials

| Tenant | Username | Password | Role |
|--------|----------|----------|------|
| Acme Corp | admin | admin123 | Admin |
| Acme Corp | legal | legal123 | Legal |
| TechStart | techstart_admin | admin123 | Admin |
| LegalCo | legalco_admin | admin123 | Admin |
| (System) | superadmin | admin123 | Super Admin |

---

## Table of Contents

- [Contract Upload & Ingestion](#contract-upload--ingestion)
- [AI-Powered Contract Analysis](#ai-powered-contract-analysis)
- [Contract Browser & Search](#contract-browser--search)
- [Obligation Management](#obligation-management)
- [SLA Tracking & Compliance](#sla-tracking--compliance)
- [Renewal Management](#renewal-management)
- [Vendor Performance](#vendor-performance)
- [Alerts & Notifications](#alerts--notifications)
- [Relationship Governance](#relationship-governance)
- [Surveys](#surveys)
- [Dashboards & Reporting](#dashboards--reporting)
- [AI Contract Q&A](#ai-contract-qa)
- [Administration](#administration)
- [External Integrations](#external-integrations)

---

## Contract Upload & Ingestion

Upload contracts and let the platform automatically parse, analyze, and index them for search and intelligence.

| Capability | Description |
|------------|-------------|
| **Single file upload** | Upload PDF or DOCX contracts with metadata |
| **Batch upload** | Upload multiple related documents at once |
| **ZIP archive upload** | Upload a ZIP file; all contracts inside are extracted and processed |
| **Client association** | Organize contracts by client for portfolio views |
| **Deduplication** | Hash-based detection prevents duplicate uploads |
| **Supplementary files** | Add supporting documents to an existing contract's folder |
| **Auto-processing** | Uploaded files are automatically parsed, chunked, indexed, and analyzed |
| **Governance Bridge** | Counterparty auto-creates Organization and BusinessRelationship records on upload |
| **Auto-Link Detection** | 7-signal AI detection automatically links related contracts (MSA to SOW, addendums, etc.) |
| **Business Unit assignment** | Assign contracts to business units within the tenant hierarchy |

**Processing Pipeline:**
```
Upload  -->  Parse (PDF/DOCX)  -->  Chunk (layout-aware)  -->  Index (ChromaDB vectors)
                                                                        |
                                                              AI Extraction Pipeline
                                                              (metadata, risk, clauses,
                                                               obligations, SLAs)
                                                                        |
                                                              Post-Processing
                                                              (Governance Bridge,
                                                               Auto-Link Detection)
```

---

## AI-Powered Contract Analysis

Nine specialized AI agents (across 11 agent files) automatically extract structured intelligence from every contract. See [AGENTS.md](./AGENTS.md) for full architecture details.

### Metadata Extraction
- **Contract type** classification (NDA, MSA, SOW, Amendment, Vendor, Employment)
- **Counterparty** identification with LLM-based name cleaning
- **Dates** (effective, expiration) with term-based calculation
- **Financial terms** (value, currency)
- **Jurisdiction** and governing law
- Regex fallback for low-confidence AI results

### Clause Extraction
- **30 clause types** identified and classified (17 legal/risk + 13 IT service/outsourcing)
- Risk level per clause (LOW / MEDIUM / HIGH)
- Missing clause detection (flags expected clauses not found)
- Handles long documents via chunked extraction with overlap

### Obligation Extraction
- **7 obligation types**: Payment, Delivery, Reporting, Compliance, Notification, Performance, Other
- **4 deadline types**: Fixed date, Recurring, Relative, Ongoing
- Identifies obligated party, beneficiary, triggering conditions, and consequences
- Source quote capture for traceability

### Risk Assessment
- **10 weighted risk categories** (liability, indemnification, termination, IP, regulatory, etc.)
- Overall risk score (0-100) with level classification: LOW / MEDIUM / HIGH / CRITICAL
- Per-factor recommendations for risk mitigation
- Clause-level risk references

### Renewal Monitoring
- Auto-renewal detection
- Notice period extraction and deadline calculation
- Urgency classification: IMMEDIATE / SOON / UPCOMING / FUTURE
- Termination for convenience analysis

### SLA Extraction
- **9 metric types** (uptime, response time, resolution time, throughput, etc.)
- Target values, warning thresholds, and breach thresholds
- Penalty terms (fixed, percentage, credit, tiered) with caps
- Measurement period identification

### Schema-Based Extraction
- User-defined extraction schemas for specific contract types
- Section-by-section extraction with field-level confidence
- Validation against schema structure

---

## Contract Browser & Search

| Capability | Description |
|------------|-------------|
| **List & filter** | Browse contracts with filters for type, status, risk level, client, counterparty |
| **Full-text search** | Search across contract content using semantic vector search |
| **Contract detail view** | View all extracted intelligence: metadata, clauses, obligations, SLAs, risk |
| **Amendment tracking** | Link amendments and addendums; view version history with field-level diffs |
| **Auto-Link Detection** | AI-powered 7-signal detection automatically identifies related contracts (MSA/SOW/addendum relationships) with confidence scores |
| **External Portal** | Share contracts with external users via token-based access; configurable access levels (view/comment) with expiration |
| **Status tracking** | Monitor processing status: Draft, Processing, Completed, Failed |
| **Re-analysis** | Trigger full AI re-extraction on any contract |

---

## Obligation Management

Track contractual obligations from extraction through completion.

| Capability | Description |
|------------|-------------|
| **Status lifecycle** | Pending --> In Progress --> Completed (or Overdue / Waived) |
| **RAG indicators** | Red-Amber-Green health status per obligation |
| **Owner assignment** | Assign responsible owners to obligations |
| **Deadline tracking** | Monitor upcoming and overdue deadlines |
| **Compliance evidence** | Upload evidence documents proving obligation fulfillment |
| **Compliance rates** | Calculate compliance by contract, owner, or category |
| **Critical flagging** | Flag obligations as critical for priority attention |

---

## SLA Tracking & Compliance

Monitor contracted service levels against actual performance.

| Capability | Description |
|------------|-------------|
| **SLA definitions** | Define metrics with targets, units, severity, and measurement periods |
| **Performance recording** | Record actual performance measurements over time |
| **Breach detection** | Automatic detection when performance falls below thresholds |
| **Severity classification** | Critical, Major, Moderate, Minor breach levels |
| **Penalty tracking** | Calculate and track financial penalties with caps |
| **Consecutive breaches** | Count consecutive breach periods for escalation |
| **Compliance trending** | Track SLA compliance rates over time (weekly/monthly) |
| **Service credits** | Calculate service credits owed based on SLA terms |

---

## Renewal Management

Never miss a renewal deadline or auto-renewal window.

| Capability | Description |
|------------|-------------|
| **Renewal calendar** | Visual calendar of upcoming expirations and renewal windows |
| **Notice deadlines** | Calculated notice deadlines based on extracted notice periods |
| **Renewal windows** | Contracts grouped by urgency: 30, 60, 90+ days |
| **Auto-renewal alerts** | Flag contracts with auto-renewal clauses approaching notice deadlines |
| **At-risk identification** | Highlight contracts at risk of unwanted auto-renewal |
| **SLA-informed recommendations** | Renewal recommendations that factor in SLA performance history |

---

## Vendor Performance

Score and compare vendor performance across your contract portfolio.

| Capability | Description |
|------------|-------------|
| **Multi-factor scoring** | Normalized scoring across obligation compliance, SLA performance, responsiveness, and issue rate |
| **Weighted formula** | Obligations (40%) + SLA (30%) + Responsiveness (20%) + Issue Rate (10%) |
| **Risk classification** | Low / Medium / High / Critical vendor risk levels |
| **Vendor comparison** | Side-by-side performance comparison across vendors |
| **Trend analysis** | Track vendor performance changes over time |
| **At-risk vendors** | Automatically identify vendors with degrading performance |

---

## Alerts & Notifications

Proactive alerting for contractual events that need attention.

| Capability | Description |
|------------|-------------|
| **Alert categories** | Obligation, SLA, Renewal, Vendor, Milestone, Compliance |
| **Priority levels** | Critical, High, Medium, Low |
| **Alert lifecycle** | Active --> Acknowledged --> Resolved / Escalated / Dismissed |
| **Financial impact** | Track monetary exposure per alert |
| **Bulk operations** | Acknowledge, resolve, or dismiss multiple alerts at once |
| **Email notifications** | Configurable email templates with multi-channel delivery |
| **Notification rules** | Configurable rules per tenant for event-based notifications (renewal approaching, SLA breach, etc.) |
| **Workflow triggers** | Event-driven automation: detect events and execute actions |

---

## Relationship Governance

Evaluetor-style business relationship management with perception gap analysis. Full frontend UI with 9 dedicated governance pages.

### Governance Bridge
- **Automatic org/relationship creation** from contract upload: when a counterparty is detected during AI extraction, the platform auto-creates an Organization record and a BusinessRelationship linking your tenant org to the counterparty
- Contracts are automatically linked to the corresponding BusinessRelationship
- Eliminates manual data entry for relationship setup

### Organizations
- Organization profiles with type (Customer, Vendor, Partner, Internal)
- Industry, size, and region classification
- Contact information management
- Full CRUD via OrganizationsPage and OrganizationDetailPage

### Business Relationships
- Relationship definitions between organizations
- Health score tracking with factor breakdown
- Team member assignment with roles and responsibilities
- Relationship status and owner management
- Full detail view via RelationshipDetailPage with tabs (Overview, KPIs, Team, Contracts, Improvements, Surveys)

### KPI Perception Scoring
| Capability | Description |
|------------|-------------|
| **KPI definitions** | Define KPIs per relationship (Financial, Operational, Quality, Service) |
| **Internal scoring** | Internal team rates KPI performance (1-10 scale) |
| **External scoring** | External party rates KPI performance (1-10 scale) |
| **Gap analysis** | Automatically calculates perception gaps between internal and external scores |
| **Severity levels** | Gaps classified by severity to prioritize action |
| **Improvement generation** | Auto-generate improvement points from perception gaps |

### Improvement Tracking
- Improvement points linked to specific KPI gaps
- Priority levels and ownership assignment
- Status lifecycle: Open --> In Progress --> Blocked / Completed
- Action item sub-tasks with individual status tracking
- Overdue identification

---

## Surveys

Collect structured feedback from internal and external stakeholders.

| Capability | Description |
|------------|-------------|
| **Template management** | Create reusable survey templates with multiple question types |
| **Rating scales** | Configurable satisfaction rating scales |
| **Survey lifecycle** | Draft --> Active --> Closed --> Published |
| **External portal** | Token-based survey access requiring no authentication |
| **Anonymous responses** | Support for anonymous response collection |
| **Response aggregation** | Automatic aggregation and satisfaction metrics |

---

## Dashboards & Reporting

Role-specific dashboards and flexible reporting.

### Dashboards

| Dashboard | Audience | Key Metrics |
|-----------|----------|-------------|
| **Main Dashboard** | All users | Contract counts, risk distribution, upcoming renewals, recent activity |
| **Legal Dashboard** | Legal team | Risk overview, clause analysis, obligation status |
| **Procurement Dashboard** | Procurement | Spend analysis, vendor performance, SLA compliance |
| **Admin Dashboard** | Administrators | System metrics, user activity, processing status |
| **Post-Signing Dashboard** | Operations | Obligation compliance, SLA performance, renewal pipeline, vendor scores, milestones |
| **Contract Intelligence** | Analysts | Clause distribution, obligation breakdown, risk scoring, financial aggregation |

### Reports

| Report | Description |
|--------|-------------|
| **Compliance Report** | Obligation and SLA compliance rates for a date range |
| **Obligation Activity** | Obligation status changes, completions, and overdue items |
| **SLA Performance** | SLA compliance trends (weekly/monthly) |
| **Trend Analysis** | Historical trends across compliance, risk, and vendor performance |
| **CSV Export** | Export any report to CSV for offline analysis |

---

## AI Contract Q&A

Interactive, natural-language question answering over your contract corpus.

| Capability | Description |
|------------|-------------|
| **Natural language queries** | Ask questions in plain English about any contract |
| **RAG retrieval** | Semantic search finds the most relevant contract sections |
| **Source citations** | Every answer includes references to specific contracts, sections, and pages |
| **Confidence scoring** | Answers include a confidence level (high / medium / low) |
| **Follow-up suggestions** | AI suggests related questions you might want to ask |
| **Contract scoping** | Search within a specific contract or across the entire corpus |
| **Session context** | Conversations maintain context across multiple questions |

---

## Administration

### User Management
- Create, update, and deactivate user accounts
- Role assignment: Super-admin, Tenant-admin, Legal, Procurement, Vendor
- Multi-tenant data isolation

### Business Units
- Hierarchical business unit structure within each tenant
- Assign contracts to business units for organizational filtering
- Parent-child relationships for division/team hierarchy
- Admin page for managing business unit hierarchy

### External Users & Portal
- Share contracts with external parties via secure token-based links
- Configurable access levels (view, comment) with expiration dates
- External users can access shared contracts without platform authentication
- Admin page for managing external user access

### Audit Trail
- Comprehensive logging of all user actions
- Search and filter by user, action type, resource, or date range
- Change history for contract metadata

### Workflow Engine
- Define event-driven workflows (e.g., alert on SLA breach, notify on renewal)
- Multi-step workflow orchestration with approvals
- Notification templates with variable substitution
- Retry and timeout configuration

### Scheduler
- Configure background job schedules
- Automate recurring tasks (SLA checks, renewal scans, compliance calculations)

### Master Data
- Reference data management (contract types, clause types, obligation categories)
- Auto-seeded on first startup

### Settings
- Langfuse observability configuration
- System-wide settings management

---

## External Integrations

Connector framework for linking contract intelligence with operational systems.

| Connector | Purpose | Status |
|-----------|---------|--------|
| **ServiceNow** | Import actual SLA performance data for comparison against contracted targets | Stub (router + service + model exist) |
| **Microsoft Teams** | Webhook-based notifications for contract events and alerts | Stub |
| **Milestone Tracker** | Sync milestone status from project management tools | Stub |
| **FX Rate Service** | Currency conversion for COLA adjustments and multi-currency contracts | Stub |
| **Email / SMTP** | Send notifications, survey invitations, and alert emails | Complete |

---

## Related Documentation

| Document | Description |
|----------|-------------|
| [AGENTS.md](./AGENTS.md) | AI agent architecture, orchestration, and agent details |
| [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) | Complete API endpoint reference |
| [ARCHITECTURE_DIAGRAMS.md](./ARCHITECTURE_DIAGRAMS.md) | System architecture and sequence diagrams |
| [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md) | Backend architecture quick reference |
| [PRODUCT_VISION_AND_ROADMAP.md](./PRODUCT_VISION_AND_ROADMAP.md) | Product vision, feature status, and roadmap |
| [TESTING_GUIDE.md](./TESTING_GUIDE.md) | Testing strategy and instructions |
