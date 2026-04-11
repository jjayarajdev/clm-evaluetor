# Evaluetor Heritage Reference

This document synthesizes all materials from the `reference-docs/` directory — the original Evaluetor product documentation, sales presentations, contractual templates, and requirements modelling from 2012-2015. It provides the foundational context for the modern AI-native CLM platform being built today.

## Source Documents

| Document | Date | Type | Description |
|----------|------|------|-------------|
| Senority Introduction to Genpact | Apr 2012 | PPTX | First sales presentation, introduces Evaluetor concept |
| Genpact Heineken - Roadmap to Success | Oct 2012 | PPTX | Contract management maturity model for Heineken |
| Commercial Presentation | May 2014 | PPTX | Generic sales deck with Allen & Overy partnership |
| Business Case - ATOS v1.0 | Sep 2014 | PPTX | Business case for Atos implementation |
| Proposal Evaluetor and Implementation for Canopy | Oct 2014 | PDF | Full implementation proposal (19 pages) |
| Appendix B - General Terms and Conditions for Canopy | Sep 2014 | PDF | Standard SaaS T&Cs (9 pages) |
| Appendix C - Draft EUA for Canopy | Sep 2014 | PDF | Usage agreement with pricing (6 pages) |
| Appendix D - Requirements Modelling for Canopy | Oct 2014 | PDF | Functional requirements mapping (12 pages) |
| Introduction to Evaluetor for TNT | Mar 2015 | PPTX | Sales presentation for TNT Express |
| Evaluetor demo to TNTE | Jun 2015 | PPTX | Demo follow-up for TNT Express |

---

## 1. Company: Senority B.V.

**Senority B.V.** was the company behind Evaluetor, headquartered in Rotterdam, The Netherlands.

- **Address:** Boompjes 680, 3011 XZ Rotterdam
- **Chamber of Commerce:** 52396126
- **Phone:** +31 (0)10 217 0118
- **Website:** www.senority.nl
- **Key People:**
  - **Enrico de Boer** — Managing Partner (2012)
  - **Steven Visser** — Managing Partner
  - **Rolf van Straaten** — Managing Partner
  - **Rob van Leeuwen** — Managing Partner
  - **Johan van Campen** — (Atos engagement)
  - **Jan Aernout** — (TNT engagement)

**Founding thesis:** "Founded by a group of people with deep experience in the services industry who collectively have been challenged over the years because there is no simple 'solution' that can help complex client-supplier relationships."

**Mission:** Assist outsourcing companies in improving customer retention through a solution built on three pillars: software (Evaluetor), consulting processes, and implementation services.

---

## 2. The Evaluetor Concept

### 2.1 Core Value Proposition

Evaluetor was designed to make business relationships **"Transparent, Measurable, and Actionable"** by bridging the gap between contract documents and day-to-day operational reality.

The platform addressed three fundamental gaps in complex business relationships:

| Gap | Description | How Evaluetor Closed It |
|-----|-------------|------------------------|
| **Commercial Gap** | Disconnect between contracted terms and actual delivery | Commitments tracking, compliance monitoring |
| **Delivery Gap** | Disconnect between service expectations and performance | SLA management, performance indicators |
| **Information Gap** | Disconnect between perception and facts | KPI perception scoring, dual-view dashboards |

### 2.2 Information Model

Evaluetor combined two data streams:

- **Fact-based data:** Contract commitments, SLA measurements, financial data, operational metrics (from ERP, HR, F&A, CRM systems)
- **Perception-based data:** KPI scores from internal teams and external stakeholders (Voice of the Customer)

This dual approach — equating *reality with perception* — was the defining innovation.

### 2.3 Application Components

```
Evaluetor
├── Organisation
│   ├── Client Relationships
│   │   ├── Contracts
│   │   ├── Projects
│   │   └── Services
│   └── Vendor Relationships
│       ├── Contracts
│       ├── Projects
│       └── Services
├── Business Structures
│   ├── Performance Indicators
│   ├── Scoring Scales
│   ├── Score
│   ├── Commitments, Deliverables & Risk
│   ├── Status
│   └── Alert Rules
├── Governance
│   └── Status and Collaboration
├── Facts on Operations
│   ├── ERP
│   ├── HR
│   ├── F&A
│   └── CRM
└── Perceptions of Involved People
    ├── Internal
    └── External
```

### 2.4 Contract Lifecycle Support

Evaluetor supported the full contract lifecycle:

```
Contracting → Execution → Close/Renewal
     │              │            │
     │         Scope change      │
     │         Dispute           │
     │         Add-on            │
     │         Complaint         │
     │         Legislation change│
     │         Dissatisfaction   │
     │         New requirement   │
     └──────────────────────────→│
```

