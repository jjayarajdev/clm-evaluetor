# Evaluetor Heritage vs. Modern Platform — Feature Comparison

This document maps every capability described in the original Evaluetor reference documents (2012-2015) against what has been built in the modern AI-native CLM platform.

## Legend

| Symbol | Meaning |
|--------|---------|
| Y | Fully implemented |
| Y+ | Implemented AND significantly enhanced beyond original |
| ~ | Partially implemented |
| N | Not yet implemented |
| NEW | New capability — no original equivalent |

---

## 1. Contract Management

The original Evaluetor required **manual** digitization, categorization, and enrichment of contracts. The modern platform automates this entirely via AI agents.

| Original Evaluetor Feature | Modern Platform | Status |
|---------------------------|-----------------|--------|
| Scan/copy contract documents into document library | Upload (PDF, DOCX, XLSX, PPTX, PNG, JPEG, TIFF) with drag-and-drop, batch upload | Y+ |
| Digitise contracts | Automated parsing (PDF/DOCX), OCR, text extraction | Y+ |
| Categorise (relate contracts and schedules per relation) | Auto-link detection (parent-child, amendments, renewals) with confidence scoring | Y+ |
| Enrich (add end date, service type, contract-specific info) | AI metadata extraction: type, parties, dates, value, currency, jurisdiction — all automated | Y+ |
| Add Alerts (analyse clauses, register relevant alerts) | AI clause extraction (17+ types), obligation tracking with deadlines, auto-renewal detection | Y+ |
| Central contract storage | PostgreSQL + file storage with tenant isolation | Y |
| Version management of documents | Contract versioning, amendment tracking, version diff comparison | Y |
| Contract commitments translated into business terms | AI-extracted obligations with categories (payment, delivery, reporting, compliance, etc.) | Y+ |
| Control cycles on commitments (daily/weekly/monthly) | Obligation frequency tracking, next compliance due calculation, scheduler-based checks | Y |
| Automated alerts on contract conditions | Notification rules with event triggers, SLA breach alerts, renewal window alerts (30/60/90 days) | Y |
| Contract parties (Principal/Provider roles) | Contract parties with buyer/seller sides, AI-extracted from preamble | Y+ |
| Commitment follow-up assigned to governance teams | Obligation owner assignment, RAG status tracking, compliance evidence uploads | Y |
| Document library with search | Full-text search (keyword + semantic vector search via ChromaDB) | Y+ |
| Contract lifecycle tracking (changes vs. document sections) | Audit trail (100+ action types), contract status history | Y |
| Contracting Policy (standard terms per contract type) | Custom fields per entity type, contract schemas (15 types, 1,235 fields) | Y+ |
| Policy Items (minimum service period, standard payment terms) | Clause extraction identifies payment terms, renewal terms, notice periods automatically | Y+ |

### New Capabilities (no original equivalent)

| Feature | Description |
|---------|-------------|
| NEW AI Contract Q&A | Natural language questions about any contract, RAG-powered with source citations |
| NEW Risk Detection | 10 risk categories, weighted scoring (0-100), auto-classified risk levels |
| NEW Knowledge Graph | Entity/relationship extraction, graph traversal, cross-contract analysis |
| NEW Defined Term Extraction | Automated extraction of defined terms and definitions |
| NEW Preamble Extraction | Automated party identification, recital extraction |
| NEW External Sharing Portal | Token-based external contract access without requiring login |
| NEW Contract Processing Pipeline | 8-stage automated pipeline (parse → chunk → embed → metadata → risk → clauses → obligations → renewals → SLAs) |
| NEW Batch Operations | Bulk upload, batch delete, multi-select |

---

## 2. Relationship Management

This was the core differentiator of the original Evaluetor — managing the "perception gap" between contracted terms and actual stakeholder experience.

