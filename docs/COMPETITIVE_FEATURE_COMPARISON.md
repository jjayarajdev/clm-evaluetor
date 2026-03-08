# Competitive Feature Comparison: Evaluetor vs CLM Market Leaders

**Last Updated:** February 2026

This document provides a comprehensive feature-by-feature comparison between Evaluetor and the leading CLM platforms in the market.

---

## Executive Summary

| Vendor | Positioning | Primary Strength | Primary Weakness |
|--------|-------------|------------------|------------------|
| **Evaluetor** | AI Legal Engineer | Post-signature governance, AI extraction, relationship management | No contract authoring, no visual workflow UI, no onboarding wizard, stubs only for integrations |
| **DocuSign CLM** | Ecosystem Extender | E-signature ubiquity, Salesforce integration | Bolt-on AI, complex implementations |
| **Icertis** | Enterprise Monolith | Deep verticals, SAP/Workday integration | 12-18 month implementations, expensive |
| **Ironclad** | Legal Operating System | Modern UX, workflow designer | Weak post-signature, limited ERP integrations |
| **Sirion** | AI Performance Manager | Buy-side value realization, invoice reconciliation | Dense UI, complex deployments |
| **Agiloft** | No-Code Chameleon | Extreme customization, flexibility | Steep admin learning curve, UI polish |
| **Legitt AI** | Agentic CLM | AI-native workflows, conversational | Emerging player, less enterprise depth |

---

## 1. Core Architecture Comparison

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|---------|-----------|----------|---------|----------|--------|---------|-----------|
| **Primary Data Model** | Clause/obligation graph | Document (file) | Contract object | Workflow (process) | Obligation (performance) | Database record | AI tasks |
| **Architecture Style** | Data-first, AI-native | File-first | Object-oriented | Process-centric | Performance-centric | Relational | Agent-centric |
| **AI Integration** | Core engine | Bolt-on (Seal) | Add-on layer | Native (Jurist) | Deep extraction | Prompt Lab | Core engine |
| **Multi-tenant** | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| **Cloud Deployment** | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| **On-Premise Option** | Planned | Yes | Yes | No | Yes | Yes | Limited |
| **Region Sharding (GDPR)** | ❌ Not Implemented | Limited | Yes | Limited | Yes | Yes | Limited |

---

## 2. Contract Ingestion & Repository

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|---------|-----------|----------|---------|----------|--------|---------|-----------|
| **PDF Upload** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **DOCX Upload** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Batch/ZIP Upload** | ✅ | ✅ | ✅ | ⚠️ Limited | ✅ | ✅ | ✅ |
| **AI Migration Wizard** | ❌ Not Implemented | ❌ Services | ❌ Services | ❌ Services | ⚠️ Partial | ⚠️ Partial | ✅ |
| **Auto-classification** | ✅ (NDA, MSA, SOW) | ⚠️ Basic | ✅ | ⚠️ Basic | ✅ | ✅ | ✅ |
| **Document Deduplication** | ✅ Hash-based | ⚠️ Manual | ✅ | ⚠️ Manual | ✅ | ⚠️ Manual | ⚠️ Basic |
| **Amendment/Version Linking** | ✅ Automatic | ⚠️ Manual | ✅ | ✅ | ✅ | ⚠️ Manual | ✅ |
| **Family Linking (MSA + SOWs)** | ✅ Auto-detected | ⚠️ Manual | ✅ | ⚠️ Manual | ✅ | ⚠️ Manual | ⚠️ Basic |
| **OCR for Scanned PDFs** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Layout-Aware Parsing** | ⚠️ Basic (PyMuPDF) | ❌ | ⚠️ Basic | ❌ | ✅ | ⚠️ Basic | ⚠️ Basic |

---

