# Implementation Plan: Strengthening Evaluetor's 4 Key Differentiators

**Created:** March 2026
**Scope:** 6 phases, 85 tasks, estimated 8-10 weeks

---

## Phase Overview

| Phase | Focus | Tasks | Depends On | Estimated Effort |
|-------|-------|-------|------------|-----------------|
| **11** | Relationship Governance Frontend | 22 tasks | None (APIs exist) | 2 weeks |
| **12** | Knowledge Graph Visualization + Cross-Contract Intelligence | 18 tasks | None | 1.5 weeks |
| **13** | Langfuse Full Observability | 15 tasks | None | 1 week |
| **14** | ServiceNow + Salesforce Real Integration | 14 tasks | Trial credentials | 1.5 weeks |
| **15** | Pricing & Usage Visibility | 8 tasks | Phase 13 (cost tracking) | 0.5 weeks |
| **16** | Cross-Differentiator Connections | 8 tasks | Phases 11-13 | 1 week |

Phases 11-13 can run in parallel. Phase 14 can run in parallel with anything. Phase 15 depends on 13. Phase 16 ties everything together.

---

## Phase 11: Relationship Governance Frontend

**Goal:** Make the unique relationship governance backend visible via a full frontend UI.

**Current State:** 9 entities, 40+ API endpoints, zero frontend pages for core features (organizations, relationships, KPIs, perception, improvements, surveys). Business Units and External Users pages exist.

### 11.1 — Relationship Governance Navigation & Layout

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 11.1.1 | Add "Governance" section to Sidebar | Add collapsible nav group: Organizations, Relationships, KPIs, Surveys, Improvements | Sidebar shows Governance section for admin/legal roles |
| 11.1.2 | Add routes to App.tsx | `/organizations`, `/relationships`, `/relationships/:id`, `/kpis`, `/surveys`, `/improvements` | All routes render placeholder pages behind auth |
| 11.1.3 | Add TypeScript types | Create `src/types/governance.ts` with Organization, BusinessRelationship, RelationshipTeam, KPI, PerceptionScore, PerceptionGap, ImprovementPoint, Survey types | Types match backend Pydantic schemas |
| 11.1.4 | Add API client methods | Add to `src/lib/api.ts`: getOrganizations, createOrganization, getRelationships, getRelationship, getKPIs, submitPerceptionScore, getGaps, getImprovements, getSurveyTemplates, etc. | All governance endpoints callable from frontend |

### 11.2 — Organizations Page

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 11.2.1 | OrganizationsPage — list view | Table with columns: Name, Type (customer/vendor/partner), Industry, Region, Primary Contact, Relationship Count, Status. Filters by type, search by name | Lists all tenant organizations, paginated |
| 11.2.2 | Create/Edit Organization modal | Form: name, code, org_type, industry, size, region, country, website, address, primary contact (name, email, phone), relationship_owner | Creates/updates organization via API |
| 11.2.3 | Organization detail panel | Slide-over or page showing: org details, linked relationships, linked contracts (by counterparty match), contact info | Click org row → see full details |

### 11.3 — Relationships Page

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 11.3.1 | RelationshipsPage — list view | Card grid or table: Org A ↔ Org B, Type, Status, Governance Tier, Health Score (colored badge), Annual Value | Shows all relationships with health indicators |
| 11.3.2 | Create Relationship modal | Form: select Org A + Org B (dropdowns), relationship_type, governance_tier, start_date, description, annual_value, currency | Creates relationship via API |
| 11.3.3 | RelationshipDetailPage — header & overview | Route: `/relationships/:id`. Header: orgs, type, status, health score gauge. Tabs: Overview, KPIs, Team, Contracts, Improvements, Surveys | Full relationship detail page loads with tabs |
| 11.3.4 | RelationshipDetailPage — Team tab | Table: member name, role, responsibilities, primary contact badge, receives alerts badge. Add/remove member buttons | View and manage team members |
| 11.3.5 | RelationshipDetailPage — Contracts tab | List contracts where `business_relationship_id` matches OR counterparty matches either org. Show contract type, status, risk, expiry | See all contracts linked to this relationship |
| 11.3.6 | RelationshipDetailPage — Overview tab | Key stats: health score, active KPIs count, open improvements, perception gap severity distribution, upcoming survey | At-a-glance relationship health |

