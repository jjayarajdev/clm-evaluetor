# Competitive Feature Comparison: Evaluetor vs CLM Market Leaders

**Last Updated:** March 2026

This document provides a comprehensive feature-by-feature comparison between Evaluetor and the leading CLM platforms in the market.

---

## Market Context

The CLM market exceeded **$1.24B in 2025** and is projected to reach **$4.1B by 2034** (~13% CAGR). The defining trend of 2025-2026 is the shift from AI-assisted to **agentic AI** — every major vendor has launched multi-agent architectures. Autonomous contract negotiation (AI-to-AI) is the emerging frontier, led by Luminance's Autopilot. Significant M&A activity is reshaping the landscape: Workday acquired Evisort, Haveli took majority stake in Sirion, Conga acquired PROS Holdings, and Agiloft acquired Screens.

---

## Executive Summary

| Vendor | Positioning | Primary Strength | Primary Weakness |
|--------|-------------|------------------|------------------|
| **Evaluetor** | AI Legal Engineer | Post-signature governance, governance bridge (contract-to-relationship automation), AI extraction (9+ agents), perception gap scoring, unlimited-users pricing | No contract authoring, no visual workflow UI, stubs only for integrations |
| **DocuSign CLM** | Intelligent Agreement Management (IAM) | E-signature ubiquity, Iris AI engine, AI Contract Agents, massive install base | Bolt-on CLM, complex implementations |
| **Icertis** | Enterprise AI Platform (Vera) | Largest contract data repository, deep verticals, SAP/Workday integration | 12-18 month implementations, expensive |
| **Ironclad** | Legal Operating System | Rivet multi-agent routing (6 agents), Jurist AI, industry-leading workflow UX | Weak post-signature, limited ERP integrations |
| **Sirion** | AI-Native Contract OS (agentOS) | Highest Gartner execution score, agentOS extensibility, AskSirion 360 conversational | Dense UI, complex deployments |
| **Agiloft** | No-Code CLM + AI on the Inside | Extreme customization, Screens acquisition, AI Obligation Management | Steep admin learning curve, UI polish |
| **Luminance** | Autonomous Legal AI | AI-to-AI negotiation (Autopilot/Lumi Go), institutional memory, multi-agent | Expensive, emerging CLM depth |
| **Conga** | Revenue Lifecycle (CLM + CPQ) | 1,400+ pre-trained models, PROS pricing intelligence acquisition, hybrid LLM/SLM | Less AI-native, acquisition integration risk |
| **SpotDraft** | Fast-Growing Agentic CLM | 169% YoY revenue growth, agentic cross-tool integration for in-house counsel | Smaller customer base, mid-market focus |
| **Summize** | AI-Powered CLM with Intelligent Agents | Summize Intelligent Agents (SIA), UK's #8 fastest-growing tech company | Smaller scale, UK-focused initially |
| **Malbek** | Conversational CLM | "Conversational Contracts" UI-less agentic interface, Ensemble LLM | Niche positioning, smaller market share |

---

## 1. Core Architecture Comparison

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Luminance | Conga |
|---------|-----------|----------|---------|----------|--------|---------|-----------|-------|
| **Primary Data Model** | Clause/obligation graph | Document (file) | Contract object | Workflow (process) | Obligation (performance) | Database record | Negotiation memory | Contract + pricing |
| **Architecture Style** | Data-first, AI-native | File-first, IAM | Object-oriented | Process-centric | Performance-centric | Relational, no-code | AI-first, multi-model | Revenue lifecycle |
| **AI Engine** | Agent Squad (9+ agents, 11 agent files) | Iris AI | Vera AI | Rivet (6 agents) | agentOS | AI on the Inside + Screens | Proprietary multi-model | Hybrid LLM + SLM |
| **Multi-Agent Architecture** | ✅ 9+ agents with intent routing | ⚠️ AI Contract Agents (2025) | ✅ Vera Agents (2025) | ✅ Rivet routing (6 agents) | ✅ agentOS (extensible) | ⚠️ Prompt Lab + Screens | ✅ Multi-agent with memory | ⚠️ Limited |
| **Governance Bridge (Contract → Relationship)** | ✅ Auto-creates orgs, relationships, KPIs, improvement points | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Multi-tenant** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Cloud Deployment** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **On-Premise Option** | Planned | Yes | Yes | No | Yes | Yes | Limited | Yes |
| **Region Sharding (GDPR)** | ❌ Not Implemented | Limited | Yes | Limited | Yes | Yes | Yes | Yes |

---