| Original Evaluetor Feature | Modern Platform | Status |
|---------------------------|-----------------|--------|
| Organisation structure (My Organisation) | Organizations with type (customer/vendor/partner/internal), size, region, industry | Y |
| Organisation hierarchy (parent/subsidiary) | Parent organization hierarchy, tree views, subsidiary management | Y |
| Client Relationships | Business relationships (type: customer/supplier/partner/joint_venture/reseller/distributor) | Y+ |
| Vendor Relationships | Same model — relationships work bidirectionally | Y |
| Business Relationship (workmode: Provider/Client) | Relationship with governance tier (operational/tactical/strategic/executive) | Y+ |
| Provider Organisation ↔ Client Organisation pairing | Internal org ↔ counterparty org, auto-created by GovernanceBridgeService | Y+ |
| Relationship KPIs with perception scoring | KPIs with 9 categories, 7 measurement types, perception scores, gap analysis | Y |
| Internal perception recording | Perception score submission with approval workflow | Y |
| Voice of the Customer (external perception) | Survey system: templates, instances, external token distribution, response collection | Y |
| Shared dashboarding (Provider & Client view) | External portal with token-based access; health score dashboards | ~ |
| Governance team collaboration | Relationship team members with 7 role types (account_manager, delivery_manager, etc.) | Y |
| Team Agenda (action items per team) | Improvement points assigned to owners with deadlines, priority, status | Y |
| Status Notes per relationship | Relationship status history with trend tracking (improving/stable/declining) | Y |
| Scoring Scales (Red/Amber/Green with symbols) | Scoring scales on KPIs (target/minimum/threshold), RAG status on obligations | Y |
| Real-time relationship monitoring | Health score calculation: risk (30%) + SLA compliance (40%) + obligation health (30%) | Y+ |
| Account dashboard for management | Relationship detail page with health score rings, breakdown scores, team members | Y |
| Transparent supplier relationship | External portal access, shared contract views | ~ |
| Pro-active governance (early issue identification) | AI-detected risks, SLA breach alerts, at-risk renewal identification | Y+ |

### New Capabilities

| Feature | Description |
|---------|-------------|
| NEW Auto-created Relationships | GovernanceBridgeService auto-creates organizations and relationships from uploaded contracts |
| NEW AI-Generated KPIs | Auto-creates KPIs from extracted SLAs |
| NEW Organization Officers | Officers with governance roles, buyer/seller sides |
| NEW Vendor Performance Scoring | A-F grades, at-risk vendor identification, vendor comparison |

---

## 3. Service Management

The original Evaluetor tracked service portfolio and SLA performance manually. The modern platform extracts SLAs via AI and tracks performance automatically.

| Original Evaluetor Feature | Modern Platform | Status |
|---------------------------|-----------------|--------|
| Service Portfolio (per organisation) | Service portfolio CRUD, linked to organizations and relationships | Y |
| Service Portfolio versions | Service type and status tracking | ~ |
| Service Level definitions | SLA extraction (11+ metric types), SLA master data templates | Y+ |
| Service performance tracking (SLA returns) | SLA performance logging, actual vs. target tracking, breach detection | Y |
| Service level measurements (monthly data capture) | SLA measurement period management, historical tracking | Y |
| Service status (RAG indicators) | RAG status on SLAs, consecutive breach counting, severity levels | Y |
| Service performance reports per portfolio | SLA compliance summary, active breach list, portfolio compliance views | Y |
| Performance Indicators (configurable per service) | KPI categories (9 types), measurement types (7 types), target/threshold values | Y |
| Contracts for Portfolio Service (linking services to contracts) | Service-to-relationship linking, contract SLA extraction | Y |
| Views per product group (IaaS, PaaS, SaaS) | Service type categorization (though not cloud-specific groupings) | ~ |
| Register overall service status per customer with escalations | SLA breach alerts with financial impact, escalation workflow | Y |
| Real-time status of service per customer for senior management | Post-signing compliance dashboard, SLA summary widgets | Y |

### New Capabilities

| Feature | Description |
|---------|-------------|
| NEW AI SLA Extraction | Automated extraction of SLAs from contract text (metric type, target, penalty terms) |
| NEW Penalty/Credit Calculation | Financial impact of SLA breaches calculated automatically |
| NEW SLA Benchmarking | Cross-contract SLA comparison and benchmarking |
| NEW ServiceNow Integration | Bi-directional sync of SLA actuals, incidents, change orders |

---

## 4. Improvement Management

The original system tracked improvement actions manually. The modern platform auto-generates improvements from AI-detected gaps.

| Original Evaluetor Feature | Modern Platform | Status |
|---------------------------|-----------------|--------|
| Improvement actions from contract commitments | Improvement points with source tracking (gap, SLA_breach, review, feedback, audit) | Y |
| Improvement actions from Relationship KPIs | Generate improvements from KPI perception gaps (automated) | Y+ |
| Improvement actions from Service KPIs | Improvements created from SLA breaches and risk analysis | Y+ |
| Actions distributed to governance teams | Owner assignment, priority (low/medium/high/critical), status tracking | Y |
| "Go-to-green" focused improvement plans | Status workflow (open → in_progress → blocked → completed/cancelled) | Y |
| Clear ownership, deadlines, status tracking | Due date management, action items per improvement point | Y |
| Continuous improvement based on actual issues | AI risk detection feeds high/critical risks → improvement points (via GovernanceBridgeService) | Y+ |
| Dedicated focus on improvement actions | Improvements page with filtering by status, priority, source | Y |

### New Capabilities