### 11.4 — KPI Perception Scorecard (Core Differentiator UI)

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 11.4.1 | KPIs tab on RelationshipDetailPage | Table: KPI name, category, target, current value, weight. For perception-based KPIs: Internal Score, External Score, Gap, Severity badge (color-coded) | Shows all KPIs with perception gap visualization |
| 11.4.2 | Perception Score submission form | Modal: select KPI, select perspective (internal/external), score (1-10 slider), period (e.g., 2026-Q1), comments. Submit creates PerceptionScore | Internal users can submit perception scores |
| 11.4.3 | Perception Gap chart component | `PerceptionGapChart.tsx` — horizontal bar chart showing internal vs external scores side-by-side per KPI. Gap magnitude highlighted. Severity color coding: green (aligned), yellow (moderate), orange (significant), red (critical) | Visual gap comparison for all KPIs in a relationship |
| 11.4.4 | Perception trend sparklines | For each KPI, show last 4 periods as a sparkline (gap trending up/down). Use `GET /kpis/{id}/gaps` endpoint | Gap trends visible at a glance |
| 11.4.5 | KPI create/edit modal | Form: name, description, category, measurement_type, target_value, amber/red thresholds, weight, is_perception_based, frequency | Admin can define new KPIs for a relationship |

### 11.5 — Improvements Page

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 11.5.1 | Improvements tab on RelationshipDetailPage | Table/kanban: title, priority (badge), status, source (perception_gap/sla_breach/etc), owner, target_date, progress % bar | Shows improvement backlog for relationship |
| 11.5.2 | Generate Improvements from Gaps button | Button on KPI tab: "Generate Improvements". Calls `POST /improvements/generate-from-gaps`. Shows created improvements count | One-click improvement generation from perception gaps |
| 11.5.3 | Improvement detail panel | Slide-over: description, linked KPI, linked gap, target/actual outcome, impact score. Action items checklist with status toggles | View and manage improvement with action items |
| 11.5.4 | Create Improvement modal | Form: title, description, priority, source, owner, target_date, linked KPI | Manually create improvement points |

### 11.6 — Surveys

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 11.6.1 | Survey Templates page | `/surveys` — list templates with name, type, question count, status. Create template button | CRUD for survey templates |
| 11.6.2 | Survey Template Builder | Add/edit/reorder questions. Question types: rating, rating_5, nps, single_choice, multiple_choice, text, yes_no. Link questions to KPIs | Full template builder with drag-reorder |
| 11.6.3 | Survey Instances management | Create instance from template: select relationship, period, due date. Send survey (generate token). Track response rate | End-to-end survey lifecycle |
| 11.6.4 | Survey Results dashboard | Per instance: response rate, average scores per question, NPS calculation, breakdown by respondent. Highlight KPI-linked questions with perception scores auto-created | Visualize survey results with KPI linkage |

---

## Phase 12: Knowledge Graph Visualization + Cross-Contract Intelligence

**Goal:** Make the KG visible via an interactive graph, and extend it to cross-contract intelligence.

**Current State:** 8 entity types, 10 relationship types, 2-pass LLM extraction, 7-signal auto-link detection. SuggestedLinksPanel exists. No KG visualization. KG is single-contract scoped.

