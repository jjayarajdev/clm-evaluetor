# Compliance & Performance Page — CTA-to-API Mapping

**Page:** `frontend/src/pages/PostSigningPage.tsx` (1,168 lines)
**Route:** `/compliance`
**Date:** 2026-05-04

---

## Data Loading (Queries)

| # | Query | API Function | Backend Endpoint | Trigger | Status |
|---|-------|-------------|-----------------|---------|--------|
| Q1 | Dashboard | `getPostSigningDashboard()` | `GET /api/dashboard/postsigning` | Page load (always) | OK — returns all widget data |
| Q2 | Compliance Trend | `getComplianceTrend('weekly', 8)` | `GET /api/reports/compliance/trend?period=weekly&lookback=8` | Page load (always) | OK — feeds sparkline charts |
| Q3 | Obligations List | `getPostSigningObligations({status, rag})` | `GET /api/dashboard/postsigning/obligations?status=X&rag=Y` | When `activeTab === 'obligations'` | OK — full filterable list |
| Q4 | SLAs List | `getPostSigningSLAs()` | `GET /api/dashboard/postsigning/slas` | When `activeTab === 'slas'` | OK — returns all 8 active SLAs |
| Q5 | Milestones List | `getPostSigningMilestones()` | `GET /api/dashboard/postsigning/milestones` | When `activeTab === 'milestones'` | OK — returns all obligations with deadlines |

**No mutations (useMutation) exist on this page.** All writes happen on downstream pages (obligation detail, contract view, etc.).

---

## URL Deep-Linking

| Parameter | Effect | Example |
|-----------|--------|---------|
| `?tab=obligations` | Sets `activeTab` on mount | `/compliance?tab=slas` |
| `?status=overdue` | Pre-fills obligation status filter | `/compliance?tab=obligations&status=overdue` |
| `?rag=red` | Pre-fills obligation RAG filter | `/compliance?tab=obligations&rag=red` |

Params are cleared after applying (`setSearchParams({}, { replace: true })`). Used by Overview's priority actions and other cross-page links.

---

## CTA Inventory by Tab

### Global — Page Header

| # | CTA | Type | Line | Target | Backend Endpoint | Correct? |
|---|-----|------|------|--------|-----------------|----------|
| 1 | **"Generate Report"** button | Navigation | 390-396 | `/reports` | N/A (navigates to ReportsPage) | OK — Route exists at `App.tsx:97` |

### Global — Summary Stat Cards (lines 401-437)

| # | CTA | Type | Line | Target | Backend Endpoint | Correct? |
|---|-----|------|------|--------|-----------------|----------|
| 2 | Overall Compliance card | Display only | 402-410 | — | Data from Q1 `dashboard.compliance.overall_compliance_rate` + Q2 sparkline | OK |
| 3 | Contracts At Risk card | Display only | 412-419 | — | Data from Q1 `dashboard.contracts_needing_attention` + Q2 breach chart | OK |
| 4 | Active Contracts card | Display only | 421-428 | — | Data from Q1 `dashboard.total_contracts`, `dashboard.total_value` | OK |
| 5 | Renewals (90 days) card | Display only | 429-436 | — | Data from Q1 `dashboard.renewals.expiring_90_days` | OK |

**Issue:** None of the stat cards are clickable. They could link to their respective tabs (e.g., clicking "Contracts At Risk" could navigate to obligations filtered by red RAG).

### Global — Tab Bar (lines 440-457)