## 2. Contract Ingestion & Repository

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Luminance | Conga |
|---------|-----------|----------|---------|----------|--------|---------|-----------|-------|
| **PDF Upload** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **DOCX Upload** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Batch/ZIP Upload** | ✅ | ✅ | ✅ | ⚠️ Limited | ✅ | ✅ | ✅ | ✅ |
| **AI Migration Wizard** | ❌ Not Implemented | ❌ Services | ❌ Services | ❌ Services | ⚠️ Partial | ⚠️ Partial | ✅ Portfolio import | ⚠️ Partial |
| **Auto-classification** | ✅ (15 contract types) | ⚠️ Basic | ✅ | ⚠️ Basic | ✅ | ✅ | ✅ | ✅ |
| **Document Deduplication** | ✅ Hash-based | ⚠️ Manual | ✅ | ⚠️ Manual | ✅ | ⚠️ Manual | ✅ | ⚠️ Basic |
| **Amendment/Version Linking** | ✅ Automatic | ⚠️ Manual | ✅ | ✅ | ✅ | ⚠️ Manual | ✅ | ✅ |
| **Family Linking (MSA + SOWs)** | ✅ Auto-detected (6-signal weighted scoring) | ⚠️ Manual | ✅ | ⚠️ Manual | ✅ | ⚠️ Manual | ✅ | ⚠️ Basic |
| **Knowledge Graph** | ✅ Entity/relationship graph | ❌ | ⚠️ Partial | ❌ | ⚠️ Limited | ❌ | ✅ Institutional memory | ❌ |
| **OCR for Scanned PDFs** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Layout-Aware Parsing** | ⚠️ Basic (PyMuPDF) | ❌ | ⚠️ Basic | ❌ | ✅ | ⚠️ Basic | ✅ | ⚠️ Basic |

---

## 3. AI Extraction Capabilities

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Luminance | Conga |
|---------|-----------|----------|---------|----------|--------|---------|-----------|-------|
| **Metadata Extraction** | ✅ LLM-powered | ⚠️ Iris AI | ✅ Vera | ⚠️ Rules-based | ✅ LLM | ✅ Screens + Prompt Lab | ✅ Multi-model | ✅ 1,400+ models |
| **Parties Identification** | ✅ (with excluded-party logic) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Key Dates Extraction** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Contract Value** | ✅ (with currency validation) | ⚠️ Manual | ✅ | ⚠️ Manual | ✅ | ⚠️ Manual | ✅ | ✅ |
| **Clause Extraction** | ✅ 31 types (AI-classified) | ⚠️ Basic | ✅ | ⚠️ Basic | ✅ | ✅ Screens | ✅ | ✅ |
| **Clause Classification** | ✅ GPT-4o semantic | ⚠️ Rules | ✅ Vera | ⚠️ Rules | ✅ | ✅ | ✅ | ✅ |
| **Obligation Extraction** | ✅ Full | ⚠️ Basic | ✅ | ⚠️ Basic | ✅ Full | ✅ AI Obligation Mgmt (2025) | ✅ | ⚠️ Partial |
| **SLA Extraction** | ✅ Metrics + Targets + Penalties | ❌ | ✅ | ❌ | ✅ Full | ⚠️ Partial | ⚠️ Limited | ⚠️ Partial |
| **Risk Assessment** | ✅ 10 categories | ⚠️ AI Contract Agents | ✅ Vera | ✅ Jurist | ✅ | ✅ Screens | ✅ | ⚠️ Basic |
| **Definition Extraction** | ✅ | ❌ | ⚠️ Partial | ❌ | ✅ | ⚠️ Partial | ✅ | ⚠️ Partial |
| **Custom Schema Extraction** | ✅ 15 types, 1,235 fields | ❌ | ✅ | ❌ | ⚠️ Partial | ✅ | ⚠️ Partial | ✅ 1,400+ models |
| **Regulatory Extraction** | ✅ 10 obligation categories | ❌ | ✅ | ❌ | ✅ | ⚠️ Partial | ✅ | ⚠️ Partial |
| **Extraction Accuracy** | 90%+ | 75-85% | 85-90% | 75-85% | 90%+ | 80-85% (improving with Screens) | 90%+ | 85-90% |

---

## 4. Search & Query Capabilities

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Luminance | Conga |
|---------|-----------|----------|---------|----------|--------|---------|-----------|-------|
| **Keyword Search** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Metadata Filters** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Semantic/Vector Search** | ✅ ChromaDB | ⚠️ Iris AI | ⚠️ Limited | ⚠️ Jurist | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited |
| **Hybrid Search (Vector + Keyword)** | ✅ | ❌ | ⚠️ Partial | ❌ | ✅ | ⚠️ Partial | ✅ | ⚠️ Partial |
| **Clause-Level Search** | ✅ | ❌ | ✅ | ❌ | ✅ | ⚠️ Partial | ✅ | ⚠️ Partial |
| **Natural Language Query** | ✅ RAG Q&A + Intent Router | ⚠️ Iris AI (2025) | ⚠️ Vera (2025) | ⚠️ Jurist | ✅ AskSirion (2025) | ⚠️ Prompt Lab | ✅ Conversational | ⚠️ Limited |
| **Cross-Contract Analysis** | ✅ | ❌ | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ Portfolio-wide | ⚠️ Limited |
| **Structured Intent Routing** | ✅ 5 categories + clause bypass | ❌ | ❌ | ❌ | ⚠️ Limited | ❌ | ⚠️ Limited | ❌ |
| **LLM-Enhanced Visualizations** | ✅ Auto-generated charts | ❌ | ⚠️ Limited | ❌ | ⚠️ Limited | ⚠️ Limited | ❌ | ❌ |
| **Query Explainability** | ✅ Source citations | ❌ | ⚠️ Partial | ⚠️ Jurist citations | ✅ | ⚠️ Partial | ✅ | ⚠️ Partial |
| **Chat History / Sessions** | ✅ Persistent, multi-tenant | ❌ | ❌ | ❌ | ⚠️ Limited | ❌ | ✅ | ❌ |

