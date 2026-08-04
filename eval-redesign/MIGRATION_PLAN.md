# Evaluetor UI Redesign — Migration Plan

**Source of truth:** `eval-redesign/Evaluetor Prototype (offline).html` — "Direction B: European-minimal"
(violet `#7c3aed`, Instrument Sans, Heroicons outline, full dark theme).
Readable sources unpacked at `eval-redesign/unpacked/` (template.html = tokens/stylesheet, assets/*.js = screens).

**Target:** `frontend/` (React 18 + TS + Vite + Tailwind 3, React Router 6, TanStack Query, ~50 pages / ~26.6k lines).

**Scope guard:** local only for now — no deploys, work on a feature branch (`feature/redesign-b`), no backend changes required (the prototype models the existing API surface: BU roles, RBAC perms, compliance/post-signing split, usage metering).

---

## 1. Strategy

**Incremental, in-place migration. Not a rewrite.**

- Port the prototype's **token sheet nearly verbatim** into the app as CSS variables (`:root` + `[data-theme="dark"]`). It is ~330 lines and already complete, including dark mode. This is the highest-fidelity, lowest-effort path.
- Rebuild the prototype's **primitives as typed React components** in `src/components/ui/` (the prototype's `Btn/Pill/Chip/Tabs/Drawer/…` are already clean React functions — they translate almost 1:1 to TSX).
- **Tailwind stays** for layout utilities (flex/grid/spacing) during and after migration; its color/font theme gets remapped to the new CSS variables so old pages don't look broken mid-migration, they just inherit the new palette.
- Migrate **page by page**, shell first. Every phase ends with a working app; old and new pages coexist because both read the same tokens.
- Real routing (React Router), real auth (AuthContext), real data (TanStack Query) are **kept as-is**. The prototype's role-switcher, localStorage routing, and `EV.*` fake dataset are demo scaffolding — only its markup, styles, and interaction patterns migrate.

## 2. Design deltas (current → target)

| Aspect | Current | Target (prototype) |
|---|---|---|
| Primary color | "Coast" slate `#6B7D91` | Violet `#7c3aed` (dark: `#a78bfa`) |
| Font | Inter | Instrument Sans (+ JetBrains Mono, kept) |
| Dark mode | None | Full, via `[data-theme="dark"]` tokens |
| Per-role theme gradients (`src/styles/theme.ts`) | Role-colored gradients | **Removed** — one neutral system, role shown via BU crumb/badge |
| Icons | Heroicons outline v2 | Same — no change |
| Sidebar | 220px/60px collapse, 4 groups | 248px, module-grouped nav, role-aware, mobile scrim drawer |
| Top bar | Header w/ notifications, lang, user menu | 56px bar: title + BU crumb, ⌘K, theme toggle, user — keep notifications & lang switcher (not in mock; restyle, don't drop) |
| Tables | `ModernTable` | `.tbl` pattern: sticky uppercase headers, sortable, row-click, selection |
| AI confidence | ad-hoc | `Confidence` primitive: bar + 2-decimal figure, ≥0.90 ok / 0.60–0.89 warn / <0.60 danger, `manual` fallback |
| Destructive confirms | window.confirm / ad-hoc modals | `Confirm` modal with explicit "This removes / This does not touch" lists |
| Empty states | ad-hoc | `Empty` primitive: why it's empty + next action |

## 3. Phases

### Phase 0 — Design foundation (no visible page changes yet)
1. `src/index.css`: replace the Coast `:root` variables with the prototype token sheet
   (colors, radii, shadows, type scale, `--ease`, `--nav-w`, `--top-h`) + the full `[data-theme="dark"]` block.
2. `tailwind.config.js`: remap `primary-*`, status colors, `fontFamily`, radii, shadows onto the new CSS variables so **existing Tailwind classes resolve to the new palette**.
3. Fonts: swap Inter → Instrument Sans in `index.html` (Google Fonts; the unpacked woff2 files are available if we want to self-host later).
4. Port the prototype's component stylesheet (`.card .btn .chip .pill .tag .ai-tag .inp .cbx .sw .tbl .tabs .scrim .modal .drawer .menu .tip .kbd .bar .empty .av .banner` + keyframes) into `index.css` under `@layer components`. Prefix nothing — names don't collide with current classes except `.btn`/`.card`/`.input`, which we replace deliberately.
5. Theme plumbing: `ThemeContext` (light/dark/system) persisting to localStorage + user preference; sets `data-theme` on `<html>`.
6. Delete-list marker (executed in Phase 7): `src/styles/theme.ts` role gradients, old `.btn-*`/`.card-*` Tailwind component classes.

**Verify:** app runs, all pages render with violet palette and Instrument Sans, nothing structurally moved.

### Phase 1 — UI primitives (`src/components/ui/`)
Port from `unpacked/assets/ac3cf787….js` (primitives) as typed TSX, one file each, with tests:

| Prototype | Target component | Notes |
|---|---|---|
| `Btn`, `IBtn` | `Button`, `IconButton` | kinds p/s/g/d/dg → variant prop |
| `Chip`, `Pill`, `Tag`, `AiTag` | `Chip`, `Pill`, `Tag`, `AiTag` | `STATUS_PILL` tone map ports as-is |
| `Cbx`, `Switch`, `Field`, `Select` | `Checkbox`, `Switch`, `Field`, `Select` | integrate with react-hook-form |
| `Bar`, `Confidence` | `Bar`, `Confidence` | core AI signal — reuse everywhere |
| `Avatar`, `Tabs`, `Tip`, `Menu` | `Avatar`, `Tabs`, `Tooltip`, `DropdownMenu` | Menu can wrap HeadlessUI `Menu` for a11y |
| `Confirm`, `Drawer` | `ConfirmDialog`, `Drawer` | Confirm's affected/safe lists become the standard for all deletes |
| `Empty`, `Stat`, `Toast` | `EmptyState`, `StatCard` (replace), `Toast` | Toast → small context/hook (`useToast`) |
| `Icon` | keep `@heroicons/react` direct imports | prototype's fetch-based loader is bundle scaffolding — not ported |

Existing `StatCard`, `ModernTable`, `LoadingSpinner`, `PageHeader` are superseded gradually; keep them working until Phase 7.
Add a `Table` component implementing the `.tbl` pattern (sortable headers, sticky, row states) to replace `ModernTable`.

**Verify:** Storybook-less check — a temporary `/design` dev route rendering all primitives light + dark (removed in Phase 7). Unit tests for Confidence banding, Pill tone mapping, Confirm rendering.

### Phase 2 — App shell
Source: `unpacked/assets/70409432….js` (Sidebar, TopBar, Palette, Wordmark).

- Rebuild `Sidebar.tsx` on the prototype design: module-grouped nav driven by one config (`NAV`) filtered by `can(user, perm)` — replacing the current role-conditional groups. Keep super-admin nav as its own group.
- Rebuild `Header.tsx` → `TopBar`: page title + breadcrumb (BU / contract id), ⌘K trigger, theme toggle; **retain** notifications bell and language switcher restyled to `.ib` icon buttons.
- `MainLayout.tsx`: prototype layout — fixed sidebar `--nav-w`, `--top-h` top bar, `compact` mode < 1024px with scrim drawer (matches current responsive behavior).
- Restyle `CommandPalette` to the prototype's palette look; keep existing behavior.
- Map prototype routes → existing router paths (no URL changes):
  dashboard, contracts, upload, groups, ask→`/query`, obligations/renewals/vendors→`/post-signing`+`/renewals`+`/vendors`, orgs→`/organizations`, relationships, kpis→`/kpi-approvals`, surveys, improvements, portal→`/admin/external-users`, usage, users, units→`/admin/business-units`, roles, settings.

**Verify:** all roles (admin/legal/procurement/bu_head/viewer/super-admin) see correct nav; mobile drawer; dark mode; e2e click-through of every route.

### Phase 3 — Contract intelligence pages
Sources: `f81a448a` (register + tree), `1539c25b` (detail), `ed761819` (upload/groups/ask/dashboard).

1. **Dashboard** (`ModernDashboardPage`) — stat cards, role-aware widgets on new primitives.
2. **Contracts register** (`ContractsPage`) — new `.tbl` table + hierarchy tree view (existing `ContractTreeView` restyled; prototype adds drag-to-reparent — adopt if the API supports re-parenting, else defer).
3. **Contract detail** (`ContractViewPage`, 1217 lines) — biggest win: per-field confidence + provenance rich-tooltip pattern, clauses/obligations/SLAs tabs. Split into subcomponents while migrating.
4. **Upload** (`UploadPage`) — live pipeline stage animation mapped to the real processing-status polling.
5. **Groups & families** (`GroupsPage`/`GroupDetailPage`), **Ask AI** (`QueryPage`).

### Phase 4 — Post-signing operations
Source: `9cbdc901`. `PostSigningPage` (1488 lines) restructured to prototype's tabbed layout (obligations / SLAs / milestones / renewals / vendors); `RenewalsPage` + `VendorsPage` either fold in as tabs (prototype structure, URLs preserved via tab deep-links) or stay as pages restyled — decide at phase start. Detail pages (Obligation/SLA/Clause) restyled with primitives.

### Phase 5 — Relationship governance
Source: `1ca87ee0`. Organizations, Relationships (+ details), KPIs & perception, Surveys, Improvements, external portal. `RelationshipDetailPage` (972 lines) gets the prototype's KPI/perception layout. `ExternalGovernancePage` restyled with tokens (keep token-gated flow untouched).

### Phase 6 — Usage & admin
Source: `f122da1f`. `UsagePage` gets the prototype's metering charts (BarChart on recharts). Users, Business Units, Roles & permissions, Settings restyled to prototype patterns; `SettingsPage` (1624 lines) split into tab components as it migrates.

### Phase 7 — Long tail + cleanup
- Pages with no prototype counterpart (Reports, Scheduler, ServiceNow/SharePoint integrations, SSO, Extraction Quality, Industry Profiles, super-admin suite, External contract portal, Login): **restyle with tokens/primitives only**, no structural redesign.
- Remove: `src/styles/theme.ts` gradients, `ModernTable`, `ModernSidebar`, legacy `DashboardPage`, old component classes, `/design` dev route, Inter font link.
- Sweep for hardcoded Coast hexes / `primary-500` misuse.

## 4. Working agreements

- **Fidelity:** the prototype is the spec for look & interaction; the live app is the spec for data, routes, auth, and i18n. Where they conflict (e.g. prototype drops notifications), the live app's functionality wins, restyled.
- **i18n:** all new components keep `react-i18next` usage; prototype strings pass through translation keys.
- **A11y:** preserve the prototype's roles/aria (it's decent: role=tab/menu/switch/checkbox, aria-modal) and keep focus-visible outlines.
- **Tests:** each primitive lands with a unit test; each phase ends with a route click-through (target: grow from the current 3 test files).
- **Commits:** one phase = one or more PRs to `feature/redesign-b`; `main` stays deployable throughout.

## 5. Open decisions (flag before the relevant phase)

1. **Fold Renewals/Vendors into Post-signing tabs** (prototype) vs keep separate pages — Phase 4.
2. **Drag-to-reparent contract tree** — needs `PATCH parent_id` API check — Phase 3.
3. **Self-host fonts** (woff2 already extracted) vs Google Fonts — Phase 0, trivial either way; self-hosting helps the EU/GDPR posture for Square One.
4. **Default theme**: light (prototype default) with system-preference detection — proposed yes.
