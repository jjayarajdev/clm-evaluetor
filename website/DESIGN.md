# DESIGN.md

The implementation-level design system for Evaluetor's commercial pages.
Read this alongside [`PRODUCT.md`](./PRODUCT.md). When tokens or patterns
here conflict with that file, that file wins.

---

## Palette

### Paper & ink (the only "background and text" colors that should appear)

| Token       | Hex       | Use                                                                |
|-------------|-----------|--------------------------------------------------------------------|
| `--paper`   | `#F7F6F3` | Page background. Warm off-white.                                   |
| `--paper-2` | `#EFEDE8` | Section background (every other section).                          |
| `--paper-3` | `#E5E2D9` | Rarely used, deeper alternate.                                     |
| `--surface` | `#FFFFFF` | Cards, mock product UI, tables, anything elevated above paper.     |
| `--ink`     | `#0E0E10` | Primary text, baseline rule on tables.                             |
| `--ink-2`   | `#2D2F36` | Secondary text (lead paragraphs, secondary copy).                  |
| `--ink-3`   | `#5B5F66` | Tertiary text (labels, captions). **Passes WCAG AA on paper.**     |
| `--ink-4`   | `#A0A4AB` | Decorative only. Icons, separators, never readable copy.           |

### Accent (one — Dutch orange)

| Token        | Hex       | Use                                                              |
|--------------|-----------|------------------------------------------------------------------|
| `--orange`   | `#E94E1B` | Marks, dots, underlines, accent borders, marginal callouts.      |
| `--orange-2` | `#C73E0F` | **Filled button backgrounds.** Passes WCAG AA on white text.     |

### Rules (separator lines)

| Token       | Hex       | Use                                              |
|-------------|-----------|--------------------------------------------------|
| `--rule`    | `#1A1A1C` | Heavy section separator (top of a sectionhead). |
| `--rule-2`  | `#D8D5CD` | Soft hairline (within sections, row dividers).   |
| `--rule-3`  | `#BDBAB1` | Rarely used.                                     |

### State (semantic only — never decorative)

| Token      | Hex       | Use                                  |
|------------|-----------|--------------------------------------|
| `--red`    | `#B91C1C` | RAG red, critical breach, overdue.   |
| `--amber`  | `#D97706` | RAG amber, warning, approaching.     |
| `--green`  | `#15803D` | RAG green, on-track, recovered.      |

### Forbidden colors

- ❌ Purple in any form (`primary-500` `#8b5cf6` from the site's global
  Tailwind config). Footer is page-overridden on `/commercial` to swap it
  to orange.