| # | CTA | Type | Line | Target | Backend Endpoint | Correct? |
|---|-----|------|------|--------|-----------------|----------|
| 6 | Overview tab | State change | 445 | `setActiveTab('overview')` | No new query | OK |
| 7 | Obligations tab | State change + query | 445 | `setActiveTab('obligations')` | Triggers Q3 | OK |
| 8 | SLAs tab | State change + query | 445 | `setActiveTab('slas')` | Triggers Q4 | OK |
| 9 | Milestones tab | State change + query | 445 | `setActiveTab('milestones')` | Triggers Q5 | OK |
| 10 | Renewals tab | State change | 445 | `setActiveTab('renewals')` | No separate query (uses Q1 dashboard data) | OK — but limited to top-5 upcoming |
| 11 | Vendors tab | State change | 445 | `setActiveTab('vendors')` | No separate query (uses Q1 dashboard data) | OK — but limited to top/bottom performers |

---

### Overview Tab (lines 461-608)

| # | CTA | Type | Line | Target | Backend Endpoint | Correct? |
|---|-----|------|------|--------|-----------------|----------|
| 12 | Priority Action items | Display only | 470-472 | — | Data from Q1 `dashboard.priority_actions[]` | ISSUE — Not clickable. Should link to the relevant obligation/SLA/contract. |
| 13 | Obligations summary card | Display only | 482-523 | — | Data from Q1 `dashboard.obligations.*` | ISSUE — No "View all" link to Obligations tab (unlike Milestones card). |
| 14 | SLA Performance summary card | Display only | 526-553 | — | Data from Q1 `dashboard.slas.*` | ISSUE — No "View all" link to SLAs tab (unlike Milestones card). |
| 15 | **Milestones "View all"** button | State change | 560-565 | `setActiveTab('milestones')` | No API call | OK — switches to Milestones tab |
| 16 | Milestones summary card | Display only | 557-605 | — | Data from Q1 `dashboard.milestones.*` | OK |

---

### Obligations Tab (lines 610-720)

| # | CTA | Type | Line | Target | Backend Endpoint | Correct? |
|---|-----|------|------|--------|-----------------|----------|
| 17 | **Status filter dropdown** | Query trigger | 618-629 | `setOblStatusFilter(value)` | Re-triggers Q3 with `?status=X` | OK — Options: pending, in_progress, completed, overdue, waived |
| 18 | **RAG filter dropdown** | Query trigger | 632-641 | `setOblRagFilter(value)` | Re-triggers Q3 with `?rag=X` | OK — Options: green, amber, red |
| 19 | **Obligation title link** (per row) | Navigation | 674-679 | `/obligations/{item.id}` | N/A (navigates to ObligationDetailPage) | OK — Route exists at `App.tsx:92` |
| 20 | **Contract filename link** (per row) | Navigation | 682-687 | `/contracts/{item.contract_id}` | N/A (navigates to ContractViewPage) | OK |

**Backend endpoint for Q3:** `GET /api/dashboard/postsigning/obligations`
- Service: `PostSigningService.get_obligation_details(status_filter, rag_filter)`
- Returns: `[{id, contract_id, contract_filename, counterparty, title, description, category, owner, due_date, status, rag_status}]`
- Status is dynamically computed: obligations past deadline show as "overdue" even if stored as "pending"
- The "overdue" filter uses: `deadline < today AND status NOT IN (completed, waived)`
- The "red" RAG filter also includes dynamically overdue obligations

---

### SLAs Tab (lines 723-900)

| # | CTA | Type | Line | Target | Backend Endpoint | Correct? |
|---|-----|------|------|--------|-----------------|----------|
| 21 | SLA stat cards (4) | Display only | 726-731 | — | Data from Q1 `dashboard.slas.*` | OK |
| 22 | **Contract filename link** in All SLAs table (per row) | Navigation | ~769 | `/contracts/{sla.contract_id}` | N/A | OK |
| 23 | **SLA Breach row click** (per row, only if breaches exist) | Modal open | ~841-860 | `setSelectedBreach({...})` | No API call | OK — opens SLABreachDetailModal |

**Backend endpoint for Q4:** `GET /api/dashboard/postsigning/slas`
- Service: `PostSigningService.get_sla_details(breached_only=False)`
- Returns: `[{id, contract_id, contract_filename, counterparty, sla_name, metric_type, target_value, compliance_rate, consecutive_breaches, severity, has_penalty}]`
- Ordered by `consecutive_breaches DESC`