## 3. AI Extraction Capabilities

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|---------|-----------|----------|---------|----------|--------|---------|-----------|
| **Metadata Extraction** | ✅ LLM-powered | ⚠️ Rules-based | ✅ | ⚠️ Rules-based | ✅ LLM | ✅ Prompt Lab | ✅ LLM |
| **Parties Identification** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Key Dates Extraction** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Contract Value** | ✅ | ⚠️ Manual | ✅ | ⚠️ Manual | ✅ | ⚠️ Manual | ✅ |
| **Clause Extraction** | ✅ 17+ types | ⚠️ Basic | ✅ | ⚠️ Basic | ✅ | ✅ | ✅ |
| **Clause Classification** | ✅ AI-powered | ⚠️ Rules | ✅ | ⚠️ Rules | ✅ | ✅ | ✅ |
| **Obligation Extraction** | ✅ Full | ⚠️ Basic | ✅ | ⚠️ Basic | ✅ Full | ⚠️ Partial | ⚠️ Partial |
| **SLA Extraction** | ✅ Metrics + Targets | ❌ | ✅ | ❌ | ✅ Full | ⚠️ Partial | ⚠️ Partial |
| **Risk Assessment** | ✅ 10 categories | ⚠️ Static rules | ✅ RiskAI | ✅ Jurist | ✅ | ✅ | ✅ |
| **Definition Extraction** | ✅ | ❌ | ⚠️ Partial | ❌ | ✅ | ⚠️ Partial | ⚠️ Partial |
| **Custom Schema Extraction** | ✅ 15 types, 1,235 fields | ❌ | ✅ | ❌ | ⚠️ Partial | ✅ | ⚠️ Partial |
| **Extraction Accuracy** | 90%+ | 70-80% | 85-90% | 75-85% | 90%+ | 80-85% | 85-90% |

---

## 4. Search & Query Capabilities

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|---------|-----------|----------|---------|----------|--------|---------|-----------|
| **Keyword Search** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Metadata Filters** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Semantic/Vector Search** | ✅ ChromaDB | ❌ | ⚠️ Limited | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ |
| **Hybrid Search (Vector + Keyword)** | ✅ | ❌ | ⚠️ Partial | ❌ | ✅ | ⚠️ Partial | ✅ |
| **Clause-Level Search** | ✅ | ❌ | ✅ | ❌ | ✅ | ⚠️ Partial | ✅ |
| **Natural Language Query** | ✅ RAG Q&A | ❌ | ⚠️ Limited | ❌ | ✅ AskSirion | ⚠️ Prompt Lab | ✅ |
| **Cross-Contract Analysis** | ✅ | ❌ | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ |
| **Query Explainability** | ✅ Source citations | ❌ | ⚠️ Partial | ❌ | ✅ | ⚠️ Partial | ✅ |

**Example Query (RAG-based Q&A):**
> "What are the SLA requirements in this contract?" or "Show me all contracts expiring in the next 90 days."

*Note: Complex multi-constraint queries with structured field extraction (e.g., "liability cap > 5x fees AND IP ownership = supplier") require extracted metadata to be available - the Q&A agent uses RAG over contract text, not structured query parsing.*

---

## 5. Contract Authoring & Negotiation

> **Note:** Evaluetor currently focuses on **post-signature management**. Pre-signature authoring features are planned for future phases.

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|---------|-----------|----------|---------|----------|--------|---------|-----------|
| **Browser-Native Editor** | ❌ Planned | ❌ Word plugin | ❌ Word plugin | ✅ | ❌ Word | ❌ Word | ✅ |
| **Track Changes** | ❌ Planned | ⚠️ Word | ⚠️ Word | ✅ | ⚠️ Word | ⚠️ Word | ✅ |
| **Word Round-Trip** | ❌ Planned | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ Partial |
| **Real-Time Collaboration** | ❌ Planned | ❌ | ❌ | ✅ Google Docs-style | ❌ | ❌ | ✅ |
| **Template Library** | ❌ Not Implemented | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Clause Library** | ❌ Not Implemented | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **AI-Assisted Drafting** | ❌ Not Implemented | ❌ | ⚠️ Limited | ✅ Jurist | ✅ | ⚠️ Prompt Lab | ✅ |
| **Playbook Comparison** | ❌ Not Implemented | ❌ | ✅ | ✅ | ✅ | ⚠️ Manual | ✅ |
| **AI Redlining Suggestions** | ❌ Planned | ❌ | ⚠️ Limited | ✅ | ⚠️ Limited | ⚠️ Prompt Lab | ✅ |
| **Amendment/Version Tracking** | ✅ Full | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Version Diff Comparison** | ✅ Field-level | ⚠️ Basic | ✅ | ⚠️ Basic | ✅ | ⚠️ Basic | ⚠️ Basic |