### 12.1 — Knowledge Graph Visualization

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 12.1.1 | Install graph visualization library | Add `react-force-graph-2d` (or `@visx/network`). Lightweight, works with React | Library available in frontend |
| 12.1.2 | KnowledgeGraphPanel component | New component for ContractViewPage. Fetch `GET /api/knowledge-graph/contracts/{id}`. Render force-directed graph: nodes = entities (circle, color by type), edges = relationships (labeled) | Interactive KG visualization on contract detail |
| 12.1.3 | Node styling by entity type | Color scheme: party=blue, clause=purple, obligation=red, term=gray, date=green, amount=orange, jurisdiction=teal, sla_metric=indigo. Size by confidence score | Entity types visually distinguishable |
| 12.1.4 | Node click interaction | Click node → sidebar panel showing: entity name, type, description, source text, confidence, page/section reference, all connected relationships | Inspect any entity in detail |
| 12.1.5 | Edge labels and filtering | Show relationship type on edges. Toolbar with checkboxes to filter by entity type and relationship type | Users can focus on specific entity/relationship types |
| 12.1.6 | Risk patterns overlay | Call `GET /api/knowledge-graph/contracts/{id}/risk-analysis`. Highlight risky nodes: red border for unlimited obligations, yellow for missing jurisdictions, orange for undefined terms | Risk patterns visible on the graph |
| 12.1.7 | Add KG tab to ContractViewPage | New "Knowledge Graph" tab alongside existing tabs. Shows graph + stats (entity count by type, relationship count) | KG accessible from contract detail page |

### 12.2 — Cross-Contract Knowledge Graph

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 12.2.1 | Backend: `merge_entities_cross_contract()` service | New method in `knowledge_graph_service.py`. For a tenant: find KG entities with same normalized name + type across contracts. Create `KGEntityCluster` records linking them | Cross-contract entity merging runs after KG extraction |
| 12.2.2 | Backend: `KGEntityCluster` model | New model: id, tenant_id, canonical_name, entity_type, entity_ids (array of KGEntity UUIDs), contract_count, first_seen, last_seen | Entity clusters stored in DB |
| 12.2.3 | Alembic migration for KGEntityCluster | Create table `kg_entity_clusters` with indexes on tenant_id, entity_type, canonical_name | Migration runs cleanly |
| 12.2.4 | Backend: Counterparty Profile endpoint | `GET /api/knowledge-graph/counterparty/{org_name}/profile` — aggregates across all contracts with this counterparty: common clause types, typical payment terms, average risk level, SLA patterns, obligation patterns | Counterparty intelligence from KG data |
| 12.2.5 | Backend: Anomaly detection endpoint | `GET /api/knowledge-graph/contracts/{id}/anomalies` — compare this contract's KG entities against the tenant-wide patterns. Flag deviations: unusual payment terms, missing standard clauses, different jurisdiction | Deviations from portfolio patterns detected |
| 12.2.6 | Trigger cross-contract merge after KG extraction | In `_run_deep_analysis()`, after KG extraction completes, call `merge_entities_cross_contract()` for the contract's tenant | Merge runs automatically on new contracts |

### 12.3 — Auto-Link Enhancements

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 12.3.1 | Add KG entity overlap signal | 8th signal in `auto_link_detector.py`: count shared KG entities (same name+type) between source and candidate contracts. Weight: 0.20. Normalize by total entities | Auto-link quality improves with KG data |
| 12.3.2 | Suggested Links dashboard page | New page `/suggested-links` showing all pending suggestions across tenant. Group by source contract. Batch approve/reject. Filter by confidence, link type | Admin can review all suggestions in one place |
| 12.3.3 | Auto-link notification | When high-confidence suggestions (>0.7) are created, create an in-app notification for the contract owner | Users aware of new link suggestions |
| 12.3.4 | Portfolio graph view | New page `/portfolio-graph` — force-directed graph of all contracts in tenant. Nodes = contracts (size by value, color by type). Edges = established links + high-confidence suggestions (dashed) | Bird's-eye view of contract portfolio relationships |
| 12.3.5 | Contract family tree component | On ContractViewPage, show hierarchical tree: MSA → SOWs → Amendments → Schedules. Uses ContractLink data | Visual contract family hierarchy |