---

## 5. Contract Authoring & Negotiation

> **Note:** Evaluetor currently focuses on **post-signature management**. Pre-signature authoring features are planned for future phases.

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Luminance | Conga |
|---------|-----------|----------|---------|----------|--------|---------|-----------|-------|
| **Browser-Native Editor** | ❌ Planned | ❌ Word plugin | ❌ Word plugin | ✅ | ❌ Word | ❌ Word | ✅ | ❌ Word |
| **Track Changes** | ❌ Planned | ⚠️ Word | ⚠️ Word | ✅ | ⚠️ Word | ⚠️ Word | ✅ | ⚠️ Word |
| **Word Round-Trip** | ❌ Planned | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Real-Time Collaboration** | ❌ Planned | ❌ | ❌ | ✅ Google Docs-style | ❌ | ❌ | ✅ | ❌ |
| **Template Library** | ❌ Not Implemented | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ Limited | ✅ |
| **Clause Library** | ❌ Not Implemented | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ Limited | ✅ |
| **AI-Assisted Drafting** | ❌ Not Implemented | ⚠️ Iris AI | ✅ Vera Composer Agent | ✅ Jurist Drafting Agent | ✅ AskSirion Draft | ⚠️ Screens | ✅ Lumi Go | ⚠️ Partial |
| **Playbook Comparison** | ❌ Not Implemented | ❌ | ✅ Vera Agents | ✅ | ✅ | ⚠️ Manual | ✅ | ⚠️ Partial |
| **AI Redlining** | ❌ Planned | ❌ | ⚠️ Vera Agents | ✅ Redlining Agent | ✅ AskSirion Redline | ⚠️ Screens | ✅ Auto-negotiation | ⚠️ Partial |
| **Autonomous Negotiation** | ❌ Not Planned | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Autopilot (AI-to-AI) | ❌ |
| **Amendment/Version Tracking** | ✅ Full | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Version Diff Comparison** | ✅ Field-level | ⚠️ Basic | ✅ | ⚠️ Basic | ✅ | ⚠️ Basic | ✅ | ⚠️ Basic |

---

## 6. Workflow & Approvals

> **Note:** Evaluetor has a full workflow engine backend (API) but lacks a visual UI builder. Configuration is done via API/scripts.

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Luminance | Conga |
|---------|-----------|----------|---------|----------|--------|---------|-----------|-------|
| **Visual Workflow Builder UI** | ❌ API only | ✅ + Monday.com (2025) | ✅ | ✅ Industry-leading | ✅ | ✅ No-code | ❌ | ✅ |
| **No-Code Configuration** | ❌ API only | ✅ Monday.com partnership | ⚠️ Complex | ✅ | ⚠️ Partial | ✅ Industry-leading | ❌ | ⚠️ Partial |
| **Workflow Definition (Backend)** | ✅ Full | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ AI-driven | ✅ |
| **Conditional Routing** | ✅ Backend | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ AI-driven | ✅ |
| **Sequential Approvals** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ Limited | ✅ |
| **Parallel Approvals** | ⚠️ Sequential only | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ Limited | ✅ |
| **Escalation Rules** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ Basic | ✅ |
| **SLA-Based Routing** | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ❌ | ⚠️ Limited |
| **Automated Actions** | ✅ 14+ types | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ AI-driven | ✅ |
| **Scheduled Jobs** | ✅ | ⚠️ Limited | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ |
| **Event-Driven Triggers** | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ AI-driven | ✅ |

---