---

## 6. Workflow & Approvals

> **Note:** Evaluetor has a full workflow engine backend (API) but lacks a visual UI builder. Configuration is done via API/scripts.

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|---------|-----------|----------|---------|----------|--------|---------|-----------|
| **Visual Workflow Builder UI** | ❌ API only | ✅ | ✅ | ✅ Industry-leading | ✅ | ✅ | ✅ |
| **Workflow Definition (Backend)** | ✅ Full | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Conditional Routing** | ✅ Backend | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Sequential Approvals** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Parallel Approvals** | ⚠️ Sequential only | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Escalation Rules** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ Basic |
| **Delegation Support** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ Limited |
| **SLA-Based Routing** | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited |
| **Automated Actions** | ✅ 14+ types | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ✅ |
| **No-Code Configuration UI** | ❌ API only | ⚠️ Partial | ⚠️ Complex | ✅ | ⚠️ Partial | ✅ | ✅ |
| **Scheduled Jobs** | ✅ | ⚠️ Limited | ✅ | ❌ | ✅ | ✅ | ⚠️ Limited |
| **Event-Driven Triggers** | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ✅ |
| **Retry Logic** | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited |

---

## 7. Post-Signature Management (Key Differentiator)

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|---------|-----------|----------|---------|----------|--------|---------|-----------|
| **Obligation Tracking** | ✅ Full | ⚠️ Basic reminders | ✅ | ⚠️ Basic | ✅ Full | ⚠️ Partial | ⚠️ Basic |
| **Obligation Status (RAG)** | ✅ | ❌ | ✅ | ❌ | ✅ | ⚠️ Manual | ❌ |
| **SLA Monitoring** | ✅ Full | ❌ | ✅ | ❌ | ✅ Full | ⚠️ Partial | ⚠️ Limited |
| **SLA vs Actual Comparison** | ✅ Automated | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Service Credit Calculation** | ✅ Automated | ❌ | ⚠️ Manual | ❌ | ✅ | ❌ | ❌ |
| **Penalty Calculation** | ✅ Automated | ❌ | ⚠️ Manual | ❌ | ✅ | ❌ | ❌ |
| **Milestone Tracking** | ✅ Full | ❌ | ✅ | ⚠️ Basic | ✅ | ⚠️ Partial | ❌ |
| **Invoice Reconciliation** | ❌ Not Implemented | ❌ | ✅ | ❌ | ✅ Industry-leading | ❌ | ❌ |
| **Revenue Leakage Detection** | ❌ Not Implemented | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Compliance Monitoring** | ✅ | ⚠️ Basic | ✅ | ⚠️ Basic | ✅ | ⚠️ Partial | ⚠️ Basic |
| **Breach Detection** | ✅ Automated | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Vendor Performance Scoring** | ✅ | ❌ | ✅ | ❌ | ✅ | ⚠️ Partial | ❌ |
| **COLA/FX Adjustments** | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ |

---

## 8. Renewal Management

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|---------|-----------|----------|---------|----------|--------|---------|-----------|
| **Auto-Renewal Detection** | ✅ | ⚠️ Manual | ✅ | ⚠️ Manual | ✅ | ⚠️ Manual | ⚠️ Basic |
| **Notice Period Calculation** | ✅ Automated | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Renewal Calendar** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ Basic |
| **At-Risk Contract View** | ✅ | ⚠️ Basic | ✅ | ⚠️ Basic | ✅ | ⚠️ Partial | ❌ |
| **Renewal Alerts** | ✅ Automated | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ Basic |
| **Renewal Recommendations** | ✅ AI-powered | ❌ | ⚠️ Limited | ❌ | ✅ | ❌ | ⚠️ Limited |

---