---

## Phase 13: Langfuse Full Observability

**Goal:** Instrument the complete processing pipeline, add cost tracking, quality feedback, and internal dashboard.

**Current State:** Orchestrator-level tracing, `@observe` on agent execution, 7 managed prompts, admin endpoints for status/sync. No cost tracking, no latency metrics, no quality feedback, no frontend dashboard.

### 13.1 — Full Pipeline Instrumentation

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 13.1.1 | Trace contract processing pipeline | In `indexer.py`: create root trace `contract_processing` at start of `index_contract()`. Add child spans for: parsing, chunking, section_classification, metadata_extraction, custom_fields, risk_assessment, auto_link_detection. Record duration, input size, output counts | Full pipeline visible in Langfuse dashboard |
| 13.1.2 | Trace vector store operations | In `vector_store.py`: wrap `add_documents()` and `query()` with Langfuse spans. Record: query text, num results, avg similarity score, duration_ms | Vector search latency and quality tracked |
| 13.1.3 | Trace KG extraction | In `knowledge_graph_extractor.py`: add spans for pass_1_extraction, orphan_resolution, entity_dedup. Record: chunk count, entities extracted, relationships created, orphans resolved | KG extraction pipeline fully traced |
| 13.1.4 | Trace intent router | In `intent_router.py`: add span for `detect_intent()` and each structured handler. Record: detected intent, handler used, data_summary size, LLM enhancement duration | Query routing decisions visible |

### 13.2 — Cost Tracking

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 13.2.1 | Token usage tracking wrapper | Create `src/services/llm_tracker.py`: wrapper around OpenAI calls that logs prompt_tokens, completion_tokens, model, estimated cost per call. Store in Langfuse generation metadata | Token usage captured for every LLM call |
| 13.2.2 | Cost per contract calculation | After `index_contract()` completes, sum all LLM costs from the trace. Store as `contract.processing_cost` (new Decimal column). Create alembic migration | Processing cost stored per contract |
| 13.2.3 | Cost metrics API endpoint | `GET /api/metrics/ai-costs` — returns: total cost (daily/weekly/monthly), cost per contract (avg, min, max), cost per agent, cost per tenant. Filterable by date range | Cost data queryable via API |
| 13.2.4 | Cost budget alerts | Per-tenant configurable monthly budget. If 80% consumed → warning, 100% → alert. Store in Tenant model as `ai_budget_monthly` | Budget monitoring prevents surprise costs |

### 13.3 — Quality Feedback

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 13.3.1 | Thumbs up/down on AI responses | In QueryPage chat UI: add thumbs up/down icons below each assistant message. On click, call `POST /api/query/feedback` with message_id, rating (positive/negative), optional comment | Users can rate AI response quality |
| 13.3.2 | Backend feedback endpoint | `POST /api/query/feedback` — stores feedback in `AIFeedback` model (message_id, session_id, rating, comment, user_id). Logs to Langfuse as score on the trace | Feedback stored in DB and Langfuse |
| 13.3.3 | Feedback model + migration | New model `AIFeedback`: id, tenant_id, user_id, session_id, message_id, trace_id, rating (positive/negative), comment, created_at | Migration runs, model accessible |
| 13.3.4 | Link suggested-link approvals to Langfuse | When user approves/rejects a suggested link, log the decision as a Langfuse score on the auto-link trace. Score: 1.0 for approve, 0.0 for reject | Auto-link quality measurable over time |

### 13.4 — Observability Dashboard (Super Admin)

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 13.4.1 | ObservabilityPage (super admin only) | New page `/super-admin/observability`. Sections: AI Costs, Processing Performance, Agent Quality, System Health | Super admin can see operational AI metrics |
| 13.4.2 | AI Costs section | Charts: daily cost trend (bar), cost by agent (pie), cost per tenant (table). Data from `/api/metrics/ai-costs` | Cost trends visible at a glance |
| 13.4.3 | Processing Performance section | Charts: avg processing time per contract (trend), contracts processed per day, error rate by stage. Data from Langfuse traces | Processing bottlenecks identifiable |

