# Evaluetor — Product Improvements Backlog

Companion to [`FEATURE_STATUS.md`](./FEATURE_STATUS.md). Where FEATURE_STATUS describes
what exists, this document lists what to build/fix/polish next.

Organized by area, roughly ordered by impact within each.

**Effort tags:**
- **S** — 1–2 days
- **M** — 3–7 days
- **L** — 1–3 weeks
- **XL** — > 3 weeks

---

## A. Integrations — replace the stubs

The single biggest "demo → production" gap.

| # | Item | Effort |
|---|------|--------|
| 1 | **Real ServiceNow connector** — replace `connectors/servicenow_stub.py`; fetch real SLA actuals, incidents, CMDB. | L |
| 2 | **Real SharePoint Graph SDK** — wire `routers/sharepoint_integration.py` browse + import; today config saves but no real API calls. | L |
| 3 | **Real Milestone / project tracker connector** — replace `milestone_stub.py` (Jira or Asana likely). | M |
| 4 | **Real FX rate API** — replace `fx_stub.py` with ECB / openexchangerates so FX threshold alerts run on real rates. | S |
| 5 | **Wire Slack delivery** — `notification_service.py:407` is a TODO; finish it. | S |
| 6 | **Wire webhook delivery** — `notification_service.py:412` TODO; finish it. | S |
| 7 | **Microsoft Teams notification channel** — alongside Slack. | S |
| 8 | **DocuSign / Adobe Sign integration** for signing workflows. | L |
| 9 | **Salesforce / HubSpot CRM** for counterparty enrichment. | L |
| 10 | **Two-way sync** — push contract changes back to ServiceNow / SharePoint, not just ingest. | L |

## B. Compliance page — finish what we started

Mutations + data already exist; this is mostly UI.

| # | Item | Effort |
|---|------|--------|
| 11 | **Inline acknowledge / resolve / approve** on Priority Actions (no navigation). | M |
| 12 | **Bulk RAG status change** on obligations table (multi-select). | S |
| 13 | **Bulk approve / decline** on renewals table. | S |
| 14 | **Bulk acknowledge** on SLA breaches. | S |
| 15 | **Saved filter views** ("My overdue obligations") per user. | M |
| 16 | **Stat card click-through** (we skipped I16 in the prior plan). | S |
| 17 | **Vendor comparison view** (we skipped I7 in the prior plan). | M |
| 18 | **Per-obligation calendar export** (currently aggregate-only). | S |

## C. Dashboard

| # | Item | Effort |
|---|------|--------|
| 19 | **Delete legacy `DashboardPage`** — `ModernDashboardPage` is canonical; remove drift risk. | S |
| 20 | **Realtime updates via SSE / WebSocket** for breach + alert events. | L |
| 21 | **Customizable widget order** per user (config exists at `config.ui.dashboard_widgets`). | M |
| 22 | **"What's new since last login"** panel. | S |

## D. AI / Extraction quality

| # | Item | Effort |
|---|------|--------|
| 23 | **DSPy compilation UI** — admin button + progress + last-compiled-at. Currently script-driven only. | M |
| 24 | **Auto-recompile DSPy** when golden set grows by N examples. | S |
| 25 | **Multilingual contract support** — currently English-assumed. | XL |
| 26 | **Better record-by-record review UX** in `ExtractionQualityPage`. | M |
| 27 | **Per-tenant prompt overrides** (admin UI on top of few-shot service). | M |
| 28 | **Per-field confidence thresholds** per tenant. | S |
| 29 | **Extraction provenance display** ("page 4, line 23") on contract metadata. | M |
| 30 | **Re-extract single field** without re-running full pipeline. | M |
| 31 | **Streaming extraction progress** on upload (replace polling). | M |
| 32 | **Excel SLA template download** so customers can fill in offline. | S |
| 33 | **Surface silent failures** — pipeline degrades silently today; tenant can't see "X failed during ingestion." | M |

## E. Knowledge graph

| # | Item | Effort |
|---|------|--------|
| 34 | **Visual graph viewer** for entity relationships per contract. | M |
| 35 | **"Related entities" panel** on contract page using KG. | S |
| 36 | **Cross-contract obligation conflict detection** (e.g., overlapping termination rights). | L |
| 37 | **Entity merging UI** for when the same party has slight name variations. | M |

## F. Q&A / Chat

| # | Item | Effort |
|---|------|--------|
| 38 | **Chat history sidebar with search**. | S |
| 39 | **Multi-document Q&A** ("compare these 3 contracts"). | M |
| 40 | **Citations clickable into PDF viewer** at exact location. | M |
| 41 | **Saved chat templates / playbooks** (e.g., "due-diligence questions"). | S |
| 42 | **Suggested follow-up questions in-flow** (we have the field; surface it better). | S |