## 7. Post-Signature Management (Key Differentiator)

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Luminance | Conga |
|---------|-----------|----------|---------|----------|--------|---------|-----------|-------|
| **Obligation Tracking** | ✅ Full | ⚠️ Basic reminders | ✅ | ⚠️ Basic | ✅ Full | ✅ AI Obligation Mgmt | ⚠️ Limited | ⚠️ Partial |
| **Obligation Status (RAG)** | ✅ | ❌ | ✅ | ❌ | ✅ | ⚠️ Manual | ❌ | ❌ |
| **SLA Monitoring** | ✅ Full | ❌ | ✅ | ❌ | ✅ Full | ⚠️ Partial | ❌ | ⚠️ Limited |
| **SLA vs Actual Comparison** | ✅ Automated | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Service Credit Calculation** | ✅ Automated | ❌ | ⚠️ Manual | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Penalty Calculation** | ✅ Automated | ❌ | ⚠️ Manual | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Milestone Tracking** | ✅ Full | ❌ | ✅ | ⚠️ Basic | ✅ | ⚠️ Partial | ❌ | ⚠️ Partial |
| **Invoice Reconciliation** | ❌ Not Implemented | ❌ | ✅ | ❌ | ✅ Industry-leading | ❌ | ❌ | ✅ PROS pricing |
| **Revenue Leakage Detection** | ❌ Not Implemented | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ PROS pricing |
| **Compliance Monitoring** | ✅ Industry-aware | ⚠️ Basic | ✅ | ⚠️ Basic | ✅ | ⚠️ Partial | ✅ | ⚠️ Basic |
| **Breach Detection** | ✅ Automated | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Vendor Performance Scoring** | ✅ | ❌ | ✅ | ❌ | ✅ | ⚠️ Partial | ❌ | ⚠️ Partial |
| **Contract Health Score** | ✅ Composite (Risk 30% + SLA 40% + Obligation 30%) | ❌ | ⚠️ Partial | ❌ | ✅ | ⚠️ Partial | ❌ | ❌ |
| **COLA/FX Adjustments** | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ |

---

## 8. Renewal Management

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Luminance | Conga |
|---------|-----------|----------|---------|----------|--------|---------|-----------|-------|
| **Auto-Renewal Detection** | ✅ | ⚠️ Manual | ✅ | ⚠️ Manual | ✅ | ⚠️ Manual | ✅ | ✅ |
| **Notice Period Calculation** | ✅ Automated | ❌ | ✅ | ❌ | ✅ | ❌ | ✅ | ⚠️ Partial |
| **Renewal Calendar** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ Limited | ✅ |
| **At-Risk Contract View** | ✅ | ⚠️ Basic | ✅ | ⚠️ Basic | ✅ | ⚠️ Partial | ✅ | ⚠️ Partial |
| **Renewal Alerts** | ✅ Automated | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Renewal Recommendations** | ✅ AI-powered | ❌ | ⚠️ Limited | ❌ | ✅ | ❌ | ⚠️ Limited | ⚠️ Limited |

---

## 9. Relationship Governance (Evaluetor Unique)

> **Note:** This is Evaluetor's most differentiated capability. No CLM competitor offers the automated governance bridge (contract upload → organization/relationship/KPI creation), internal vs external perception gap analysis, or integrated relationship management.

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Luminance | Conga |
|---------|-----------|----------|---------|----------|--------|---------|-----------|-------|
| **Governance Bridge (Auto-Pipeline)** | ✅ Contract upload auto-creates orgs, relationships, KPIs, improvement points | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Organization Management** | ✅ | ❌ | ⚠️ Basic | ❌ | ⚠️ Vendor-centric | ❌ | ❌ | ⚠️ CRM-linked |
| **Business Relationship Tracking** | ✅ Full | ❌ | ⚠️ Limited | ❌ | ⚠️ Limited | ❌ | ❌ | ❌ |
| **Relationship Health Scores** | ✅ | ❌ | ❌ | ❌ | ⚠️ Limited | ❌ | ❌ | ❌ |
| **Team Assignment per Relationship** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **KPI Definition & Tracking** | ✅ Full | ❌ | ⚠️ Limited | ❌ | ✅ | ⚠️ Partial | ❌ | ❌ |
| **Internal Perception Scoring** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **External Perception Scoring** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Perception Gap Analysis** | ✅ Automated (dual-perspective with gap severity classification) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Improvement Point Tracking** | ✅ Auto-generated | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Multi-Party Satisfaction Surveys** | ✅ Full | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **External Survey Portal** | ✅ Token-based | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Governance Structure Visualization** | ✅ | ❌ | ⚠️ Limited | ❌ | ⚠️ Limited | ❌ | ❌ | ❌ |

---

## 10. AI Agent Capabilities (2025-2026 Landscape)