| Feature | Description |
|---------|-------------|
| NEW Auto-Generated Improvements | GovernanceBridgeService auto-creates improvement points from AI-detected high/critical risks |
| NEW Gap-to-Improvement Pipeline | One-click generation of improvements from KPI perception gaps |

---

## 5. Risk Management

The original Evaluetor had a manual risk register. The modern platform has fully automated risk detection across 10 categories.

| Original Evaluetor Feature | Modern Platform | Status |
|---------------------------|-----------------|--------|
| Risk register | AI-powered risk detection: 10 categories, weighted scoring (0-100) | Y+ |
| Risk categories | Unlimited liability, broad indemnification, weak termination, auto-renewal traps, IP risk, confidentiality weakness, data protection gaps, jurisdiction risk, ambiguous terms, missing protections | Y+ |
| Risk scoring | Risk levels (low/medium/high/critical), weighted risk score | Y+ |
| Risk alerts | Risk-based alerts, at-risk contract identification | Y |
| Risk mitigation tracking | Improvement points auto-created from high/critical risks | Y+ |
| Validate deviations from standard product (Opportunity/Bid) | Compliance gap detection against industry-specific rules | Y+ |
| Define important product standards for risk checking | Compliance rule management, industry detection, regulatory obligation tracking | Y+ |

### New Capabilities

| Feature | Description |
|---------|-------------|
| NEW AI Risk Detection Agent | Fully automated, no manual risk entry needed |
| NEW Industry-Specific Compliance | Auto-detected industry with compliance rules matching |
| NEW Regulatory Obligation Extraction | Audit rights, change control, deviation reporting, recall obligations |
| NEW Risk Distribution Analytics | Dashboard visualizations of risk across portfolio |

---

## 6. Opportunity Management

The original Evaluetor had a full opportunity/bid management module for sales pipeline tracking. This is **not** part of the modern platform's scope.

| Original Evaluetor Feature | Modern Platform | Status |
|---------------------------|-----------------|--------|
| Maintain list of opportunities | Not implemented | N |
| Automatic import from external source | Not implemented | N |
| Maintain sales status of opportunities | Not implemented | N |
| Maintain list of supporting sales actions | Not implemented | N |
| Link Opportunity to service portfolio product | Not implemented | N |
| Define customer contract (from opportunity) | Not implemented | N |
| Define important contract commitments to monitor | Partially — obligations are extracted post-upload | ~ |
| Transfer signed contract to Order-to-Cash list | Not implemented | N |
| Opportunity types (ATOS lead, etc.) | Not implemented | N |

**Assessment:** Opportunity/bid management was specific to the original Evaluetor's use case as a provider-side tool for outsourcing companies managing their sales pipeline. The modern platform focuses on contract intelligence and post-signing governance, which serves both buy-side and sell-side users. Pre-signing pipeline management is intentionally out of scope.

---

## 7. Financial Management

The original had financial tracking around product ROI and customer cost models. The modern platform has contract-level financial tracking but not product-level P&L.

| Original Evaluetor Feature | Modern Platform | Status |
|---------------------------|-----------------|--------|
| Contract value tracking | Contract value + currency, total portfolio value aggregation | Y |
| Register product investment | Not implemented | N |
| Actual total cost and revenue per customer product | Not implemented | N |
| Monthly incremental product revenues and costs | Not implemented | N |
| Report on incremental revenue, cost and profit per product | Not implemented | N |
| Customer Cost Model registration | Not implemented | N |
| Report on Customer revenue, cost and profit per product | Not implemented | N |
| Billing and payment status | Payment terms extracted from contracts (clause type) | ~ |

**Assessment:** Product-level P&L, cost model tracking, and revenue management were Canopy-specific requirements for their cloud services business. The modern platform tracks contract financial exposure but doesn't provide a product profitability module. This could be considered for a future phase if customer demand warrants it.

---

## 8. Reporting & Dashboards

| Original Evaluetor Feature | Modern Platform | Status |
|---------------------------|-----------------|--------|
| Management Dashboard (executive overview) | ModernDashboardPage with role-specific views (Admin/Legal/Procurement) | Y+ |
| Account status overview | Relationship health score with breakdown (compliance/SLA/perception/improvement) | Y |
| Contract alerts overview | Notification rules, SLA alerts with severity and financial impact | Y |
| High-level overview of all contract/relationship statuses | Contract summary cards, status distribution, risk distribution | Y |
| Drill-down to underlying issues | Contract detail tabs, obligation detail, clause detail pages | Y |
| Service Portfolio Report (SPI scores per service) | SLA compliance summary, portfolio compliance views | Y |
| Real-time status dashboards | Post-signing compliance dashboard, renewal calendar | Y |
| Checklist dashboards (Ready to Sell / Ready to Deliver) | Not implemented (checklist concept not used) | N |
| Management reporting (overall status for management) | Super admin dashboard (total tenants, users, contracts, value, plan distribution) | Y |