## 9. Relationship Governance (Evaluetor Unique)

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|---------|-----------|----------|---------|----------|--------|---------|-----------|
| **Organization Management** | ✅ | ❌ | ⚠️ Basic | ❌ | ⚠️ Vendor-centric | ❌ | ❌ |
| **Business Relationship Tracking** | ✅ Full | ❌ | ⚠️ Limited | ❌ | ⚠️ Limited | ❌ | ❌ |
| **Relationship Health Scores** | ✅ | ❌ | ❌ | ❌ | ⚠️ Limited | ❌ | ❌ |
| **Team Assignment per Relationship** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **KPI Definition & Tracking** | ✅ Full | ❌ | ⚠️ Limited | ❌ | ✅ | ⚠️ Partial | ❌ |
| **Internal Perception Scoring** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **External Perception Scoring** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Perception Gap Analysis** | ✅ Automated | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Improvement Point Tracking** | ✅ Auto-generated | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Multi-Party Satisfaction Surveys** | ✅ Full | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **External Survey Portal** | ✅ Token-based | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Governance Structure Visualization** | ✅ | ❌ | ⚠️ Limited | ❌ | ⚠️ Limited | ❌ | ❌ |

---

## 10. Alerts & Notifications

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|---------|-----------|----------|---------|----------|--------|---------|-----------|
| **Email Notifications** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Customizable Templates** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ Limited |
| **Threshold-Based Alerts** | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited |
| **Alert Severity Levels** | ✅ | ❌ | ✅ | ❌ | ✅ | ⚠️ Partial | ❌ |
| **Bulk Alert Actions** | ✅ | ❌ | ⚠️ Limited | ❌ | ✅ | ⚠️ Partial | ❌ |
| **Alert Acknowledge/Resolve/Escalate** | ✅ Full | ❌ | ✅ | ❌ | ✅ | ⚠️ Partial | ❌ |
| **Alert Trends & Statistics** | ✅ | ❌ | ⚠️ Limited | ❌ | ✅ | ⚠️ Limited | ❌ |
| **In-App Notifications** | ⚠️ Backend only | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Slack/Teams Integration** | ✅ Planned | ✅ | ✅ | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited |

---

## 11. Dashboards & Reporting

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|---------|-----------|----------|---------|----------|--------|---------|-----------|
| **Role-Based Dashboards** | ✅ 4 roles | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited |
| **Executive Dashboard** | ✅ | ⚠️ Basic | ✅ | ⚠️ Basic | ✅ | ✅ | ⚠️ Basic |
| **Legal Dashboard** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Procurement Dashboard** | ✅ | ⚠️ Limited | ✅ | ❌ | ✅ | ⚠️ Partial | ❌ |
| **Admin Dashboard** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ Basic |
| **SLA Compliance Dashboard** | ✅ | ❌ | ✅ | ❌ | ✅ | ⚠️ Partial | ❌ |
| **Portfolio Risk Dashboard** | ✅ | ❌ | ✅ | ⚠️ Limited | ✅ | ⚠️ Partial | ⚠️ Limited |
| **Obligation Status Tracker** | ✅ | ❌ | ✅ | ❌ | ✅ | ⚠️ Partial | ❌ |
| **Milestone Health Dashboard** | ✅ | ❌ | ✅ | ❌ | ✅ | ⚠️ Partial | ❌ |
| **Compliance Trend Analysis** | ✅ | ❌ | ✅ | ❌ | ✅ | ⚠️ Partial | ❌ |
| **CSV/Excel Export** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Custom Report Builder** | ✅ Planned | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited |
| **Scheduled Reports** | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited |

---