> **Note:** The agentic AI landscape has shifted dramatically. Every major vendor now claims multi-agent capabilities. This table reflects the latest announced capabilities as of March 2026.

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Luminance | Conga |
|---------|-----------|----------|---------|----------|--------|---------|-----------|-------|
| **Multi-Agent Architecture** | ✅ Agent Squad (9+ agents, 11 agent files) with intent routing | ⚠️ AI Contract Agents | ✅ Vera Agents | ✅ Rivet (6 agents) | ✅ agentOS (extensible) | ⚠️ Screens + Prompt Lab | ✅ Multi-agent with memory | ⚠️ Hybrid LLM/SLM |
| **Agent Types** | 9+ specialized (metadata, clause, obligation, risk, renewal, Q&A/RAG, SLA, schema, intent router) | 2-3 general | Composer, Playbook | Intake, Redlining, Drafting, Review, Research, Search | Search, Draft, Issue Detection, Redline, Extraction + custom | AI review, Ask AI | Multi-agent + Autopilot | 1,400+ extraction models |
| **Custom Agent Building** | ❌ Fixed agents | ❌ | ⚠️ Vera Agents API | ❌ | ✅ agentOS (no-code) | ⚠️ Prompt Lab | ❌ | ❌ |
| **Metadata Extraction Agent** | ✅ | ⚠️ Iris AI | ✅ Vera | ❌ | ✅ AskSirion | ✅ Screens | ✅ | ✅ |
| **Clause Extraction Agent** | ✅ 31 types | ⚠️ Basic | ✅ Vera | ⚠️ Jurist | ✅ | ✅ Screens | ✅ | ✅ |
| **Obligation Tracking Agent** | ✅ | ❌ | ⚠️ Partial | ❌ | ✅ | ✅ (Dec 2025) | ⚠️ Limited | ⚠️ Partial |
| **Risk Detection Agent** | ✅ 10 categories | ⚠️ AI Contract Agents | ✅ Vera | ✅ Jurist Review Agent | ✅ Issue Detection | ✅ Screens | ✅ | ⚠️ Basic |
| **Renewal Monitoring Agent** | ✅ | ❌ | ⚠️ Rules | ❌ | ✅ | ❌ | ✅ | ⚠️ Partial |
| **Q&A/RAG Agent** | ✅ (with intent routing) | ⚠️ Iris AI | ⚠️ Vera | ✅ Jurist Search Agent | ✅ AskSirion Search | ⚠️ Prompt Lab | ✅ Conversational | ⚠️ Limited |
| **SLA Extraction Agent** | ✅ | ❌ | ⚠️ Partial | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Schema Extraction Agent** | ✅ 15 schemas, 1,235 fields | ❌ | ✅ | ❌ | ⚠️ Partial | ✅ | ⚠️ Partial | ✅ 1,400+ models |
| **Contract Drafting Agent** | ❌ | ⚠️ AI Doc Prep | ✅ Vera Composer | ✅ Jurist Drafting | ✅ AskSirion Draft | ⚠️ Screens | ✅ Lumi Go | ⚠️ Partial |
| **Agentic Redlining** | ❌ | ❌ | ✅ Vera Agents | ✅ Redlining Agent | ✅ AskSirion Redline | ⚠️ Screens | ✅ Auto-negotiation | ❌ |
| **Autonomous Negotiation** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Autopilot (AI-to-AI) | ❌ |
| **Institutional Memory** | ⚠️ Chat history only | ❌ | ⚠️ Contract data repo | ❌ | ⚠️ Limited | ❌ | ✅ Full portfolio memory | ❌ |
| **Agent Observability** | ✅ Langfuse | ❌ | ⚠️ Limited | ⚠️ Limited | ⚠️ Limited | ⚠️ Limited | ⚠️ Limited | ⚠️ Limited |

---

## 11. Alerts & Notifications

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Luminance | Conga |
|---------|-----------|----------|---------|----------|--------|---------|-----------|-------|
| **Email Notifications** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Microsoft Teams** | ✅ Webhooks | ✅ | ✅ | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ |
| **Threshold-Based Alerts** | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited | ⚠️ Limited |
| **Alert Severity Levels** | ✅ 10 categories | ❌ | ✅ | ❌ | ✅ | ⚠️ Partial | ❌ | ⚠️ Partial |
| **Alert Acknowledge/Resolve/Escalate** | ✅ Full lifecycle | ❌ | ✅ | ❌ | ✅ | ⚠️ Partial | ❌ | ⚠️ Partial |
| **Notification Rules Engine** | ✅ Fully configurable (event types, conditions, channels) | ⚠️ Basic | ✅ | ⚠️ Basic | ✅ | ✅ | ⚠️ Basic | ⚠️ Basic |
| **In-App Notifications** | ⚠️ Backend only | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 12. Dashboards & Reporting

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Luminance | Conga |
|---------|-----------|----------|---------|----------|--------|---------|-----------|-------|
| **Role-Based Dashboards** | ✅ 4 roles | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited | ✅ |
| **Executive Dashboard** | ✅ | ⚠️ Basic | ✅ | ⚠️ Basic | ✅ | ✅ | ⚠️ Basic | ✅ |
| **SLA Compliance Dashboard** | ✅ | ❌ | ✅ | ❌ | ✅ | ⚠️ Partial | ❌ | ⚠️ Partial |
| **Portfolio Risk Dashboard** | ✅ | ❌ | ✅ | ⚠️ Jurist insights | ✅ | ⚠️ Partial | ✅ | ⚠️ Limited |
| **Obligation Status Tracker** | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ (Dec 2025) | ⚠️ Limited | ⚠️ Partial |
| **AI-Generated Visualizations** | ✅ LLM-enhanced | ❌ | ⚠️ Vera Analytics | ❌ | ⚠️ Limited | ❌ | ❌ | ❌ |
| **CSV/Excel Export** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Custom Report Builder** | ✅ Planned | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited | ✅ |

---