### New Capabilities

| Feature | Description |
|---------|-------------|
| NEW AI-Powered Visualizations | Query page generates bar charts, pie charts, timelines, tables, stat cards from natural language |
| NEW Compliance Trend Reports | Weekly/monthly compliance trend visualization with CSV/Excel export |
| NEW Vendor Scorecards | A-F performance grades across vendors with comparison |
| NEW Renewal Calendar | Visual renewal windows with ICS calendar export |
| NEW Risk Distribution | Portfolio-wide risk analysis dashboard |

---

## 9. Security & Access Control

| Original Evaluetor Feature | Modern Platform | Status |
|---------------------------|-----------------|--------|
| Three-tier security (access, role-based, personal involvement) | JWT auth + role-based access (6 roles) + tenant isolation + team membership | Y+ |
| Access control | Login/token-based authentication | Y |
| Role-based permissions | admin, legal, finance, operations, vendor, super_admin | Y+ |
| Personal involvement (team membership) | Relationship team members, obligation owners | Y |
| Expert user and system administrator roles | Admin and super_admin roles with separate UI sections | Y |
| User subscription management | Tenant-based user management with contract limits per plan | Y |
| External user access (Clients/Suppliers) | External users with company info, token-based portal access, contract sharing | Y |

---

## 10. Technology Platform

| Original Evaluetor | Modern Platform | Assessment |
|--------------------|-----------------|------------|
| Microsoft SharePoint | FastAPI (Python) + React (TypeScript) | Complete rewrite, modern stack |
| SQL Server | PostgreSQL + ChromaDB (vectors) | More capable, vector search added |
| SaaS on hosted SharePoint | Docker Compose on AWS EC2 | Cloud-native deployment |
| SharePoint full-text search | ChromaDB semantic search + PostgreSQL full-text | Far more capable |
| MS Office integration (Outlook, Word) | ServiceNow integration, Teams/Slack notifications | Different integration targets |
| SharePoint Apps architecture | REST API + SPA architecture | Modern standards |
| Standard internet browsers | Standard internet browsers | Same |
| Web services for DB access | 315+ REST API endpoints | Comprehensive API |

---

## 11. Implementation & Consulting

The original Evaluetor included a consulting practice. These concepts inform but don't directly map to software features.

| Original Concept | Modern Platform Equivalent | Status |
|-----------------|---------------------------|--------|
| Contract Management Scan (maturity assessment) | Not implemented as a feature | N |
| Capability Maturity Model (Control → Manage → Cooperate) | Could be modelled as a KPI category | ~ |
| 10-area measurement questionnaire | Survey system could support this | ~ |
| Improvement project identification from scan results | Improvement management from KPI gaps | Y |
| Account improvement main process | Relationship governance workflow | Y |
| Governance structure (Steering Group, Work Group) | Relationship governance tiers (operational → executive) | Y |

---

## 12. Process Coverage (Canopy Requirements)

How the six Canopy CDM processes map to the modern platform:

| Canopy Process | Original Evaluetor | Modern Platform | Status |
|---------------|-------------------|-----------------|--------|
| **Portfolio Management** (Ready to Sell) | Checklists, service portfolio, SLA definitions | Service portfolio management, SLA master data | ~ |
| **Opportunity & Bid Management** | Full opportunity pipeline, bid tracking | Not in scope | N |
| **Order-to-Cash** (Customer Onboarding) | Ready to Deliver checklists, reporting | Contract upload + processing pipeline | ~ |
| **Usage-to-Cash** (Service Delivery) | SLA performance, service status, escalations | SLA tracking, breach alerts, post-signing compliance | Y |
| **Product ROI** | Product investment, cost/revenue per product | Not in scope | N |
| **Customer Cost Model vs. Actual** | Cost model registration, profitability reporting | Not in scope | N |

---

## Summary Scorecard

### By Original Functional Pillar

| Pillar | Coverage | Assessment |
|--------|----------|------------|
| **Contract Management** | 16/16 features | Y+ Fully implemented + AI automation |
| **Relationship Management** | 16/17 features | Y Comprehensive with AI enhancements |
| **Service Management** | 11/12 features | Y Strong, AI-extracted SLAs |
| **Improvement Management** | 8/8 features | Y+ Enhanced with AI-generated improvements |
| **Risk Management** | 7/7 features | Y+ Fully automated via AI |
| **Opportunity Management** | 1/9 features | N Intentionally out of scope |
| **Financial Management** | 2/8 features | ~ Contract-level only, no product P&L |
| **Reporting & Dashboards** | 8/9 features | Y Role-specific with AI visualizations |
| **Security & Access** | 7/7 features | Y+ Enhanced with multi-tenant isolation |