## 12. Integrations

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|---------|-----------|----------|---------|----------|--------|---------|-----------|
| **Salesforce** | ✅ Stub | ✅ Native | ✅ | ✅ | ✅ | ✅ Workato | ⚠️ Limited |
| **SAP** | ✅ Planned | ⚠️ Limited | ✅ Strategic | ⚠️ Limited | ✅ | ✅ Workato | ❌ |
| **Workday** | ✅ Planned | ⚠️ Limited | ✅ Strategic | ⚠️ Limited | ✅ | ✅ Workato | ❌ |
| **ServiceNow** | ✅ Stub | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ Workato | ❌ |
| **Jira** | ✅ Planned | ⚠️ Limited | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ Workato | ⚠️ Limited |
| **SharePoint/O365** | ✅ Planned | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ Limited |
| **NetSuite** | ✅ Planned | ⚠️ Limited | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ Workato | ❌ |
| **E-Signature (DocuSign)** | ✅ Planned | ✅ Native | ✅ | ✅ | ✅ | ✅ | ✅ |
| **E-Signature (Adobe Sign)** | ✅ Planned | ❌ | ✅ | ✅ | ✅ | ✅ | ⚠️ Limited |
| **Generic API/Webhooks** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **iPaaS (Workato/Zapier)** | ✅ Planned | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ Native | ⚠️ Limited |

---

## 13. AI Agent Capabilities

> **Note:** Evaluetor's AI agents are focused on **analysis and extraction** of uploaded contracts, not contract generation or drafting.

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|---------|-----------|----------|---------|----------|--------|---------|-----------|
| **Multi-Agent Architecture** | ✅ Agent Squad | ❌ | ❌ | ⚠️ Single (Jurist) | ⚠️ Limited | ⚠️ Prompt Lab | ✅ Multi-agent |
| **Metadata Extraction Agent** | ✅ | ❌ | ⚠️ Rules | ❌ | ✅ | ⚠️ Prompt Lab | ✅ |
| **Clause Extraction Agent** | ✅ 17+ types | ❌ | ⚠️ Rules | ❌ | ✅ | ⚠️ Prompt Lab | ✅ |
| **Obligation Tracking Agent** | ✅ | ❌ | ⚠️ Partial | ❌ | ✅ | ❌ | ⚠️ Limited |
| **Risk Detection Agent** | ✅ 10 categories | ⚠️ Static | ✅ RiskAI | ✅ Jurist | ✅ | ⚠️ Prompt Lab | ✅ |
| **Renewal Monitoring Agent** | ✅ | ❌ | ⚠️ Rules | ❌ | ✅ | ❌ | ⚠️ Limited |
| **Q&A/RAG Agent** | ✅ | ❌ | ⚠️ Limited | ❌ | ✅ AskSirion | ⚠️ Prompt Lab | ✅ |
| **SLA Extraction Agent** | ✅ | ❌ | ⚠️ Partial | ❌ | ✅ | ❌ | ❌ |
| **Custom Schema Agent** | ✅ 15 schemas, 1,235 fields | ❌ | ✅ | ❌ | ⚠️ Partial | ✅ | ⚠️ Limited |
| **Contract Drafting Agent** | ❌ Not Implemented | ❌ | ❌ | ✅ Jurist | ✅ | ⚠️ Prompt Lab | ✅ |
| **Agentic Redlining** | ❌ Not Implemented | ❌ | ❌ | ✅ | ❌ | ⚠️ Prompt Lab | ✅ |
| **Agent Observability** | ✅ Langfuse | ❌ | ⚠️ Limited | ⚠️ Limited | ⚠️ Limited | ⚠️ Limited | ⚠️ Limited |

---

## 14. Security & Compliance

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|---------|-----------|----------|---------|----------|--------|---------|-----------|
| **SOC 2 Type II** | ✅ Planned | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ In progress |
| **GDPR Compliance** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **HIPAA** | ✅ Planned | ✅ | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited |
| **SSO/SAML** | ✅ Planned | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **RBAC** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **ABAC (Attribute-Based)** | ❌ RBAC only | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited |
| **Full Audit Trail** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ Partial |
| **Data Encryption (At Rest)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Data Encryption (In Transit)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **AI Data Zero-Retention** | ✅ | ❌ | ⚠️ Limited | ⚠️ Limited | ⚠️ Limited | ⚠️ Limited | ⚠️ Limited |
| **Private LLM Deployment** | ✅ Planned | ❌ | ❌ | ❌ | ⚠️ Limited | ❌ | ❌ |

---

## 15. Implementation & Time-to-Value

> **Note:** Evaluetor requires technical setup (Docker, database, API configuration). No self-service wizard exists.

