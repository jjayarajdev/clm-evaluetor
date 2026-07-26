# Database Table Inventory & Hygiene

**Purpose:** Diligence-grade inventory of the database — what's populated, what's
empty and why, and which empty tables are dead vs. scaffolded-ahead-of-use.
**Prepared:** 2026-07-26
**Source:** production schema (verified against a byte-for-byte prod clone).
**Migration baseline:** `hyg01_drop_dead` applied.

---

## Summary

- **Total tables:** 82 (was 86; 4 dead tables dropped — see below).
- **Populated / actively used:** ~44 (the contract-intelligence core, AI pipeline,
  governance, platform, integrations, scheduler, notifications).
- **Empty:** 36 — **every one has live code**; they are features scaffolded ahead
  of use, not dead code. They populate when the relevant feature or integration
  is exercised.

> Key principle: **empty ≠ dead.** Only 4 tables were genuinely dead (no rows,
> no code usage) and were dropped. The rest are wired code paths.

---

## 1. Dropped (genuinely dead — removed in `hyg01`)

Empty, zero code usage, no inbound dependencies. Dropped with zero data loss.

| Table | Feature | Why dropped |
|---|---|---|
| `project_notes` | Project tracking | Unwired to any router/service; self-contained FK cluster |
| `project_tasks` | Project tracking | Unwired |
| `project_phases` | Project tracking | Unwired |
| `alert_configs` | Alerts | Superseded by `notification_rules`; only reference was a tenant-purge `DELETE` (removed) |

The two backing model files (`alert.py`, `project_task.py`) and their exports
were deleted. Model history remains in git if ever needed.

## 2. Retention (unbounded scratch tables)

No prior retention existed; these dwarfed the real data. Age-based prune added
(`scripts/prune_scratch_tables.py`, default 90 days). `audit_logs` is **excluded**
— kept for compliance.

| Table | Feature | Retention |
|---|---|---|
| `extraction_verifications` | AI extraction QA | prune > 90d (≈8.7k rows cleared) |
| `scheduler_job_history` | Scheduler | prune > 90d (≈1.3k rows cleared) |
| `suggested_contract_links` | Auto-linking suggestions | ⚠️ grows fast (~23k, all recent) — age-retention does **not** bound it; needs a lifecycle-based prune (keep-latest-per-contract / delete reviewed) |

---

## 3. Empty tables → feature → code

Every table below is empty in the current data but backed by live code.