The process for getting contracts into Evaluetor:
1. **Digitise** — Scan/copy contract documents into document library
2. **Categorise** — Electronically relate contracts and schedules per relation
3. **Enrich** — Add details (end date, service types, contract-specific info)
4. **Add Alerts** — Analyse clauses and register relevant alerts

---

## 3. Four Functional Pillars

### 3.1 Contract Management

- Central storage and version management of all contract documents
- Contract commitments translated into business terms
- Control cycles defined on commitments for frequent monitoring
- Automated alerts on contract conditions (deadlines, renewals, obligations)
- Risk assessment and monitoring via Risk Register
- Lifecycle tracking: monitors changes on commitments vs. contract document sections

**Workflow:**
```
Contracts → Commitments → Control Cycle → Status Updates
                                              │
                              Frequency: Daily/Weekly/Monthly/Once/Alert-based
```

### 3.2 Service Management

- SLA tracking with performance indicators
- Service level measurements (monthly data capture)
- Service status tracking with RAG (Red/Amber/Green) indicators
- Service performance reports per portfolio service
- Views per product group (IaaS, PaaS, SaaS)
- Service escalation management

### 3.3 Relationship Management

- Business relationship modelling (Provider ↔ Client)
- Relationship KPIs with perception scoring
- Governance team collaboration (internal and external)
- Shared dashboards between parties
- Transparent supplier relationship with aligned expectations
- Pro-active governance and real-time relationship monitoring

### 3.4 Improvement Management

- Continuous improvement actions driven by:
  - Contract commitments
  - Relationship KPIs
  - Service KPIs
- Improvement actions distributed across governance teams
- "Go-to-green" focused improvement plans
- Clear ownership, deadlines, and status tracking

**Flow:**
```
Commitment ──→ Improvement Actions ──→ Governance Team A
                                   ──→ Governance Team B
Relationship KPIs ──→ Improvement  ──→ Governance Team C
                      Actions      ──→ Governance Team D
Service KPIs ──→──────────────────────→ Governance Team E
```

---

## 4. Key Clients and Case Studies

### 4.1 Client Engagements

| Client | Industry | Year | Context |
|--------|----------|------|---------|
| **Genpact** | IT Outsourcing | 2012 | Pilot with Staples account; service excellence program |
| **Heineken** | FMCG / Beverages | 2012-2013 | Contract management maturity assessment across OpCos |
| **Allen & Overy** | Law Firm | 2014 | Partnership for electronic contract services |
| **Atos / Canopy** | IT Services / Cloud | 2014 | Full implementation for cloud services business |
| **TNT Express** | Logistics | 2015 | Vendor Management Office support |

### 4.2 Proven Results

**Case Study 1** (18 months post-implementation):
- Outsourcing Recommendation Index increased **+14 points**
- Number of Promoters increased **+21%**
- Revenue de-risked by **11%**
- Add-on business growth of **6%** within existing portfolio

**Case Study 2** (3-year results):
- Customer retention increased from **53% to 82%**
- Referenceability increased **+20%**
- Win rate increased **+10%**
- Operational cost decreased **-5%**

### 4.3 Projected Business Value

| Metric | Improvement |
|--------|-------------|
| Return on contract base | +3-5% |
| Sourcing satisfaction | +10-25% |
| Supplier delivered value | +15% |
| Operational cost reduction | -5% |
| Operational risk reduction | -20% |
| Renewal rate & references (ORI) | +20% |

---

## 5. Heineken Contract Management Maturity Model

Senority developed a **Contract Management Scan** — a capability maturity model with three levels:

### Level 2: Control
- Central contract registration and storage
- Contract administration is operational with clear responsibilities
- Central registration of financial commitments in general ledger
- Suppliers consulted incidentally

### Level 3: Manage
- Service delivery according to agreed service levels
- Contract management integrated into sourcing strategy and procurement
- Incident, Problem, and Risk management processes operational
- Periodic evaluation of contracts and suppliers

### Level 4: Cooperate
- Focus on continuous improvement and exploration of new cooperation
- Sourcing strategy aims at long-term cooperation
- Governance structure guarantees optimal, durable cooperation
- Excellent working relations between key players at every management level
- Supplier management governed by corporate strategy

The scan measured **10 areas**:
1. Organization
2. Roles & Responsibilities
3. Contract Administration
4. Compliance Management
5. Performance Management
6. Risk Management
7. Relationship Management
8. Financial Management
9. Change Management
10. Improvement Management

### Savings Potential (Heineken)

| Project | Timeline | Savings |
|---------|----------|---------|
| Supplier Development | 3-12 months | 2-5% cost reduction |
| Contract Development | 1-12 months | 5-20% from captured discounts |
| Performance Improvement (Evaluetor) | 6-12 months | 3-8% cost savings |

---

## 6. Canopy/Atos Implementation Proposal