| Metric | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|--------|-----------|----------|---------|----------|--------|---------|-----------|
| **Typical Implementation** | Days-Weeks | 3-6 months | 12-18 months | 2-4 months | 6-12 months | 3-6 months | Weeks |
| **Time to First Value** | Hours (after setup) | Weeks | Months | Weeks | Weeks | Weeks | Hours-Days |
| **Professional Services Required** | Medium (technical) | High | Very High | Medium | High | Medium-High | Low |
| **Self-Service Setup** | ❌ Not Implemented | ⚠️ Limited | ❌ | ⚠️ Partial | ⚠️ Limited | ⚠️ Partial | ✅ |
| **AI-Assisted Onboarding** | ❌ Not Implemented | ❌ | ❌ | ❌ | ⚠️ Partial | ❌ | ✅ |
| **Configuration Complexity** | Medium (API/scripts) | Medium | Very High | Medium | High | High | Low |

---

## 16. Pricing Model

| Aspect | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|--------|-----------|----------|---------|----------|--------|---------|-----------|
| **Model** | Asset-based | Per-user | Per-user + volume | Per-user | Enterprise deals | Per-user | SaaS subscription |
| **Unlimited Users** | ✅ | ❌ | ❌ | ❌ | Negotiable | ❌ | ⚠️ Varies |
| **Entry Price Point** | €18,000/year | High | Very High | Medium-High | Very High | Medium | Low-Medium |
| **Mid-Market Tier** | €40,000/year | High | N/A (Enterprise) | High | N/A (Enterprise) | Medium-High | Medium |
| **Enterprise Tier** | €100,000/year | Very High | Very High | Very High | Very High | High | High |
| **AI Features Included** | ✅ All tiers | ⚠️ Premium only | ⚠️ Add-on | ✅ | ✅ | ⚠️ Add-on | ✅ |
| **Implementation Fees** | €5-15K | €25-100K | €100K-500K+ | €25-75K | €50-200K | €25-75K | €5-20K |

---

## 17. Vertical Industry Support

> **Note:** Evaluetor has no industry-specific configurations. The platform is generic and can be used across industries.

| Industry | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Legitt AI |
|----------|-----------|----------|---------|----------|--------|---------|-----------|
| **Technology** | ⚠️ Generic | ✅ | ✅ | ✅ Primary | ✅ | ✅ | ✅ |
| **Financial Services** | ⚠️ Generic | ✅ | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited |
| **Healthcare/Pharma** | ⚠️ Generic | ⚠️ Limited | ✅ Strong | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited |
| **Manufacturing** | ⚠️ Generic | ⚠️ Limited | ✅ Strong | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited |
| **Retail/CPG** | ⚠️ Generic | ✅ | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited |
| **Energy/Utilities** | ⚠️ Generic | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited |
| **Government** | ⚠️ Generic | ✅ | ✅ | ⚠️ Limited | ⚠️ Limited | ✅ Strong | ⚠️ Limited |
| **Legal Services** | ⚠️ Generic | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ |

---

## 18. Summary: Competitive Positioning Matrix

| Dimension | Leader(s) | Evaluetor Position |
|-----------|-----------|-------------------|
| **Pre-Signature (Authoring/Negotiation)** | Ironclad, Legitt AI | ❌ **Not Implemented** |
| **Post-Signature (Execution Management)** | Sirion, Evaluetor | ✅ **Strong** (SLAs, obligations, compliance) |
| **AI Extraction (Analysis)** | Sirion, Icertis, Evaluetor | ✅ **Strong** (6+ agents) |
| **Agentic AI Architecture** | Evaluetor, Legitt AI | ✅ **Strong** (Agent Squad + Langfuse) |
| **Workflow Backend** | Icertis, Sirion | ✅ **Competitive** (API-only, no UI) |
| **Visual Workflow Builder** | Ironclad, Agiloft | ❌ **Not Implemented** |
| **Enterprise Integrations** | Icertis, Sirion | ⚠️ **Stubs only** |
| **Time-to-Value (Analysis)** | Evaluetor, Legitt AI | ✅ **Fast** (upload → insights) |
| **Relationship Governance** | Evaluetor | ✅ **Unique** (KPIs, perception, surveys) |
| **Template/Clause Libraries** | Ironclad, Icertis | ❌ **Not Implemented** |
| **Region Sharding / GDPR** | Icertis, Sirion | ❌ **Not Implemented** |
| **Self-Service Onboarding** | Legitt AI | ❌ **Not Implemented** |
| **Vertical Industry Solutions** | Icertis, Agiloft | ⚠️ **Generic only** |