- ❌ Coral red (#F25C49 and similar). Not Dutch.
- ❌ Pastels.
- ❌ Gradients other than the orange diagonal-hatch leakage pattern in the
  value-erosion SVG chart.

## Typography

### Font stack

| Family            | Weights used     | Where                                                    |
|-------------------|------------------|----------------------------------------------------------|
| **Geist**         | 300, 400, 500, 600, 700, 800 | All headlines, body, CTAs.                   |
| **Geist Mono**    | 400, 500, 600    | Labels, chapter numbers, data tables, technical content. |
| **Instrument Serif** | 400, italic   | **Emphasis spans only.** Never an h1.                    |

### Type scale (clamps)

| Class        | Size                              | Use                                |
|--------------|-----------------------------------|------------------------------------|
| `.display`   | (via display-xl/lg/md/sm)         | All headlines.                     |
| `.display-xl`| `clamp(48px, 6.8vw, 96px)`        | Hero h1.                           |
| `.display-lg`| `clamp(34px, 4.6vw, 64px)`        | Section h2.                        |
| `.display-md`| `clamp(26px, 3vw, 40px)`          | Discipline h3, CTA card headline.  |
| `.display-sm`| `clamp(18px, 1.8vw, 22px)`        | Card headlines, side-rail titles.  |
| `.lead`      | `clamp(16px, 1.2vw, 18px)`        | Lead paragraphs after a headline.  |
| Body         | `14px` / `15px`                   | All other copy.                    |
| `.label`     | `10.5px` Geist Mono, 0.14em track | Chapter labels, microsignals.      |

### Italic emphasis pattern

The signature move: one **Instrument Serif italic** phrase per major
headline, in the same color as the rest of the headline. Picks up the
punch-word. Used sparingly — at most one per h1/h2.

```html
<h2 class="display display-lg">
  What the legacy CLM tools <span class="emph">do not do</span>.
</h2>
```

### Forbidden type choices

- ❌ Inter (the AI-marketing-page default).
- ❌ Fraunces / Playfair / Recoleta / Cormorant as primary h1.
- ❌ Three or more font families on a page.
- ❌ Synthetic italic on Geist (we ship Instrument Serif for that).

## Spacing

### Section scale

| Token             | Padding                          | Use                                  |
|-------------------|----------------------------------|--------------------------------------|
| `.section`        | `clamp(48px, 4.8vw, 72px) 0`     | Standard section.                    |
| `.section-tight`  | `clamp(36px, 3.4vw, 56px) 0`     | Tighter section (e.g., Outcomes).    |

### Container

| Token   | Max-width | Side padding (responsive)              |
|---------|-----------|----------------------------------------|
| `.wrap` | `84rem`   | `20px / 32px ≥768 / 48px ≥1280`        |

### Grid

12-column grid via Tailwind / CSS Grid. The dominant sectionhead pattern:
3-col label rail + 9-col headline, baseline-aligned.

## Components

### Chapter / section header

```html
<header class="sechead">
  <div class="sechead-num label label-ink">02 / Where it leaks</div>
  <h2 class="sechead-h display display-lg">
    Ten places the money tends to <span class="emph">walk out the door</span>.
  </h2>
</header>
```

- Label lives **inside the grid**, not floating above the h1.
- Label is mono caps, 0.14em tracking, ~10.5px.
- Headline carries one Instrument Serif italic span.

### Filled primary CTA

```html
<a href="..." class="cta-btn">Schedule a 30-minute review <span class="arr">→</span></a>
```

- Background `--orange-2`. White text, weight 600 (passes WCAG AA).
- Hover: background and border swap to `--ink`, gap widens 10→16px.
- `:focus-visible`: 2px `--orange-2` outline, 3px offset.

### Outline secondary CTA

```html
<a href="..." class="cta-outline">See the platform</a>
```

- Transparent background, `--ink` border + text.
- Hover: fills to `--ink`, text becomes `--paper`.

### Card (when a card is unavoidable)

- Surface `--surface`. Single `1px solid --rule-2` border on all four sides.
- **No top accent stripe** (the side-stripe anti-pattern).
- No nested cards. Rows inside a card are fine if they're table-like data
  separated by hairlines, not card-in-card.

### Data table (e.g., comparison table)

- First-column header **named** (`Capability`, not empty).
- Header row: ink-3 mono caps, 1px solid `--rule` bottom-border.
- "Our" column header marked with a 6px square orange dot before the name.
- Zebra striping with `--paper-2` on alternating rows.
- Em-dashes ("Not standard") are softer than the bare `—` glyph for missing
  capabilities. Avoid the bare `—`.

### Mock product UI panels (the hero overview + four discipline mocks)

- Container border `--rule-2`, surface `--surface`.
- Header strip in `--paper-2` with: live-pulse dot, brand name, date stamp,
  small "illustrative" corner marker.
- Inside, sectional structure: label → stat row → divider → data rows.
- Mono numbers, tabular-nums.

### Forbidden component patterns

- ❌ Eyebrow chips (mono caps with letter-spacing) floating directly above h1.
- ❌ Side-stripe cards (`border-top: 3px solid var(--orange)` on a card).
- ❌ Nested cards (a card inside a card).
- ❌ Glassmorphism backgrounds.
- ❌ Drop shadows beyond the single subtle product-mock elevation shadow.
- ❌ Rounded corners larger than `4px`. We're flat.

## Motion

| Effect          | When                                        | Spec                                          |
|-----------------|---------------------------------------------|-----------------------------------------------|
| Scroll reveal   | First appearance of any `.sr` block         | `0.7s cubic-bezier(.2,.7,.2,1)`, 10px translate |
| Hero stagger    | Page load                                   | 5-child cascade, 50ms → 600ms delays          |
| CTA hover       | On `.cta-btn` and `.cta-outline`            | `0.2s ease` background, gap expands           |
| Pulse           | Live-status dot in product mock             | `1.8s ease-in-out infinite`                   |
| Audience rotator| Hero "Built for [X]"                        | 15s loop, 5 items × 3s each, `steps(1)`       |

Anything else: no.

## Dark mode

**Decision (2026-05-28): the commercial page ships light-only.**

Rationale:
- The audience reads this page on desktop, in daylight, evaluating an
  enterprise purchase. Light mode is the default they'll encounter.
- A toggleable dark theme adds maintenance surface (every component must
  honor it) for negligible audience value.
- If/when the Evaluetor product itself supports dark mode, this decision is
  revisited and we ship a matching commercial-page dark theme.

This is a deliberate departure from Taste Skill's "dual-mode by default"
default. Documented here so it survives future audits.

## Do's

- ✅ Lead with the headline. No eyebrow chip above it.
- ✅ Italic-serif on one punch-phrase per headline.
- ✅ Mono labels for chapter numbers and microsignals.
- ✅ Tabular numerals on every number that lives in a row with other numbers.
- ✅ Hairline rules between rows; thick rule (`--rule`) only as a section
  opener.
- ✅ Two CTAs at every commit moment: filled primary + outline secondary.
- ✅ Honest hedging on every external claim ("industry research has
  reported," "available on request," "targets, not promises").
- ✅ "Illustrative" corner marker on every product-mock that contains
  fabricated data.

## Don'ts

- ❌ Generic CTA copy ("Learn more →", "Click here", "Get started").
- ❌ Placeholder slots, Lorem ipsum, `[TBD]`, dashed-border logo cells.
- ❌ Claims of customer outcomes we cannot point to (90% / 3-5× / etc. are
  labeled "targets, not promises" specifically for this reason).
- ❌ More than three font families on a page.
- ❌ More than one accent color.
- ❌ Gradient text. Gradient backgrounds (other than the leakage diagonal
  hatch). Glassmorphism.

---

## Decision log (chronological)

| Date       | Decision                                                                    | Why                                                                |
|------------|-----------------------------------------------------------------------------|--------------------------------------------------------------------|
| 2026-05-17 | Editorial paper aesthetic (Fraunces, parchment cream)                       | Initial frontend-design skill output. Rejected as "whacky."        |
| 2026-05-19 | Dutch modernist aesthetic — Geist + Dutch orange `#E94E1B`                  | User-directed. Studio Dumbar / Adyen / contemporary EU B2B.        |
| 2026-05-20 | Section padding reduced ~40% (information density over museum spacing)      | User feedback: too much whitespace.                                |
| 2026-05-20 | Added value-erosion SVG chart, four product mock UIs                        | "Show, don't tell." Stronger than text descriptions.               |
| 2026-05-20 | Softened all overclaiming: connectors → "concept," EU residency → "available," removed verdict, etc. | User concern about unvalidated numbers.                            |
| 2026-05-20 | Numbers validated against codebase: 10 risks, 7 obligation types, composite formula `0.3/0.4/0.3` confirmed | Verified honesty.                                                  |
| 2026-05-24 | Italic emphasis (Instrument Serif) on punch words across all major headlines | Real Ironclad/Luminance pattern. Replaced ink-3 muted clauses.     |
| 2026-05-28 | Hero eyebrow chip removed; CTA orange darkened to `--orange-2` for WCAG AA  | Manual `/impeccable audit`.                                        |
| 2026-05-28 | "Learn more" CTAs removed; logo placeholders replaced with honest copy      | Manual `/impeccable audit`.                                        |
| 2026-05-28 | Footer accent overridden (purple → orange) on `/commercial` only           | Manual `/impeccable audit`.                                        |
| 2026-05-28 | `--ink-3` darkened `#6B6F78 → #5B5F66` for WCAG AA body labels             | Manual `/impeccable audit`.                                        |
| 2026-05-28 | Audience rotator trimmed 7 → 5 items at 3s each                            | Manual `/impeccable audit` P3.                                     |
| 2026-05-28 | Dark mode decision: light-only, documented                                  | Manual `/taste-skill audit`.                                       |
| 2026-05-28 | `PRODUCT.md` + `DESIGN.md` written                                          | Taste Skill §0 + §11 compliance.                                   |
| 2026-05-31 | "Rotterdam" → "the Netherlands" across branding copy; postal address keeps the city | Steven Visser review feedback. Broader geographic framing, less city-specific. |
| 2026-05-31 | "Senority B.V." → "Evaluetor B.V." in footer + colophon                     | Steven Visser review — legal entity name should match brand-facing name. |
| 2026-05-31 | Added "Both sides of every contract" section (buy-side / sell-side cards)  | Steven Visser review — current narrative is buy-side biased; sell side equally served (revenue protection, account health, deliver as promised). |
| 2026-05-31 | Added "What it returns" pricing/value section (~3% of contract value, 10× ROI rule, 3 portfolio examples) | Steven Visser review — page was missing commercial math. Numbers from `docs/mockup-review/evaluetor_pricing_value_model.xlsx`. |
| 2026-05-31 | Added 5th audience tab (Sales & AM) to mockup audience module; header updated to "Five points of view" | Steven Visser review slide 4 — literal ask: add sales/account-mgmt/Commercial view. |
| 2026-05-31 | Expanded "What it returns" with 3 packaging tiers (Monitoring €40-60k / Recovery €60-120k / Optimisation €120-250k+), connector pricing structure, floor pricing (€40k/€80k), and the one-line CFO summary | Steven Visser review slides 6+7 — pricing section was missing tiers, floors, connector lines, and the board-ready summary. |
| 2026-05-31 | Replaced 3 FAQ entries with Steven's sharper framings: "We already have a CLM" (repository vs execution visibility), "AI accuracy" (3 concrete safeguards), "Integration" (honest about complexity + time-to-value) | Steven Visser review slide 8 — my versions were generic; his are tighter and more defensible. |
| 2026-05-31 | Added FAQ entry "How is perception gap actually measured" (surveys, KPI inputs, communication signals) | Steven Visser review slide 5 critical observation — page was hand-waving around perception gap measurement. |
| 2026-05-31 | Added ICP statement to PRODUCT.md (first-wave customer profile: €20M-€500M ACV, procurement-led, EU mid-large, high SLA spend, structured contracts, pain signal). Sharpened trust strip from generic to ICP-aligned. | Steven Visser review slide 5/6 — target market was too wide; no clear ICP. |
| 2026-05-31 | Added "Cost of doing nothing" callout above the final CTA (€1.5M-€2M/year on €50M portfolio) | Steven Visser review slide 8 — CFO negotiation playbook framing; cost-of-inaction belongs near the CTA, not just in internal sales script. |

---

_Updated by whoever changes the system. New rows append at the bottom._