**Issues:**
- No filters (no status/severity dropdown like Obligations tab has)
- No SLA row click — the All SLAs table rows don't do anything when clicked (unlike breach rows)
- `compliance_rate` is null for all 8 SLAs (no performance data logged yet) — shows "N/A"

---

### SLA Breach Detail Modal (lines 97-242)

| # | CTA | Type | Line | Target | Backend Endpoint | Correct? |
|---|-----|------|------|--------|-----------------|----------|
| 24 | **Close (X) button** | Modal close | 129 | `onClose()` → `setSelectedBreach(null)` | No API call | OK |
| 25 | **Backdrop click** | Modal close | 116 | `onClick={onClose}` | No API call | OK |
| 26 | **Contract link in header** | Navigation | 122-127 | `/contracts/{breach.contract_id}` | N/A | OK |
| 27 | **"View Contract" button** | Navigation | 229-234 | `/contracts/{breach.contract_id}` | N/A | OK — duplicate of #26 but in footer |
| 28 | **"Close" button** | Modal close | 235 | `onClose()` | No API call | OK |

---

### Milestones Tab (lines 903-1032)

| # | CTA | Type | Line | Target | Backend Endpoint | Correct? |
|---|-----|------|------|--------|-----------------|----------|
| 29 | Milestone stat cards (4) | Display only | 906-918 | — | Data from Q1 `dashboard.milestones.*` | OK |
| 30 | Progress bar (stacked) | Display only | 921-967 | — | Data from Q1 | OK |
| 31 | **Contract filename link** in All Milestones table (per row) | Navigation | 1004 | `/contracts/{ms.contract_id}` | N/A | OK |

**Backend endpoint for Q5:** `GET /api/dashboard/postsigning/milestones`
- Service: `PostSigningService.get_milestone_details()`
- Returns: `[{id, contract_id, contract_filename, counterparty, title, due_date, status, category, owner}]`
- Status dynamically computed: overdue if `deadline < today AND status NOT IN (completed, waived)`

**Issues:**
- No filters (no status dropdown)
- Milestone rows are not clickable (no link to obligation detail page) — the milestone IS an obligation, so it could link to `/obligations/{ms.id}`
- No owner assignment CTA (backend supports `PUT /api/milestones/{id}/owner`)

---

### Renewals Tab (lines 1034-1101)

| # | CTA | Type | Line | Target | Backend Endpoint | Correct? |
|---|-----|------|------|--------|-----------------|----------|
| 32 | Renewal stat cards (4) | Display only | 1036-1046 | — | Data from Q1 `dashboard.renewals.*` | OK |
| 33 | **Contract filename link** in Upcoming Renewals table (per row) | Navigation | 1075 | `/contracts/{renewal.contract_id}` | N/A | OK |

**Data source:** `dashboard.renewals.upcoming_renewals` from Q1 (embedded in dashboard, no separate query)

**Issues:**
- Limited to dashboard's embedded `upcoming_renewals` list (top N from dashboard widget)
- No separate detail query (unlike Obligations/SLAs/Milestones) — `getPostSigningRenewals()` does not exist
- No filters (urgency window, auto-renew, etc.)
- Backend has rich renewal endpoints (`GET /api/renewals/calendar`, `GET /api/renewals/at-risk`, `PUT /api/renewals/{id}/status`) that are completely unused
- No "View renewal recommendation" CTA (`GET /api/renewals/{id}/recommendation` exists but unused)
- No renewal status update CTA (`PUT /api/renewals/{id}/status` exists but unused)
- No calendar export CTA (`GET /api/renewals/export/calendar.ics` exists but unused)

---

### Vendors Tab (lines 1103-1165)