## 13. Integrations

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Luminance | Conga |
|---------|-----------|----------|---------|----------|--------|---------|-----------|-------|
| **Salesforce** | ⚠️ Stub | ✅ Native | ✅ | ✅ | ✅ | ✅ Workato | ⚠️ Limited | ✅ Native |
| **SAP** | ✅ Planned | ⚠️ Limited | ✅ Strategic | ⚠️ Limited | ✅ | ✅ Workato | ⚠️ Limited | ⚠️ Limited |
| **Workday** | ✅ Planned | ⚠️ Limited | ✅ Strategic | ⚠️ Limited | ✅ | ✅ Workato | ⚠️ Limited | ⚠️ Limited |
| **ServiceNow** | ⚠️ Stub (not full integration yet) | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ Workato | ⚠️ Limited | ⚠️ Limited |
| **Microsoft 365** | ✅ Planned | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **E-Signature** | ✅ Planned | ✅ Native | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Generic API/Webhooks** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **iPaaS (Workato/Zapier)** | ✅ Planned | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ Native | ⚠️ Limited | ⚠️ Limited |

---

## 14. Security & Compliance

| Feature | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Luminance | Conga |
|---------|-----------|----------|---------|----------|--------|---------|-----------|-------|
| **SOC 2 Type II** | ✅ Planned | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **GDPR Compliance** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **SSO/SAML** | ✅ Planned | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **RBAC** | ✅ 5 roles | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Business Unit Hierarchy** | ✅ Multi-level BU scoping | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited | ⚠️ Limited |
| **External Portal / Sharing** | ✅ Secure token-based sharing | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ⚠️ Limited | ⚠️ Limited | ⚠️ Limited |
| **ABAC (Attribute-Based)** | ❌ RBAC only | ⚠️ Limited | ✅ | ⚠️ Limited | ✅ | ✅ | ⚠️ Limited | ⚠️ Limited |
| **Full Audit Trail** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Data Encryption** | ✅ In transit + at rest | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **AI Data Zero-Retention** | ✅ | ❌ | ⚠️ Limited | ⚠️ Limited | ⚠️ Limited | ⚠️ Limited | ⚠️ Limited | ⚠️ Limited |
| **Private LLM Deployment** | ✅ Planned | ❌ | ⚠️ Vera infrastructure | ❌ | ⚠️ GPU investment (Haveli) | ❌ | ✅ Proprietary models | ❌ |

---

## 15. Implementation & Time-to-Value

| Metric | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Luminance | Conga |
|--------|-----------|----------|---------|----------|--------|---------|-----------|-------|
| **Typical Implementation** | Days-Weeks | 3-6 months | 12-18 months | 2-4 months | 6-12 months | 3-6 months | Weeks | 3-6 months |
| **Time to First Value** | Hours (after setup) | Weeks | Months | Weeks | Weeks | Weeks | Days | Weeks |
| **Professional Services** | Medium (technical) | High | Very High | Medium | High | Medium-High | Medium | High |
| **Self-Service Setup** | ❌ Not Implemented | ⚠️ Limited | ❌ | ⚠️ Partial | ⚠️ Limited | ⚠️ Partial | ⚠️ Partial | ⚠️ Limited |
| **Cycle Time Improvement** | 50-70% (extraction) | 30-50% | 40-60% | 50-70% | 50-80% (claimed) | Up to 80% (claimed) | 50-70% | 30% (reported) |

---

## 16. Pricing Model

| Aspect | Evaluetor | DocuSign | Icertis | Ironclad | Sirion | Agiloft | Luminance | Conga |
|--------|-----------|----------|---------|----------|--------|---------|-----------|-------|
| **Model** | Asset-based (unlimited users) | Per-user + IAM tiers | Per-user + volume | Per-user | Enterprise deals | Per-user | Enterprise deals | Per-user + modules |
| **Unlimited Users** | ✅ All tiers | ❌ | ❌ | ❌ | Negotiable | ❌ | Negotiable | ❌ |
| **AI Included** | ✅ All tiers | ⚠️ Premium tier | ⚠️ Add-on (Vera) | ✅ | ✅ | ⚠️ Add-on (Screens) | ✅ | ⚠️ Add-on |
| **Entry Price** | ~$20K/year | High | Very High | Medium-High | Very High | Medium | High | Medium-High |
| **Enterprise** | ~$100K/year | Very High | Very High | Very High | Very High | High | Very High | High |
| **Implementation Fees** | $5-15K | $25-100K | $100K-500K+ | $25-75K | $50-200K | $25-75K | $50-150K | $25-100K |

> **Market trend (2025-2026):** 70% of vendors projected to move away from pure per-seat pricing by 2028 (IDC). Hybrid models (per-seat + usage) growing fastest at 21% median revenue growth. Evaluetor's asset-based unlimited-users model is a genuine differentiator — no major CLM vendor has adopted this approach.

---

## 17. Summary: Competitive Positioning Matrix