| Table | Feature | Model class → file | Primary code (router · service) |
|---|---|---|---|
| **Compliance** (regulatory engine — page removed, engine still wired) | | | |
| `compliance_gaps` | Compliance | `ComplianceGap` → compliance_gap.py | `compliance.py` · `compliance_gap_detector.py`, `compliance_alert_service.py` |
| `regulatory_obligations` | Compliance | `RegulatoryObligation` → regulatory_obligation.py | `compliance.py` · `compliance_alert_service.py` |
| `industry_compliance_rules` | Compliance | `IndustryComplianceRule` → compliance_rule.py | `compliance.py` · `compliance_gap_detector.py` |
| **SLA monitoring** (real capability; needs a live performance feed) | | | |
| `sla_alerts` | SLA monitoring | `SLAAlert` → sla_alert.py | `alerts.py`, `notification_feed.py` · `sla_alert_service.py` |
| `sla_performances` | SLA monitoring | `SLAPerformance` → sla.py | `sla.py` · `sla_comparison.py`, `dashboard_service.py`, `vendor_service.py` |
| `sla_measurements` | SLA monitoring (actuals feed) | `SLAMeasurement` → integration.py | · `tenant_provisioner.py` |
| **External portal / sharing** | | | |
| `external_users` | External portal | `ExternalUser` → external_user.py | `external_portal.py`, `external_users.py` |
| `external_access_tokens` | External portal | `ExternalAccessToken` → external_access.py | `external_portal.py`, `external_users.py`, `surveys.py` |
| `contract_shares` | External portal | `ContractShare` → contract_share.py | `contracts.py`, `external_portal.py` |
| **Surveys** | | | |
| `survey_instances` | Surveys | `SurveyInstance` → survey.py | `surveys.py` |
| `survey_responses` | Surveys | `SurveyResponse` → survey.py | `surveys.py` |
| **Relationship governance (depth)** | | | |
| `perception_scores` | Governance / KPI | `PerceptionScore` → kpi.py | `kpis.py` · `kpi_service.py` |
| `perception_gaps` | Governance / KPI | `PerceptionGap` → kpi.py | `kpis.py`, `improvements.py` · `kpi_service.py` |
| `relationship_services` | Governance | `RelationshipService` → service_portfolio.py | `service_portfolio.py` · `governance_bridge.py` |
| `service_portfolios` | Governance | `ServicePortfolio` → service_portfolio.py | `service_portfolio.py` · `governance_bridge.py` |
| `relationship_teams` | Governance | `RelationshipTeam` → relationship.py | `relationships.py` |
| `relationship_status_history` | Governance | `RelationshipStatusHistory` → relationship_history.py | `relationships.py` |
| `organization_officers` | Governance | `OrganizationOfficer` → organization_officer.py | `organizations.py` |
| `improvement_actions` | Governance | `ImprovementAction` → improvement.py | `improvements.py` |
| **Document / exhibit deep-extraction** | | | |
| `contract_documents` | Doc structure | `ContractDocument` → contract_document.py | `contract_documents.py` |
| `document_sections` | Doc structure | `DocumentSection` → contract_document.py | `contract_documents.py` |
| `document_signatures` | Doc structure | `DocumentSignature` → contract_document.py | `contract_documents.py` |
| `contract_exhibits` | Exhibit extraction | `ContractExhibit` → exhibit.py | `contracts.py` · `exhibit_extraction.py` |
| `exhibit_fee_items` | Exhibit extraction | `ExhibitFeeItem` → exhibit.py | · `exhibit_extraction.py` |
| `contract_definitions` | Defined-terms extraction | `ContractDefinition` → definition.py | `contracts.py` · `definition_extraction.py` |
| `contract_process_steps` | Process extraction | `ContractProcessStep` → process_step.py | `contracts.py` · `process_extraction.py` |
| **Workflow / approvals engine** | | | |
| `workflow_definitions` | Workflow | `WorkflowDefinition` → workflow.py | `workflow_admin.py`, `monitor.py` |
| `workflow_steps` | Workflow | `WorkflowStep` → workflow.py | `workflow_admin.py` |
| `action_executions` | Workflow | `ActionExecution` → workflow.py | `monitor.py` · `calculation_service.py` |
| `approval_requests` | Approvals | `ApprovalRequest` → approval.py | `monitor.py` · `notification_service.py` |
| `approvers` | Approvals | `Approver` → approval.py | `workflow_admin.py` |
| `events` | Event engine | `Event` → event.py | `renewals.py`, `monitor.py` · `notification_service.py`, `calculation_service.py` |
| **Knowledge Graph** (engine kept; headless — see below) | | | |
| `kg_entities` | Knowledge Graph | `KGEntity` → knowledge_graph.py | · `knowledge_graph_extractor.py`, `knowledge_graph_service.py` |
| `kg_relationships` | Knowledge Graph | `KGRelationship` → knowledge_graph.py | · `knowledge_graph_extractor.py`, `knowledge_graph_service.py` |
| **Other** | | | |
| `clients` | Legacy client model | `Client` → client.py | `clients.py`, `contracts.py` · `upload.py`, `indexer.py` |
| `dashboard_cache` | Dashboard caching | `DashboardCache` → metric_snapshot.py | · `metric_snapshot_service.py`, `dashboard_service.py` |

---

## 4. Feature decisions for the enterprise review

The empty tables cluster into whole **features** that are either "finish" or
"retire the surface" calls — not code cleanup:

| Feature cluster | State | Recommendation |
|---|---|---|
| **Compliance** (`compliance_*`, `regulatory_obligations`, `industry_compliance_rules`) | Page removed; detection engine + router still registered | Decide: re-expose or retire the backend surface (dead endpoints = audit surface) |
| **Knowledge Graph** (`kg_*`) | Engine built, never populated; lapsed key + schema drift; headless-only per product decision | Park; fix `master_entity_id` migration if/when turned on |
| **External portal** (`external_*`, `contract_shares`) | Wired, unused | Keep if external sharing is in scope for Square One; else retire |
| **Surveys** (`survey_*`) | Wired, unused | Keep (governance feature) |
| **Workflow / approvals** (`workflow_*`, `approval_*`, `approvers`, `action_executions`, `events`) | Wired, unused | Keep or retire depending on roadmap |
| **SLA monitoring** (`sla_*`) | Real; needs a live performance feed to populate | Keep — activates on integration |
| **Doc/exhibit extraction** (`contract_documents`, `document_*`, `contract_exhibits`, `exhibit_fee_items`, `contract_definitions`, `contract_process_steps`) | Wired; populate on deep extraction | Keep |
| **`clients`** | Legacy; superseded by `organizations` but still wired in `upload.py` | Keep until a deliberate refactor removes the client path |
| **`dashboard_cache`** | Live cache; empty because entries expire | Keep |