### Overall

| Metric | Count |
|--------|-------|
| Original features fully implemented or enhanced | **69 / 93** (74%) |
| Original features partially implemented | **8 / 93** (9%) |
| Original features not implemented | **16 / 93** (17%) |
| New capabilities with no original equivalent | **20+** |

### What the Modern Platform Does Better

1. **AI Automation** — The original required manual data entry for everything. The modern platform has 9 AI agents that automatically extract metadata, clauses, obligations, risks, SLAs, and renewals from uploaded contracts.

2. **Governance Bridge** — Auto-creates organizations, relationships, KPIs, improvement points, and health scores from contract data. The original required manual setup of every governance entity.

3. **Risk Intelligence** — The original had a manual risk register. The modern platform detects 10 risk categories automatically with weighted scoring.

4. **Semantic Search** — Vector embeddings enable natural language queries across the entire contract corpus, versus SharePoint's keyword-only search.

5. **Multi-Tenant Architecture** — Row-level tenant isolation supports unlimited organizations on a single platform, versus SharePoint's site-collection-per-client model.

6. **Contract Q&A** — Users can ask questions in natural language and get sourced answers with visualizations. This capability didn't exist in the original.

### What the Original Had That's Missing

1. **Opportunity/Bid Management** — Pre-signing sales pipeline. Intentionally out of scope for a CLM-focused platform.

2. **Product P&L** — Product-level cost/revenue/profit tracking. Was Canopy-specific for cloud services business management.

3. **Checklists** — "Ready to Sell" and "Ready to Deliver" structured checklists. Could be modelled as workflow steps if needed.

4. **Contract Management Maturity Scan** — Consulting tool for assessing organizational maturity. Could be implemented as a survey template.

5. **Shared Dashboard** — The original provided identical dashboards to both parties (provider and client). The external portal provides read-only contract access but not full shared governance dashboards.

---

## 13. Screen-by-Screen UI Comparison

The original Evaluetor screenshots (from Appendix D and PPTX presentations) reveal specific UI patterns. Below is a detailed comparison of every visible screen against the modern platform.

### 13.1 Navigation Structure

**Original (SharePoint):**
- Top navigation bar: `Home | 1 My Evaluetor | 2 Corporation | 3 Organisation | 4 Business Relationship | 5 Team | 6 Security | 7 Settings | 8 Configuration`
- Three main tabs: `My Organisation | My Clients | My Evaluetor`
- Left sidebar: tree of Relationship/Team memberships per account

**Modern Platform:**
- Collapsible sidebar with role-filtered navigation sections:
  - Core: Dashboard, Contracts, Upload, Ask AI
  - Post-Signing: Compliance, Renewals, Vendors, Reports
  - Governance: Organizations, Relationships, KPIs, Service Portfolio, Improvements, Surveys, KPI Approvals
  - Admin: Users, Business Units, External Users, Integrations, SLA Config, Milestone Config, Scheduler
  - Super Admin: Platform Dashboard, Tenants, Global Users, Custom Fields
- Top header with user menu, logout

**Assessment:** Y+ Modern navigation is deeper (more sections) and role-aware. The original's flat 8-tab structure is replaced by a hierarchically organized sidebar that hides irrelevant sections per role. However, the original's "My Evaluetor" personal view (bringing all YOUR actions and alerts together) is a pattern worth noting — we have dashboard widgets for this but not a dedicated "my tasks" aggregation page.

---

### 13.2 Team Collaboration Screen (Appendix D, p.3)

**Original screen shows:**
- **Officers & Organisation** header with user profile (photo, name "Koos van den Berge", title "Chief BDO")
- **Team Memberships** panel (left): tree of all relationship/team memberships, e.g.:
  - `Canopy > ABN/Amro Account Service Team`
  - `Canopy > Dell/Westcon Account Team`
  - `Canopy > Atos/OnBoarding Hosting mBlock R1.1 BU Airways`
  - `Ready to Sell upon SharePoint R2.1`
- **TEAM** panel (right): Team name, mission, team agenda subjects
- **Team Agenda Subjects** table with columns: Effective Date, Label, Stage, Description/SLA/Level Status, Source, Assigned To
  - Example: "1.3 Sales Presentation", status "Completed", "Team action"
  - Example: "2.7 Deliver SaaS Description", "In Progress"
- **Status Notes** section below with date, label, description, document reference, quantity, units, RAG indicator

**Modern Platform equivalents:**
- **Organization Officers**: `OrganizationDetailPage` with officers list (name, role, side)
- **Team Memberships**: `RelationshipDetailPage` → Team Members section (role types: account_manager, delivery_manager, etc.)
- **Team Agenda**: `ImprovementsPage` with improvement points (status, priority, owner, due date)
- **Status Notes**: `RelationshipHistoryEntry` with trend tracking