| Dimension | Leader(s) | Evaluetor Position |
|-----------|-----------|-------------------|
| **Pre-Signature (Authoring/Negotiation)** | Ironclad, Luminance, Icertis (Vera) | ❌ **Not Implemented** |
| **Autonomous Negotiation** | Luminance (Autopilot) | ❌ **Not on roadmap** |
| **Post-Signature (Execution Management)** | Sirion, Evaluetor | ✅ **Strong** (SLAs, obligations, compliance) |
| **AI Extraction (Analysis)** | Sirion, Evaluetor, Conga | ✅ **Strong** (9+ agents, 15 schemas, ~405 endpoints) |
| **Governance Bridge** | Evaluetor | ✅ **Unique** (automated contract → org/relationship/KPI/improvement pipeline) |
| **Perception Gap Scoring** | Evaluetor | ✅ **Unique** (dual-perspective internal vs external with severity classification) |
| **Agentic AI Architecture** | Ironclad (Rivet), Sirion (agentOS), Evaluetor | ✅ **Strong** (Agent Squad + Langfuse) |
| **Custom Agent Building** | Sirion (agentOS) | ❌ **Fixed agents only** |
| **Workflow Backend** | Icertis, Sirion, Agiloft | ✅ **Competitive** (API-only, no UI) |
| **Visual Workflow Builder** | Ironclad, Agiloft, DocuSign/Monday.com | ❌ **Not Implemented** |
| **Enterprise Integrations** | Icertis, Sirion, Conga | ⚠️ **Stubs only** |
| **Time-to-Value (Analysis)** | Evaluetor, Luminance | ✅ **Fast** (upload -> insights in hours) |
| **Relationship Governance** | Evaluetor | ✅ **Unique** (KPIs, perception, surveys) |
| **Unlimited-Users Pricing** | Evaluetor | ✅ **Unique** in market |
| **Knowledge Graph / Auto-Linking** | Evaluetor, Luminance | ✅ **Differentiated** (6-signal weighted scoring) |
| **LLM Observability** | Evaluetor (Langfuse) | ✅ **Differentiated** |
| **External Portal** | Evaluetor, Icertis, Sirion | ✅ **Implemented** (secure token-based sharing) |
| **Business Unit Hierarchy** | Evaluetor, Icertis, Sirion | ✅ **Implemented** (multi-level BU scoping) |
| **Contract Health Score** | Evaluetor, Sirion | ✅ **Differentiated** (composite: Risk 30% + SLA 40% + Obligation 30%) |
| **Institutional Memory** | Luminance | ⚠️ **Chat history only** |
| **Template/Clause Libraries** | Ironclad, Icertis | ❌ **Not Implemented** |
| **Region Sharding / GDPR** | Icertis, Sirion | ❌ **Not Implemented** |

---

## 18. Key Takeaways

### Evaluetor Strengths (Implemented & Differentiated):

1. **Governance Bridge** (unique): Automated contract-to-governance pipeline — contract uploads auto-create organizations, business relationships, KPIs, and improvement points. No competitor has this automated pipeline connecting contract intelligence to relationship governance
2. **Perception Gap Scoring** (unique): Dual-perspective KPI scoring (internal vs external) with gap severity classification. No competitor measures relationship health this way
3. **Relationship Governance** (unique): Full governance suite — KPI perception scoring, gap analysis, improvement tracking, multi-party surveys, external survey portal — no competitor offers this
4. **Unlimited-Users Pricing** (unique): Asset-based model eliminates seat-cost anxiety for extending CLM access to business users
5. **Post-Signature Management**: SLA monitoring, obligation tracking, compliance, breach detection, milestone tracking, contract health scores (Risk 30% + SLA 40% + Obligation 30%) — on par with Sirion
6. **9+ AI Extraction Agents** (11 agent files): Metadata, clauses (31 types), obligations, SLAs, risks (10 categories), renewals, regulatory, schema (15 types / 1,235 fields), intent-routed Q&A — more specialized agents than most competitors (Ironclad has 6 via Rivet)
7. **Auto-Link Detection**: 6-signal weighted scoring (counterparty, type hierarchy, semantic similarity, filename pattern, batch, date proximity) — only Luminance partially addresses contract relationship detection
8. **Knowledge Graph**: Entity/relationship graph with deep contract intelligence
9. **LLM Observability**: Full Langfuse tracing — no competitor offers comparable agent observability
10. **Intent Router with LLM Visualizations**: Structured query routing with auto-generated charts — unique capability
11. **External Portal**: Secure token-based contract sharing with external users
12. **Business Unit Hierarchy**: Multi-level organizational scoping for contract access
13. **Configurable Notification Rules**: Event-driven notification engine with conditions and channel routing
14. **Fast Time-to-Value**: Upload to AI insights in hours vs weeks/months for incumbents
15. **Platform Scale**: 44 routers, ~405 API endpoints, 53 models, ~77 database tables, 38 services, 37 frontend pages

### Evaluetor Gaps (Strategic Priorities):