### 6.1 Context

Canopy was the cloud services subsidiary of Atos. The proposal positioned Evaluetor as a bridge between Atos's client-oriented processes and Canopy's product-oriented approach, supporting four main business processes:

**Operational Processes:**
1. **Portfolio Management** (Ready to Sell)
2. **Opportunity & Bid Management**
3. **Order-to-Cash** (Customer Onboarding)
4. **Usage-to-Cash** (Service Delivery)

**Financial Processes:**
5. **Product ROI**
6. **Customer Cost Model vs. Actual**
7. **Billing and Payment Status**

### 6.2 Implementation Approach

**Three-step phased approach:**

| Step | Duration | Focus | Cost |
|------|----------|-------|------|
| **Step 1: Initiate** | 15 weeks | Setup + Process Support + Integration | ~69,300 EUR |
| **Step 2: Organizational Adoption** | TBD | Broader rollout across organization | TBD |
| **Step 3: Client Engagement** | TBD | External client-facing deployment | TBD |

**Step 1 Breakdown:**

| Phase | Effort (Days) | Cost (EUR) |
|-------|---------------|------------|
| Setup | 8 | 10,600 |
| Preparations | 8 | 10,700 |
| Process Support: Portfolio Mgmt | 4 | 5,400 |
| Process Support: Opportunity & Bid | 10 | 15,200 |
| Process Support: Order-to-Cash | 4 | 5,400 |
| Process Support: Usage-to-Cash | 10 | 15,200 |
| Contingency (5%) | — | 3,125 |
| Project Management | — | 3,600 |
| **Total** | **~50** | **~69,300** |

### 6.3 Governance Structure

```
Program Steering Group
├── Senior Canopy Management
├── Senior Senority Management
└── Meets: Monthly

Project Work Group
├── Canopy Project Lead
├── Senority Project Manager
├── Senority Implementation Consultant
└── Meets: Weekly

Account Implementation Work Group
├── Canopy Account Manager
├── Senority Implementation Consultant
└── Meets: As needed per account
```

### 6.4 Functional Building Blocks (Appendix A)

The proposal described **7 functional building blocks** plus reporting:

| # | Building Block | Key Capabilities |
|---|---------------|-----------------|
| 1 | **Relationship Management** | Organization structure, client/vendor relationships, governance teams, team agendas, collaboration |
| 2 | **Contract Management** | Contract registration, parties, commitments, obligations, alerts, document management |
| 3 | **Service Management** | Service portfolio, SLA definitions, service performance tracking, RAG status |
| 4 | **Improvement Management** | Improvement actions from KPIs, task assignment, progress tracking |
| 5 | **Risk Management** | Risk register, risk categories, scoring, alerts, mitigation tracking |
| 6 | **Opportunity Management** | Sales pipeline, opportunity tracking, bid management |
| 7 | **System Administration** | User management, security (3-tier), configuration, role-based access |
| — | **Reporting** | Dashboards, portfolio reports, service reports, compliance reports |

---

## 7. Requirements Modelling (Canopy)

Appendix D mapped Canopy's CDM requirements to Evaluetor standard functionality across six processes:

### 7.1 Portfolio Management
| Object | Functions | Evaluetor Support |
|--------|-----------|-------------------|
| Checklist Ready to Sell | Define checklists, assign tasks, maintain deadlines, track status | Standard (module 151) |
| Service Portfolio | Maintain portfolio, versions, SLA definitions, product data | Standard (module 351) |

### 7.2 Opportunity & Bid Management
| Object | Functions | Evaluetor Support |
|--------|-----------|-------------------|
| Opportunity | Maintain list, import from external sources, track sales status | Standard (module 334) |
| Bid Process | Validate deviations, define contracts & commitments, risk checking | Standard (modules 436, 394, 331/431) |

### 7.3 Order-to-Cash
| Object | Functions | Evaluetor Support |
|--------|-----------|-------------------|
| Ready to Deliver Checklist | Define checklists, assign tasks, maintain deadlines, dashboards | Standard (module 151) |

### 7.4 Usage-to-Cash
| Object | Functions | Evaluetor Support |
|--------|-----------|-------------------|
| Service Performance | Register SLA returns, report history, define escalations | Standard (modules 451, 311) |
| Real-time Status | Service status per customer for senior management | Standard (modules 311/411/413) |

### 7.5 Product ROI
| Object | Functions | Evaluetor Support |
|--------|-----------|-------------------|
| Service Performance | Register product investment, maintain costs/revenue per customer | Release / Reports |

### 7.6 Customer Cost Model vs. Actual
| Object | Functions | Evaluetor Support |
|--------|-----------|-------------------|
| Service Performance | Register cost model, track actual vs. model, profitability reporting | Release / Custom |

---

## 8. Commercial Terms