---

## 19. Key Takeaways

### Evaluetor Strengths (Actually Implemented):

1. **Post-Signature Management**: SLA monitoring, obligation tracking, compliance monitoring, breach detection, milestone tracking
2. **Relationship Governance**: KPI perception scoring, gap analysis, improvement tracking, multi-party surveys (unique feature)
3. **AI Extraction Agents**: 6+ specialized agents for metadata, clauses, obligations, SLAs, risks, renewals
4. **Workflow Engine (Backend)**: Full workflow orchestration with 14+ automated action types, event detection, approval chains, delegation
5. **Agentic AI Architecture**: Agent Squad multi-agent system with Langfuse observability
6. **Multi-Tenancy**: Full tenant isolation with subscription tiers
7. **COLA/FX Adjustments**: Implemented in connector stubs
8. **Renewal Monitoring**: AI-powered with recommendations and urgency levels
9. **Scheduled Jobs**: Background job orchestration with history tracking
10. **Amendment/Version Tracking**: Full version history with field-level diff comparison

### Evaluetor Gaps (Not Implemented):

1. **Contract Authoring**: No browser editor, track changes, templates, clause library, or AI drafting
2. **Visual Workflow Builder**: Workflow engine exists but no UI - configuration via API only
3. **Pre-Signature Features**: No playbook comparison, AI redlining, or negotiation support
4. **Enterprise Integrations**: ServiceNow, Salesforce are stubs only
5. **SSO/SAML**: Not yet implemented
6. **Parallel Approvals**: Currently sequential only
7. **Region Sharding (GDPR)**: Not implemented despite being listed as a requirement
8. **Layout-Aware Parsing**: Uses basic PyMuPDF, not LayoutLM as documented
9. **AI Migration Wizard**: Not implemented - only basic upload exists
10. **Invoice Reconciliation**: Not implemented
11. **Revenue Leakage Detection**: Not implemented
12. **ABAC**: Only RBAC implemented, not attribute-based access control
13. **Self-Service Setup / Onboarding Wizard**: Not implemented
14. **Custom Report Builder**: Not implemented
15. **In-App Notifications UI**: Backend only, no frontend display
16. **Vertical Industry Configurations**: No industry-specific features

### Strategic Positioning:

**Evaluetor is optimized for organizations that:**
- ✅ Already have signed contracts to manage (post-signature focus)
- ✅ Need to track obligations, SLAs, and compliance
- ✅ Want AI-powered extraction and risk analysis
- ✅ Need relationship governance and KPI perception scoring
- ✅ Have technical resources to deploy Docker, configure APIs, and write scripts
- ✅ Can work with stub integrations or build custom connectors

**Evaluetor is NOT suited for organizations that need:**
- ❌ Contract drafting and negotiation tools
- ❌ Template and clause library management
- ❌ Visual no-code workflow configuration
- ❌ Pre-signature collaboration features
- ❌ Self-service setup or onboarding wizard
- ❌ Production-ready enterprise integrations (SAP, ServiceNow, Salesforce)
- ❌ GDPR region sharding
- ❌ Layout-aware document parsing (LayoutLM/Textract)

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Full support / Industry-leading |
| ⚠️ | Partial support / Basic capability |
| ❌ | Not supported / Not available |

---

*Document Version: 1.2*
*Last Updated: March 2026*
*Author: Development Team*
*Based on: Codebase verification, market research, vendor documentation, analyst reports*

**Version History:**
- v1.1: Corrected Evaluetor features based on actual codebase verification (removed marketing claims not backed by implementation)
- v1.2: Updated schema extraction (15 types, 1,235 fields), auto-detected contract family linking, competitive comparison updates
- v1.0: Initial document with competitive analysis