| Original Element | Modern Equivalent | Status |
|-----------------|-------------------|--------|
| User profile with photo | User name/role in header, no photo | ~ |
| Team membership tree (left sidebar) | Relationships list page, filter by team member | ~ |
| Team agenda with stages | Improvement points with status workflow | Y |
| Status notes with RAG + document links | Relationship status history with trend + obligation RAG | Y |
| Delivery "Comfort" indicator (progress bars) | Not implemented — no visual progress bars for deliverables | N |

---

### 13.3 Service Portfolio Screen (Appendix D, p.4)

**Original screen shows:**
- **Organisation** page for "Senority Test Organisation"
- **Portfolio Services** panel (left): list of services per organization (e.g., "SAP Maintenance")
  - Expandable tree: `Applications > SAP Maintenance`, `Senority Test Organisation > Desktop management`
- **Portfolio Service Details** panel (right):
  - Value Proposition (long text)
  - Competitive Position (long text)
  - Target Customers
  - Scope
  - Deal Characteristics
- **Performance Indicators** table: Seq, Description, Unit, Scoring Scale (with colored dots)
  - Example: "Problem resolution time" in Hours, with red/amber/green dots
  - Example: "Incident resolution time" in Hours
- **Scoring Scale** table: Sequence, Operator, Value, Symbol (colored circle), Class
  - Example: Sequence 1, "--", Value 4, orange circle, "Very Bad"
- **Contracts for Portfolio Service** table: Client, Contract, Description And Status, Quantity, Units, Service, Delivery & Control Status (RAG bars)
  - Example: "ABN AMRO Bank", "Desktops & Apps Dev", "Service: SAP Maintenance...", with red/green status bars

**Modern Platform equivalents:**
- **Service Portfolio page** (`ServicePortfolioPage`): CRUD for services with type, status, organization linking
- **Service-to-Relationship linking**: link services to relationships
- **SLA definitions**: extracted via AI from contracts (metric type, target, unit, warning threshold)
- **Performance tracking**: SLA compliance summary, breach detection

| Original Element | Modern Equivalent | Status |
|-----------------|-------------------|--------|
| Service portfolio per organization | ServicePortfolio model with org linking | Y |
| Portfolio service details (value prop, scope, etc.) | Service has name, type, status, description — but not value proposition/competitive position fields | ~ |
| Performance indicators per service with scoring scales | KPIs with categories + SLAs with targets/thresholds | Y |
| RAG scoring scale (colored dots/circles) | RAG status on obligations + SLA breach severity levels | Y |
| Contracts linked to portfolio service | Services linked to relationships (which have contracts) | Y |
| Delivery & Control Status (multi-color progress bars) | Health score rings (single composite score) | ~ |

---

### 13.4 Opportunity & Business Relationship Screen (Appendix D, p.6)

**Original screen shows:**
- **Business Relationship** header: `workmode=Provider`, Provider Organisation: **Canopy**, Client Organisation: **Achmea** (with logos)
- **Opportunity** table: Opportunity name, Contract Type, Expected dates, Sales Phase, Prob%, Prospect, Total Value, Annual Value, Cur.Year Value, Expected Contract Sign Date, Opportunity Type
  - Example: "CEW Sales opportunity to sell CEW to Achmea", type "Canopy CEW service contract", "2.Qualified (70%)", prospect "Achmea", total value 150,000, signed "15-dec-2014", "1 ATOS lead"
- **Commitments (Contract Scope)** table: Label, Full Description, Deadline, Document Reference, Warning, Status
  - Example: "CEW", "Commitment: CEW service", with amber warning indicator
- **Alert Rules** table: Label, Description, Severity, AlertRule, AlertDate
- **Contracting Policy** section (lower screenshot):
  - Organisation: "Canopy"
  - Policy list with Label, Description, ContractType
  - Policy Items with Label, Description, Preferred Text, ContractingPolicy
  - Example: "Minimum Service period" = "12 months with automatic 12 months extensions after contract expiry date"
  - Example: "Standard payment terms" = "Monthly payments within 30 days after invoice receipt"

**Modern Platform equivalents:**

| Original Element | Modern Equivalent | Status |
|-----------------|-------------------|--------|
| Opportunity tracking (sales pipeline) | Not implemented | N |
| Business relationship Provider ↔ Client with logos | Business Relationships page, internal org ↔ counterparty, no logos | ~ |
| Commitments (contract scope) with deadline/warning | Obligations with deadline, RAG status, compliance tracking | Y+ |
| Alert Rules per relationship | Notification rules with event triggers, SLA breach alerts | Y |
| Contracting Policy with preferred contract terms | Not implemented as a policy template feature — but clauses are extracted by AI | ~ |
| Policy Items (minimum service period, payment terms) | AI clause extraction identifies these automatically from contract text | Y+ |