| # | CTA | Type | Line | Target | Backend Endpoint | Correct? |
|---|-----|------|------|--------|-----------------|----------|
| 34 | Vendor stat cards (3) | Display only | 1105-1114 | — | Data from Q1 `dashboard.vendors.*` | OK |
| 35 | Top Performers list | Display only | 1119-1139 | — | Data from Q1 `dashboard.vendors.top_performers` | ISSUE — Vendor names not clickable |
| 36 | Needs Attention list | Display only | 1142-1162 | — | Data from Q1 `dashboard.vendors.bottom_performers` | ISSUE — Vendor names not clickable |

**Data source:** `dashboard.vendors.*` from Q1 (embedded in dashboard, no separate query)

**Issues:**
- No separate detail query — `getVendors()` exists but unused on this page
- Vendor names are not clickable (no vendor detail page link)
- No vendor comparison CTA (`GET /api/vendors/compare` exists but unused)
- No vendor scorecard CTA (`GET /api/vendors/scorecard` exists but unused)
- No vendor performance drill-down (`GET /api/vendors/{name}/performance` exists but unused)
- Backend has rich vendor endpoints (5 endpoints) that are completely unused from this page

---

## Summary

### Total Interactive Elements: 36

| Category | Count |
|----------|-------|
| Navigation links (to contract/obligation pages) | 8 types (repeated per row) |
| Tab switches | 6 |
| Filter dropdowns | 2 |
| Modal open (breach row click) | 1 |
| Modal close (X, backdrop, button) | 3 |
| "View all" internal tab links | 1 |
| "Generate Report" header button | 1 |
| Display-only stat cards | 14 |

### Mutations: 0

This page is **read-only**. No data is written from this page. All writes happen on destination pages (ObligationDetailPage, ContractViewPage, ReportsPage).

---

## Issues Found

### P1 — Missing Functionality (backend exists, frontend doesn't use it)

| # | Issue | Tab | Unused Backend Endpoint | Recommendation |
|---|-------|-----|------------------------|----------------|
| I1 | Renewals tab shows only dashboard widget data (top N) | Renewals | `GET /api/renewals/calendar` | Add separate query like Obligations tab has. Show ALL upcoming renewals. |
| I2 | No renewal status update | Renewals | `PUT /api/renewals/{contract_id}/status` | Add "Renew / Terminate / Negotiate" action buttons per row |
| I3 | No renewal recommendation | Renewals | `GET /api/renewals/{contract_id}/recommendation` | Add "Get AI Recommendation" button per row |
| I4 | No calendar export | Renewals | `GET /api/renewals/export/calendar.ics` | Add "Export to Calendar" button in tab header |
| I5 | Vendors tab shows only dashboard widget data | Vendors | `GET /api/vendors` | Add separate query for full vendor list with sorting/filtering |
| I6 | Vendor names not clickable | Vendors | `GET /api/vendors/{name}/performance` | Make vendor names link to a vendor detail view |
| I7 | No vendor comparison | Vendors | `GET /api/vendors/compare` | Add multi-select + "Compare" button |
| I8 | No SLA filters | SLAs | `GET /api/dashboard/postsigning/slas?breached_only=true` | Add severity/breach filter dropdowns like Obligations tab |
| I9 | No milestone filters | Milestones | — (backend would need filter params) | Add status filter dropdown |
| I10 | No milestone owner assignment | Milestones | `PUT /api/milestones/{id}/owner` | Add owner column with edit-in-place or modal |

### P2 — Missing Navigation (page exists, link doesn't)

| # | Issue | Tab | Where It Should Link | Recommendation |
|---|-------|-----|---------------------|----------------|
| I11 | Priority actions not clickable | Overview | Should link to the relevant obligation or SLA | Add `contract_id` / `obligation_id` to action data, make items clickable |
| I12 | Obligations summary card has no "View all" | Overview | `setActiveTab('obligations')` | Add "View all" link like Milestones card has |
| I13 | SLA Performance card has no "View all" | Overview | `setActiveTab('slas')` | Add "View all" link like Milestones card has |
| I14 | Milestone rows don't link to obligation detail | Milestones | `/obligations/{ms.id}` | Add title as link (like Obligations tab does) |
| I15 | SLA rows (in All SLAs table) not clickable | SLAs | Could open SLA detail or navigate to contract SLA section | Add row click or title link |
| I16 | Stat cards not clickable | Global | Could navigate to relevant tab | Add onClick to navigate |