---

## Phase 14: ServiceNow + Salesforce Real Integration

**Goal:** Connect to real SNOW/SFDC trial instances, replacing stubs with live data flows.

**Current State:** Production-ready SNOW client (Basic Auth), partial SFDC client (OAuth2 mock). SLA comparison engine works with stub data. 15 pre-configured SLA metrics.

**Prerequisites:** SNOW Developer Instance URL + credentials, SFDC Developer Org + Connected App credentials.

### 14.1 — ServiceNow Real Connection

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 14.1.1 | Configure SNOW Developer Instance | Create IntegrationConfig record via API or seed script: system=servicenow, base_url, auth_type=basic, credentials (username/password) | Config stored in DB |
| 14.1.2 | Add SNOW connector toggle | In `connectors.py` router: check for active IntegrationConfig with system=servicenow. If exists and healthy → use real client. Otherwise → fall back to stub. Add `use_real` query param for explicit override | Seamless stub-to-real switching |
| 14.1.3 | Seed SNOW with sample incidents | Script: `scripts/seed_servicenow.py`. Creates 10-15 incidents in SNOW trial matching the SLA categories (P1-P4, various categories). Use REST API | Trial instance has realistic data |
| 14.1.4 | Test SLA comparison with real data | Run `POST /api/connectors/compare/{contract_id}` against real SNOW. Verify: incidents fetched, SLA actuals calculated, breach detection works, alerts created | End-to-end SLA comparison with live SNOW |
| 14.1.5 | Incident creation from CLM alerts | When SLA breach detected → auto-create incident in SNOW with details: contract name, SLA name, breach severity, deviation %. Link incident number back to SLAAlert | CLM → SNOW incident flow working |
| 14.1.6 | SNOW incident status sync | Scheduled job: poll SNOW for incident status updates. When incident resolved in SNOW → update SLAAlert status in CLM | Two-way sync between CLM and SNOW |

### 14.2 — Salesforce Real Connection

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 14.2.1 | Implement OAuth2 password grant flow | In `salesforce.py`: implement `_authenticate()` with username-password OAuth2 flow. Store access_token, refresh_token, instance_url. Handle token expiry | Real SFDC auth working |
| 14.2.2 | Configure SFDC Connected App | Create Connected App in SFDC trial. Set OAuth scopes (api, refresh_token). Store client_id/secret in IntegrationConfig | Connected App configured |
| 14.2.3 | Create custom fields in SFDC | In SFDC trial, create on Account object: `Contract_Health__c` (Picklist: healthy/at_risk/critical), `Active_Contracts__c` (Number), `Renewal_Date__c` (Date), `Contract_Value__c` (Currency) | Custom fields exist in SFDC |
| 14.2.4 | Contract health sync to SFDC | When contract risk_level changes or renewal approaches → update linked SFDC Account with health status. Match by counterparty name → Account name | Contract health visible in SFDC |
| 14.2.5 | Renewal task creation in SFDC | When renewal notice triggered → create Task in SFDC: "Review renewal for {contract.filename}", due_date = notice_deadline, priority = High | Renewal tasks appear in SFDC |
| 14.2.6 | SFDC Account → Organization sync | Seed script: `scripts/sync_sfdc_accounts.py`. Pull Accounts from SFDC → create/update Organizations in CLM. Map Account.Name → Organization.name, Account.Industry → Organization.industry | SFDC accounts visible as CLM organizations |
| 14.2.7 | Integration status dashboard component | On SettingsPage: show connected integrations with health status, last sync time, request counts, error rate. Refresh/test connectivity buttons | Admin can see integration health |
| 14.2.8 | Connector demo mode toggle | Settings toggle: "Use demo data" (stubs) vs "Use live integrations". Default to demo. When live: validate credentials before switching | Easy switching between demo and real data |