1. **Contract Authoring & Negotiation**: No browser editor, templates, clause library, or AI drafting — the biggest gap vs Ironclad/Luminance
2. **Autonomous Negotiation**: Luminance's Autopilot (AI-to-AI) is the market frontier — consider roadmap implications
3. **Visual Workflow Builder**: Backend engine exists but no UI — Ironclad and Agiloft lead here
4. **Enterprise Integrations**: ServiceNow, Salesforce are stubs — critical for enterprise sales
5. **Custom Agent Building**: Sirion's agentOS allows no-code custom agents — Evaluetor's agents are fixed
6. **No-Code Configuration**: DocuSign/Monday.com and Agiloft push no-code for non-technical users
7. **Institutional Memory**: Luminance retains negotiation context across entire portfolios
8. **Invoice Reconciliation / Revenue Leakage**: Sirion and Conga (with PROS) lead here

### Market Positioning Strategy:

**Evaluetor is best positioned for organizations that:**
- ✅ Have existing contract portfolios needing immediate AI-powered analysis
- ✅ Need post-signature governance (obligations, SLAs, compliance, renewals)
- ✅ Want automated contract-to-governance workflows (governance bridge — unique capability)
- ✅ Want relationship intelligence with dual-perspective perception gap scoring (unique capability)
- ✅ Need external stakeholder access via secure token-based sharing
- ✅ Require business unit hierarchy for organizational contract scoping
- ✅ Prefer unlimited-users pricing over per-seat models
- ✅ Value AI transparency (Langfuse observability)
- ✅ Want fast time-to-value (hours, not months)

**Key competitive wedges:**
1. **vs DocuSign/Icertis**: Faster time-to-value, unlimited users, deeper AI extraction, governance bridge, perception gap scoring
2. **vs Ironclad**: Stronger post-signature management, unlimited users, SLA/obligation tracking, governance bridge, more AI agents (9+ vs 6)
3. **vs Sirion**: Governance bridge (unique), perception gap scoring (unique), unlimited users, knowledge graph, faster deployment
4. **vs Luminance**: Post-signature management, governance bridge, perception gap scoring, structured dashboards, health scores, lower cost

---

## Appendix: Recent Vendor Moves (2025-2026)

| Date | Vendor | Event |
|------|--------|-------|
| Apr 2025 | DocuSign | Launched AI Contract Agents (Iris AI) |
| Apr 2025 | Summize | Launched Summize Intelligent Agents (SIA) |
| Early 2025 | Agiloft | Acquired Screens (AI contract review) |
| Sep 2025 | Icertis | Launched Vera AI system with Vera Agents |
| Oct 2025 | Sirion | Launched AskSirion 360 conversational contracting |
| Nov 2025 | Ironclad | Launched next wave of AI Agents (6 agents via Rivet) |
| Nov 2025 | DocuSign | Monday.com partnership for no-code workflows |
| Dec 2025 | Agiloft | Launched AI-driven Obligation Management |
| Jan 2026 | DocuSign | AI Signer Experience (plain-English summaries) |
| Jan 2026 | Luminance | Largest platform update — multi-agent with institutional memory |
| Feb 2026 | Sirion | Haveli Investments took majority stake |
| Feb 2026 | Conga | Acquired PROS Holdings B2B business |

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Full support / Industry-leading |
| ⚠️ | Partial support / Basic capability |
| ❌ | Not supported / Not available |

---

*Document Version: 3.0*
*Last Updated: March 2026*
*Author: Development Team*
*Based on: Codebase verification (44 routers, ~405 endpoints, 53 models, ~77 tables), market research (March 2026), vendor documentation, Gartner MQ 2025, Forrester Wave 2025, analyst reports*

**Version History:**
- v3.0: Updated Evaluetor capabilities to reflect current state (44 routers, ~405 endpoints, 53 models, ~77 tables, 38 services, 11 agent files, 37 frontend pages). Added Governance Bridge as key differentiator across all comparison tables — automated contract-to-governance pipeline (unique, no competitor has this). Added Perception Gap Scoring (dual-perspective with severity classification). Updated auto-link detection to 6-signal weighted scoring. Added Contract Health Score (composite formula). Added External Portal (secure token sharing), Business Unit Hierarchy, and configurable Notification Rules. Updated ServiceNow to stub status. Expanded Key Takeaways from 8 to 15 strengths.
- v2.0: Major update — added Luminance, Conga, SpotDraft, Summize as competitors. Updated all vendors with 2025-2026 AI agent launches (Vera, Rivet, agentOS, Iris AI, Autopilot, Screens). Added market context ($1.24B market), autonomous negotiation category, institutional memory comparison, vendor timeline appendix. Expanded from 7 to 8 vendors in comparison tables. Updated pricing with market trends.
- v1.2: Updated schema extraction (15 types, 1,235 fields), auto-detected contract family linking, competitive comparison updates
- v1.1: Corrected Evaluetor features based on actual codebase verification (removed marketing claims not backed by implementation)
- v1.0: Initial document with competitive analysis