---

### 13.5 Contract List & Parties Screen (Appendix D, p.7)

**Original screen shows:**
- **Contracts** table within a Business Relationship: Contract name, Counterparty, Contract Type, Start Date, End Date, Value, Extensions, Library, Delivery & Control Status (RAG bars), Progression
  - Example: "CIS an ASC (Service contract for delivery CIS on ASC)", Counterparty "Achmea", type "Canopy service combination contract", Start 01-jan-2014, End 01-jan-2016, Value 850K, Extensions "indefinite with 24 months", multi-color RAG bars
  - Example: "mBlock R1.1 (Service contract for delivery of mBlock R1.1)", Value EUR 135K, Extensions "indefinite with 12 months"
- **Contract Parties** table: Name, Company, Hereafter Name, Roletype In Contract
  - Example: "Achmea" → role "Principal" / "Principal"
  - Example: "Canopy" → role "Provider" / "Provider"

**Modern Platform equivalents:**

| Original Element | Modern Equivalent | Status |
|-----------------|-------------------|--------|
| Contract list within relationship context | Contracts page with counterparty filter; relationship detail shows linked contracts | Y |
| Contract Type (service combination contract, etc.) | 15 contract types (MSA, NDA, SOW, SLA, etc.) — AI-detected | Y+ |
| Start/End dates | Effective/Expiration dates — AI-extracted | Y+ |
| Contract Value with currency | Contract value + currency (ISO code) — AI-extracted | Y+ |
| Extensions (indefinite with X months) | Auto-renewal detection, renewal term, notice period — AI-extracted | Y+ |
| Delivery & Control Status (multi-segment color bars) | Risk level (low/medium/high/critical) + health score | ~ |
| Progression indicator | Processing status (pending/processing/completed/failed) — different concept | ~ |
| Contract Parties with Roletype (Principal/Provider) | Contract parties with role (buyer/seller), side — AI-extracted from preamble | Y+ |

---

### 13.6 Usage-to-Cash / Service Performance Screen (Appendix D, p.9)

**Original screen shows:**
- **Services** table within relationship: Label, Description, Quantity, Units, Service, Discipline, Document Reference, Delivery & Control Status (RAG bars), Attention Level, Status
  - Example: "Service Commitment: ASE service", discipline "Service Performance"
  - Example: "Service Commitment: Continuous mBlock R1.1 service", with red/yellow/green bars
  - Example: "Service Commitment: OS", attention level warning icon with note "29 Sep 2014: Service under control, Customer reviewing, as committed"
- **Service Level Details** table: Full Description, Label, Status
  - Example: "SPI: Incident resolution time Severity 1 within set time...", Label "Incident resolution time Severity 1", Status with RAG dots and dates
  - Example: "SPI: Service availability: Percentage of problem free usage per reported month...", Label "Service availability"
- **Service Level Measurements** table: Note Date, Label, Description, Quantity, Units, RAG (colored dot)
  - Monthly entries: "August SLR" = 97 (green), "July SLR" = 80 (green), "June SLR" = 86 (amber), "May SLR" = 68 (amber), "April SLR" = 37 (red), etc.
- **Service Status** table: Note Date, Label, Description, RAG
  - Status notes with narrative: "Service under control, Customer reviewing, as committed" (green)
  - "Better grip on severity 1 resolution, Availability still a bit too low" (amber)
  - "Many reported severity 1 incidents. Not enough capacity to process all events in time..." (red)

**Modern Platform equivalents:**

| Original Element | Modern Equivalent | Status |
|-----------------|-------------------|--------|
| Services per relationship with RAG bars | SLAs per contract with compliance rate, breach severity | Y |
| Attention Level (warning icon with notes) | SLA alerts with severity, description, financial impact | Y |
| Service Level Details (SPI definitions with thresholds) | SLA model: metric_type, target_value, warning_threshold, severity | Y |
| Service Level Measurements (monthly numeric values with RAG) | SLA performance logging: actual values, breach detection, consecutive breach counting | Y |
| Service Status (narrative notes with RAG) | Relationship status history with trend (improving/stable/declining) | Y |
| Monthly SLR numeric tracking (97, 80, 86, 68, 37...) | SLA compliance rate tracking, measurement period management | Y |
| Color-coded RAG dots per measurement period | SLA breach severity levels, compliance percentage | Y |

---

### 13.7 Service Portfolio Report (Appendix D, p.10)