---

## Phase 15: Pricing & Usage Visibility

**Goal:** Make the unlimited-users pricing model tangible and visible.

**Depends on:** Phase 13 (cost tracking provides the data).

### 15.1 — Usage Dashboard

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 15.1.1 | Tenant Usage API endpoint | `GET /api/tenants/{id}/usage` — returns: total_contracts, total_users, total_ai_operations (queries + extractions), ai_cost_this_month, contract_value_under_management, storage_used_mb | Usage data queryable |
| 15.1.2 | Usage Dashboard component on SettingsPage | Section on SettingsPage (admin role): contracts used vs limit (progress bar), total users (no limit badge), AI operations this month, processing cost | Admin sees tenant usage |
| 15.1.3 | Per-seat cost comparison callout | Below usage stats: "Your {N} users would cost ${X}/month at per-seat pricing" (calculate at $50/user/month industry avg). Show savings | Pricing advantage quantified |
| 15.1.4 | Contract value tier indicator | Show: "Contract value under management: ${X}M". Map to tier (Starter/Pro/Enterprise). Show next tier threshold | Value-based tier visible |

### 15.2 — Tenant Plan Enhancements

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 15.2.1 | Add AI budget fields to Tenant model | New fields: ai_budget_monthly (Decimal), ai_operations_limit (Integer, nullable=unlimited). Migration | Plan-based AI limits configurable |
| 15.2.2 | Feature gating by tier | Middleware: check tenant.plan against feature requirements. Starter: no relationship governance, no custom schemas. Pro: full features. Enterprise: API access + custom agents | Feature access controlled by plan |
| 15.2.3 | Upgrade prompt component | When user accesses gated feature → show upgrade modal: "Relationship Governance is available on Pro plan. Your plan: Starter. Contact sales to upgrade" | Upgrade path clear to users |
| 15.2.4 | Super Admin plan management | On TenantDetailPage: edit plan, set contract limit, set AI budget. Show usage vs limits | Super admin can manage tenant plans |

---

## Phase 16: Cross-Differentiator Connections

**Goal:** Wire the four differentiators together so they reinforce each other.

**Depends on:** Phases 11-13 completed.

### 16.1 — Contract ↔ Relationship Auto-Linking

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 16.1.1 | Auto-suggest relationship linkage on upload | In indexer pipeline, after metadata extraction: if counterparty matches an Organization name → find active BusinessRelationship → suggest linking contract to relationship. Store as `suggested_relationship_id` on contract | Upload auto-suggests relationship link |
| 16.1.2 | Relationship link confirmation UI | On ContractViewPage: banner "This contract may belong to relationship: {Org A ↔ Org B}. Link it?" with Confirm/Dismiss buttons | User confirms/dismisses relationship link |
| 16.1.3 | Relationship health auto-calculation | Implement `calculate_health_score()` in relationships service. Composite: obligation_completion (30%), sla_compliance (25%), perception_gap_avg (30%), improvement_progress (15%). Recalculate on: score submission, obligation status change, SLA comparison | Health score computed from real data |

### 16.2 — KG → Perception Intelligence

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 16.2.1 | Auto-suggest KPIs from contract KG | When contract linked to relationship: analyze KG entities (SLA metrics, obligations) → suggest KPIs: "SLA: Uptime 99.9% — create KPI?" | KPIs auto-suggested from contract intelligence |
| 16.2.2 | Obligation → KPI linkage | Link obligations to KPIs: "Payment within 30 days" obligation → "Payment Timeliness" KPI. Track actual compliance as KPI current_value | Contract obligations feed KPI actuals |

### 16.3 — Observability → Relationship Governance

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 16.3.1 | Trace perception score submissions | Log perception score submissions to Langfuse: who scored, when, gap magnitude. Track scoring frequency per relationship | Governance activity observable |
| 16.3.2 | Survey response quality tracking | Track survey completion rates, response times, NPS trends in Langfuse. Alert on declining response rates | Survey engagement measurable |