## G. Renewals

| # | Item | Effort |
|---|------|--------|
| 43 | **Auto-generated renewal recommendation memo** (LLM over contract + performance). | M |
| 44 | **Renewal pipeline kanban** (pending → negotiating → approved). | M |
| 45 | **Side-by-side comparison** of expiring contract vs. proposed renewal terms. | M |
| 46 | **Counterparty notification** on auto-renewals approaching notice deadline. | S |

## H. Vendors

| # | Item | Effort |
|---|------|--------|
| 47 | **Vendor performance trend chart** over time. | S |
| 48 | **Vendor 360 page** consolidating contracts + obligations + SLAs + perception scores. | M |
| 49 | **Auto-flag** vendors trending toward "at risk". | S |
| 50 | **Vendor benchmarking** (your scores vs. peer industry baseline). | L |

## I. Governance

| # | Item | Effort |
|---|------|--------|
| 51 | **Auto-pull KPI actuals** from SLA performance (currently can be manual). | M |
| 52 | **Survey reminder emails** for non-responders. | S |
| 53 | **Survey partial-save / resume**. | S |
| 54 | **Anonymous mode** for perception scoring. | S |
| 55 | **Improvement point lifecycle** (open → in-progress → closed with evidence). | M |

## J. Multi-tenant admin

| # | Item | Effort |
|---|------|--------|
| 56 | **Tenant usage analytics** (storage, API calls, AI tokens consumed). | M |
| 57 | **Per-tenant feature flags**. | M |
| 58 | **Tenant impersonation** for support. | S |
| 59 | **Bulk user provisioning** via CSV / SCIM. | M |
| 60 | **SSO group → role mapping**. | M |
| 61 | **Role customization** (today roles are fixed). | L |

## K. External portal

| # | Item | Effort |
|---|------|--------|
| 62 | **Vendor self-service onboarding**. | M |
| 63 | **Document acknowledgment tracking**. | S |
| 64 | **Status indicator** on shared contracts so vendor sees what's expected. | S |

## L. Performance & scale

| # | Item | Effort |
|---|------|--------|
| 65 | **Dashboard query profiling** — likely N+1 in `dashboard_service.py`. | M |
| 66 | **Pagination on big tables** (obligations table can grow huge). | S |
| 67 | **Cache invalidation reliability** — currently best-effort. | M |
| 68 | **ChromaDB sharding strategy** for very large tenants. | L |
| 69 | **Background queue UI** to manage stuck / failed ingestion jobs. | M |

## M. Observability

| # | Item | Effort |
|---|------|--------|
| 70 | **Langfuse trace viewer** in admin UI for prompt debugging. | M |
| 71 | **Token cost dashboard** per tenant. | S |
| 72 | **Pipeline SLA tracking** (when does upload finish?). | S |
| 73 | **Test coverage audit** + fill gaps. | M |

## N. Security

| # | Item | Effort |
|---|------|--------|
| 74 | **MFA enforcement**. | M |
| 75 | **Session timeout config**. | S |
| 76 | **Password policy admin**. | S |
| 77 | **PII redaction** on extracted data. | M |

## O. Reports

| # | Item | Effort |
|---|------|--------|
| 78 | **Scheduled report email delivery**. | M |
| 79 | **PDF export** (currently CSV only). | S |
| 80 | **Custom report builder**. | L |
| 81 | **White-labeled exports** for external sharing. | M |

## P. Polish

| # | Item | Effort |
|---|------|--------|
| 82 | **SettingsPage tab persistence audit** — depth uneven across tabs. | S |
| 83 | **Mobile-responsive review** — likely uneven. | M |
| 84 | **Accessibility audit** (WCAG). | M |
| 85 | **Print-friendly contract view**. | S |

---

## Suggested starting batch

If you want a balanced first sprint that compounds the work already done, pick from:

- **#1** — one production-grade integration story (replace ServiceNow stub)
- **#5, #6** — Slack + webhook delivery (close the notification gap)
- **#11–14, #16** — inline + bulk workflow polish on the Compliance page (extends the recent rewire)
- **#19** — delete legacy dashboard (removes drift risk)
- **#23, #33** — DSPy admin UI + surface silent extraction failures (quality boost without new UI surface)
- **#51** — auto-pull KPI actuals from SLA performance (governance feels alive)
- **#65** — dashboard query profiling (perf pass before the codebase grows further)

That mix covers: one real integration, productivity polish, quality / observability, and a perf pass.

---

## How we'll work this list

- One branch (`feature/new-improvements`) for the active batch; spin off sub-branches per item if the batch is large.
- Re-evaluate priority after every 5–10 items shipped — feature use will reorder this list.
- When an item ships, move its line to a `## Shipped` section at the bottom (with commit hash + date) so the backlog stays a backlog.