**Original screen shows:**
- **352 Service Portfolio Report** (printable format)
- Report per service (e.g., "Service: SAP Maintenance"):
  - **SPI / Source** with relationship context (e.g., "KPN > ABN Amro | Desktops & Apps Dev")
  - **SPI description** with measurement rules (e.g., "Problem resolution time: Date is taken as soon as problem incident report and resolution in hours")
  - **SPI Score**: numeric value (e.g., 100, 300)
  - **Remarks** column
  - **RAG** indicator (green/red dot)
  - **Compare to portfolio** column with mini bar chart showing actual vs. portfolio benchmark
  - **Bhl Scale** column

**Modern Platform equivalents:**

| Original Element | Modern Equivalent | Status |
|-----------------|-------------------|--------|
| Formatted service portfolio report | SLA compliance summary, portfolio compliance views | Y |
| SPI per relationship per service | SLAs per contract with compliance rates | Y |
| Compare to portfolio (benchmark bar chart) | SLA benchmarking service (cross-contract comparison) | Y |
| Printable report format | Reports page with CSV/Excel export — but not a formatted PDF/print report | ~ |
| Mini bar charts inline | Dashboard visualizations, but not inline in SLA tables | ~ |

---

### 13.8 Executive Dashboard Screens (PPTX presentations)

**Original screens described in presentations:**
- **Management Dashboard**: High-level overview of all relationships with drill-down
- **Contract Managers Dashboard**: "Maximize the return on contracts" — contract-centric view
- **Governance Team Collaboration**: Shared view between Provider & Client
- **My Evaluetor**: Personal aggregation of all YOUR actions, alerts, teams
- **Contract alerts overview**: List of alerts across all contracts

**Modern Platform equivalents:**

| Original Screen | Modern Equivalent | Status |
|----------------|-------------------|--------|
| Management Dashboard (executive overview) | ModernDashboardPage with role-specific widgets (Admin/Legal/Procurement) | Y |
| Contract Managers Dashboard | ContractsPage + ContractViewPage with intelligence tabs | Y |
| Governance Team Collaboration (shared Provider/Client) | External portal (read-only), no full shared governance dashboard | ~ |
| "My Evaluetor" (personal todo aggregation) | Dashboard shows recent activity, but no dedicated "My Tasks" view aggregating all obligations/improvements assigned to current user | ~ |
| Contract alerts overview | SLA alerts page, notification rules — but no single unified alerts inbox | ~ |

---

### 13.9 Key UI Patterns Missing from Modern Platform

Based on the screenshot analysis, these specific UI patterns from the original have no direct equivalent:

| Original Pattern | Description | Priority |
|-----------------|-------------|----------|
| **"My Evaluetor" personal hub** | Single page showing all YOUR assigned actions, team agendas, alerts, obligations across all relationships | High — high-value UX pattern |
| **Multi-segment RAG bars** | Delivery & Control Status shown as horizontal bars with multiple colored segments (red/amber/green proportions) | Medium — visual pattern |
| **User profile photos** | Officer/user photos in team views | Low — cosmetic |
| **Contracting Policy templates** | Reusable standard terms (min service period, payment terms) that can be applied to new contracts and checked for deviation | Medium — could use compliance rules |
| **"Progression" indicator** | Visual progress bar for contract lifecycle stage | Low — replaced by processing status |
| **Unified Alerts inbox** | Single view of all alerts (contract, SLA, compliance, renewal) across the entire portfolio | High — operational UX pattern |
| **Printable service portfolio reports** | Formatted, printable reports with inline charts and benchmark comparisons | Medium — need formatted export |

---

## Summary: What the Screenshots Reveal

The original Evaluetor UI, while built on SharePoint, had some sophisticated interaction patterns:

1. **Relationship-centric navigation** — Everything was organized around the business relationship context (Provider ↔ Client), with contracts, services, opportunities, and improvements nested within that context. The modern platform has relationship pages but the primary navigation is contract-centric.

2. **Dense information panels** — The original packed many data sections into single pages (opportunities, commitments, alert rules, contracting policy all on one relationship page). The modern platform separates these into distinct pages, which is cleaner but requires more navigation.

3. **Multi-color status bars** — The original used multi-segment horizontal bars showing proportions of red/amber/green across multiple metrics. The modern platform uses single RAG indicators and health score rings, which are cleaner but less information-dense.

4. **Personal aggregation** — "My Evaluetor" was a key productivity feature that brought all your action items into one view. The modern dashboard partially does this but could benefit from a dedicated "My Tasks" page.

5. **Shared governance views** — The original was designed for both parties (provider AND client) to see the same data through the same interface. The modern platform's external portal is read-only — it doesn't support the collaborative governance dashboard concept where both parties interact.

---

*Comparison based on reference documents (2012-2015) vs. codebase as of April 2026.*