### 16.4 — Integration → Governance

| # | Task | Details | Acceptance Criteria |
|---|------|---------|-------------------|
| 16.4.1 | SNOW incidents → Relationship health | When SLA breach creates SNOW incident → factor into relationship health score. Open P1 incidents = health -10 points per incident | External system data affects relationship health |

---

## Execution Order & Dependencies

```
Week 1-2:  Phase 11 (Governance Frontend)  ←── highest impact, no dependencies
           Phase 14 (SNOW/SFDC)            ←── parallel, independent

Week 2-3:  Phase 11 continued
           Phase 12 (KG Visualization)     ←── can start after 11.1 (nav/types)
           Phase 13 (Langfuse)             ←── parallel, independent

Week 3-4:  Phase 12 continued (cross-contract)
           Phase 13 continued
           Phase 14 continued

Week 5:    Phase 15 (Pricing/Usage)        ←── needs Phase 13 cost tracking
           Phase 16 (Cross-connections)    ←── needs 11, 12, 13

Week 6:    Phase 16 continued
           Testing, bug fixes, deployment
```

---

## Demo Script (After All Phases)

After implementation, the platform demo flow becomes:

1. **Upload** DemoSup MSA + 7 schedules → auto-classification, extraction, auto-link detection
2. **Knowledge Graph** → show interactive graph on MSA, click parties/obligations/SLAs
3. **Auto-Links** → schedules auto-linked to MSA, show portfolio graph
4. **Cross-Contract Intelligence** → "DemoSup typically has 30-day payment terms, this contract has 45 days" (anomaly)
5. **Relationship Governance** → create DemoSup organization, link relationship, show KPIs
6. **Perception Scoring** → submit internal score (8/10 delivery), external score (5/10) → gap analysis
7. **Generate Improvements** → one-click from perception gaps → action items
8. **Survey** → send satisfaction survey to external stakeholder → auto-creates perception scores
9. **SNOW Integration** → SLA breach detected → incident auto-created in ServiceNow
10. **SFDC Integration** → renewal approaching → task created in Salesforce
11. **Observability** → show Langfuse traces, cost per contract, quality feedback
12. **Usage Dashboard** → "47 users, $0 seat cost. At industry rates, you'd pay $28K/year"

---

## Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| Phase 11 is large (22 tasks) | Start with KPI Perception Scorecard (11.4) — it's the demo centerpiece |
| KG visualization performance with large contracts | Limit initial render to 100 nodes, add pagination/filtering |
| Cross-contract merge creates false positives | Use strict name normalization + same entity_type requirement. Add manual merge/split UI later |
| SNOW/SFDC trial limitations | Vanilla data is fine — seed scripts create realistic test data. Document trial expiry dates |
| Langfuse costs with full instrumentation | Use sampling (10% of requests) for non-critical spans. Full tracing for contract processing |
| Feature gating breaks existing users | Default all existing tenants to Enterprise tier. Only apply gating to new tenants |

---

## Success Metrics

| Differentiator | Metric | Target |
|----------------|--------|--------|
| **Relationship Governance** | Perception gap visible in UI | Yes/No (currently No) |
| **Relationship Governance** | End-to-end survey → gap → improvement flow | Working in demo |
| **Knowledge Graph** | Interactive visualization renders | < 2 seconds for 50-node graph |
| **Knowledge Graph** | Cross-contract anomalies detected | At least 1 anomaly per 10 contracts |
| **Langfuse Observability** | Full pipeline traced | 100% of contract processing stages |
| **Langfuse Observability** | Cost per contract known | Within 5% accuracy |
| **Integrations** | Real SNOW incident creation | < 5 second round-trip |
| **Integrations** | Real SFDC task creation | < 5 second round-trip |
| **Pricing** | Per-seat savings displayed | Calculated for every tenant |

---

*Document Version: 1.0*
*Last Updated: March 2026*