### 8.1 Subscription Pricing (Canopy, 2014)

| Item | Users | Monthly Fee |
|------|-------|-------------|
| Base subscription (Contract, Relationship, Service, Improvement Mgmt) | 50 | 5,000 EUR |
| Additional user | 1 | 75 EUR |

### 8.2 Storage
- 1 GB per user included (pooled across all users)
- Additional storage: 2.50 EUR per GB/month

### 8.3 Professional Services Day Rates

| Role | Day Rate (EUR) |
|------|---------------|
| Implementation Support Consultant | 1,700 |
| Project Manager | 1,400 |
| Enhancement Developer | 1,200 |
| Evaluetor Administration | 950 |
| Car travel per km | 0.40 |

All prices exclusive of VAT.

### 8.4 Service Desk

- **Hours:** 9:00-17:00 CET, weekdays
- **First-line support:** Subscriber responsibility
- **Level 1 (High):** Critical production issue, resolution starts immediately
- **Level 2 (Medium):** Bug with workaround available, resolution within 4 business hours
- **Service Requests:** Handled within 4 business hours
- **Change Requests:** Estimated, priced, and submitted for approval

---

## 9. General Terms and Conditions (Summary)

Key provisions from the standard Evaluetor T&Cs (Appendix B):

| Clause | Key Terms |
|--------|-----------|
| **Term** | Auto-renews annually; 30-day non-renewal notice |
| **Liability** | Capped at lesser of 100,000 EUR or 12 months' fees |
| **Data** | Subscriber retains all rights to their data |
| **Confidentiality** | Standard mutual obligations, 5-year duration |
| **Warranties** | Services conform to documentation; no other warranties |
| **Indemnification** | Mutual indemnification for IP infringement and data breaches |
| **Governing Law** | Dutch law, Rotterdam jurisdiction |
| **Data Location** | EU-based hosting |

---

## 10. Technology Platform (Original)

The original Evaluetor was built on Microsoft SharePoint:

- **Platform:** Microsoft SharePoint + SQL Server
- **Delivery:** SaaS (standard), on-premise options available
- **Access:** Standard internet browsers
- **Architecture:** Apps structure within SharePoint with active repositories
- **Integration:** Standard web services, MS Office, Outlook, 3rd party (SAP, Oracle)
- **Search:** Full-text search on stored documents via SharePoint
- **Security:** Three-tier (Access, Role-based, Personal involvement/team membership)

---

## 11. Evolution to Modern Platform

The current Evaluetor CLM platform represents a fundamental reimagining of the original concept, preserving core domain knowledge while adopting modern AI-native architecture:

| Aspect | Original (2012-2015) | Modern Platform |
|--------|---------------------|-----------------|
| **Platform** | Microsoft SharePoint + SQL Server | FastAPI + React + PostgreSQL |
| **AI** | None (manual data entry) | 9 AI agents (GPT-4o), automated extraction |
| **Contract Processing** | Manual digitization, categorization, enrichment | Automated: parse, chunk, embed, extract, analyze |
| **Relationship Governance** | Manual KPI entry, team-based perception scoring | AI-assisted KPI creation from SLAs, automated health scores |
| **Architecture** | Monolithic SharePoint app | Multi-tenant SaaS, async microservices |
| **Vector Search** | SharePoint full-text search | ChromaDB embeddings, semantic RAG |
| **Risk Management** | Manual risk register | AI-detected risk categories (10 types) |
| **Contract Alerts** | Manually configured alerts | AI-extracted obligations, auto-renewal detection |
| **Multi-tenancy** | Per-site collection | Row-level tenant isolation |
| **Improvement Management** | Manual improvement actions | Auto-generated from AI risk analysis |
| **Deployment** | On-premise or hosted SharePoint | Docker Compose on AWS |

### Core Concepts Preserved

Despite the complete technical rewrite, the fundamental Evaluetor concepts remain:

1. **Dual-view philosophy** — Facts (AI-extracted contract data) + Perceptions (KPI scoring surveys)
2. **Four management pillars** — Contract, Service, Relationship, Improvement management
3. **Organization ↔ Relationship ↔ Contract hierarchy** — Same data model ancestry
4. **Governance team collaboration** — Teams assigned to relationships with specific roles
5. **Commitment tracking** — Obligations with deadlines, owners, and consequences
6. **Performance indicators** — KPIs with scoring scales, targets, and RAG status
7. **Health/status dashboards** — Executive-level portfolio views with drill-down capability
8. **Risk register** — Contract risk identification and mitigation tracking
9. **Closing the gaps** — Commercial, delivery, and information gaps addressed through transparency

---

*Compiled from Senority/Evaluetor reference documents (2012-2015). This heritage document provides context for the AI-native CLM platform's domain model and feature design.*