### P3 — Data Gaps

| # | Issue | Tab | Details |
|---|-------|-----|---------|
| I17 | All 8 SLAs show `compliance_rate: null` | SLAs | No SLA performance data has been logged. `POST /api/sla/{contract_id}/performance/{sla_id}` has never been called. Frontend shows "N/A". |
| I18 | Priority actions list may be empty | Overview | Depends on having overdue/breached items. Currently works correctly. |

---

## Backend Endpoints Available but Unused by This Page

| Endpoint | What It Does | Could Be Used For |
|----------|-------------|-------------------|
| `GET /api/renewals/calendar` | Full renewal calendar by time window | Replace limited dashboard widget data |
| `GET /api/renewals/at-risk` | At-risk contracts (past notice, poor SLA) | "At Risk" section in Renewals tab |
| `GET /api/renewals/summary` | Renewal dashboard summary stats | Could replace dashboard widget stats |
| `PUT /api/renewals/{id}/status` | Update renewal decision | Action buttons on renewal rows |
| `GET /api/renewals/{id}/recommendation` | AI renewal recommendation | Per-contract recommendation CTA |
| `GET /api/renewals/export/calendar.ics` | Export ICS calendar file | Export button in Renewals tab |
| `GET /api/vendors` | Full vendor list with sorting | Replace limited dashboard widget data |
| `GET /api/vendors/{name}/performance` | Detailed vendor performance | Vendor detail drill-down |
| `GET /api/vendors/compare` | Side-by-side vendor comparison | Multi-select compare feature |
| `GET /api/vendors/scorecard` | Vendor scorecards for procurement | Scorecard view option |
| `GET /api/vendors/at-risk` | At-risk vendors with reasons | "Needs Attention" details |
| `PUT /api/milestones/{id}/owner` | Assign milestone owner | Inline owner assignment |
| `GET /api/milestones/health` | Full milestone health dashboard | Replace limited dashboard widget |
| `GET /api/milestones/at-risk-contracts` | At-risk contracts by milestones | Risk drill-down |
| `GET /api/milestones/portfolio-compliance` | Portfolio compliance metrics | Additional compliance view |
| `GET /api/sla/compliance/summary` | SLA compliance summary | Additional SLA analytics |
| `GET /api/sla/breaches/active` | Active SLA breaches grouped by severity | Breach drill-down |
| `GET /api/obligations/compliance/rates` | Compliance rates by status/RAG/category | Analytics view |
| `PUT /api/obligations/{id}/status` | Update obligation status | Inline status update |
| `PUT /api/obligations/{id}/rag` | Update obligation RAG | Inline RAG update |
| `PUT /api/obligations/{id}/owner` | Assign obligation owner | Inline owner assignment |
| `POST /api/obligations/{id}/evidence` | Upload compliance evidence | Evidence attachment CTA |

---

## Architecture Notes

- **Dashboard widget pattern:** Q1 returns summary data for all tabs. Tabs that need full lists (Obligations, SLAs, Milestones) make separate detail queries. Renewals and Vendors still rely on dashboard widget data only.
- **Lazy loading:** Detail queries use `enabled: activeTab === 'xxx'` to only fire when the tab is visible.
- **Dynamic status computation:** Overdue status is computed on the backend at query time (`deadline < today AND status NOT IN (completed, waived)`), not stored as a database enum.
- **No write operations:** This page is purely a read dashboard. All mutations happen on ObligationDetailPage, ContractViewPage, or other downstream pages.
