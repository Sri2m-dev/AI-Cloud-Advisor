# Nexora Design System & UX Specification v1.0

Status: **FROZEN DESIGN STANDARD v2.0 — IMPLEMENTATION NOT AUTHORIZED**

Program: P5 Executive Experience Platform / WP-001 Executive Design System

Foundation: Nexora Design System Z1.1.1, Product Specification v1.0, Enterprise
Vision v2.0, and Decision Framework Specification

## 1. Purpose

This specification is the single UX standard for P5. It defines how executive
intelligence looks, reads, behaves, discloses evidence, and moves into governed
workflows. Future pages must compose shared patterns rather than invent local CSS,
cards, terminology, colors, or interaction models.

This document specifies presentation semantics. It does not approve health,
materiality, confidence, risk, ranking, or governance formulas.

## 2. Experience principles

1. **Calm authority:** high information value without visual alarm fatigue.
2. **Consequence first:** lead with change, business meaning, and required attention.
3. **Evidence at hand:** proof is one action away, never buried in a separate product.
4. **Truthful uncertainty:** partial, stale, conflicted, unknown, and unsupported are
   designed states.
5. **One product:** persona lenses share primitives, language, and interaction.
6. **Progressive disclosure:** executive meaning first; technical detail on demand.
7. **Authority clarity:** review, recommend, simulate, decide, authorize, and execute
   are visually and verbally distinct.
8. **Accessible by default:** color, motion, charts, focus, and exports work for all
   authorized users.

## 3. Design token architecture

The existing `components/design_system` tokens remain the implementation baseline.
WP-001 may extend them only through reviewed semantic tokens.

### 3.1 Token layers

```text
Primitive tokens
  color / type / space / radius / shadow / motion
        ↓
Semantic tokens
  surface / text / border / status / materiality / evidence / authority
        ↓
Component tokens
  card / drawer / timeline / narrative / chart / report
```

Pages may consume semantic or component tokens, never raw page-specific colors.

## 4. Typography

Primary stack remains Inter, Segoe UI, Arial, sans-serif. Numeric and evidence IDs
may use the approved monospaced stack.

| Role | Size/weight intent | Usage |
|---|---|---|
| Display | 36 px / 700 | Rare command-center posture value |
| Page title | 30 px / 700 | One per page |
| Section title | 24 px / 650 | Major story section |
| Card title | 16–18 px / 600 | Business-readable label |
| KPI value | 28–36 px / 700 | One primary value per card |
| Body | 15 px / 400 | Narrative and explanation |
| Strong body | 15 px / 600 | Consequence or required action |
| Label | 13 px / 600 | Controls, metadata, badges |
| Caption | 13 px / 400 | Source, period, freshness, help |
| Evidence/code | 13 px / 500 mono | IDs, hashes, versions only |

Rules:

- use sentence case for page, section, card, button, and table labels;
- never use all caps for paragraphs or warning messages;
- tabular numerals are required for financial/time-series comparisons;
- line length for narrative prose is 60–85 characters where layout permits;
- status is expressed as text, not typographic emphasis alone.

## 5. Spacing, layout, and density

The base spacing unit is 4 px. Existing 4/8/12/16/20/24/32/40/48/64/80 px tokens
remain valid.

### 5.1 Executive page grid

- content uses the shared wide shell;
- desktop grid: 12 columns, 24 px gutters;
- maximum readable narrative width: 840 px;
- page-to-first-section: 32 px;
- major section gap: 32 px;
- card gap: 16–20 px;
- card internal padding: 20–24 px;
- no nested bordered cards;
- tables/charts use full available section width.

### 5.2 First viewport

At 1440 × 900 CSS pixels, the command center must show:

- page/scope/trust header;
- posture and material-change narrative;
- five dimension cards or approved equivalent;
- the beginning of Attention Required and Decisions Waiting.

No horizontal scrolling or more than two stacked navigation bars is allowed.

### 5.3 Responsive behavior

| Width | Behavior |
|---|---|
| ≥1280 px | 12-column executive layout; side-by-side attention/decision panels |
| 1024–1279 px | 8 columns; cards may wrap 3+2; drawers retain side placement |
| 768–1023 px | 4 columns; two-card rows; evidence becomes full-width overlay |
| <768 px | Single column; summary first; tables become cards or horizontal regions |

Priority order is preserved when wrapping. Responsive layout may not hide trust,
unknown, or authority indicators.

## 6. Color language

Existing light/dark surface, text, border, primary, success, warning, error, info,
and neutral tokens remain canonical. Semantic families must not be conflated.

### 6.1 Status

| Status | Meaning | Visual family |
|---|---|---|
| Healthy | No material action required | Green + check/text |
| Informational | Neutral context | Blue + info/text |
| Watch | Monitor or investigate | Amber + eye/clock/text |
| Warning | Review required | Amber/orange + alert/text |
| Critical | Material action required | Red + alert/text |
| Blocked | Cannot proceed safely | Dark red + stop/text |
| Unknown | Evidence cannot support conclusion | Slate + question/text |
| Partial | Supported with missing dimensions | Slate/amber + split/text |
| Stale | Outside approved freshness | Slate + clock/text |
| Conflicted | Governed sources disagree | Purple + conflict/text |
| Unsupported | No approved model | Neutral outline + text |

### 6.2 Materiality

Materiality is not status or risk. It describes business significance and uses an
approved label/icon pattern—such as `Material`, `Not material`, or `Not assessed`—
only after the materiality model is approved. Pages must not encode materiality by
inventing shades or thresholds.

### 6.3 Confidence and coverage

Confidence and coverage are separate:

- confidence: strength/applicability of the conclusion;
- coverage: proportion of required governed inputs available.

Both display a label, value/state, and definition tooltip. Neither uses red/green
alone. Bands and thresholds remain Decision Framework policy.

### 6.4 Authority

Authority uses state labels and icons, not risk colors:

`Insight`, `Finding`, `Recommendation proposal`, `Simulation`, `Decision`,
`Policy preview`, `Authorized`, `Executing`, `Verified outcome`.

Simulation always displays `SIMULATION — NOT AUTHORIZATION`.

## 7. Shape, borders, shadows, and motion

- standard card radius: 12 px;
- compact control/badge radius: 6–8 px;
- pill radius only for short filters/statuses;
- one-pixel semantic border is preferred over heavy shadow;
- shadow is subtle and indicates elevation, not importance;
- criticality is never communicated by increasing shadow or animation.

Motion duration is 120–240 ms for state transitions. Respect `prefers-reduced-motion`.
No pulsing risk cards, decorative parallax, autoplay charts, or animation that delays
access to evidence.

## 8. Iconography

Use existing domain concepts consistently: enterprise, capability, service,
workflow, application, technology, cloud, cost, savings, risk, AI, evidence,
timeline, decision, governance, and reports.

- icons supplement text and never replace status labels;
- the same icon cannot mean both Recommendation and Decision;
- decorative icons are hidden from assistive technology;
- interactive icons have accessible names and 44 × 44 px target areas.

## 9. Executive component library

### 9.1 Page header

Contains title, one-sentence purpose, authorized persona lens, enterprise scope,
time comparison, and compact Data Trust control. Optional actions are limited to
Search, Ask AI, Share, and Export when authorized.

### 9.2 Executive summary / narrative card

Anatomy:

1. narrative type and timeframe;
2. 3–5 sentence structured brief;
3. material change and consequence;
4. confidence/coverage/freshness row;
5. unknowns indicator;
6. `Why?`, `Drivers`, `Evidence`, and contextual next actions;
7. `AI-assisted` label when model prose is present.

It never presents AI prose without its deterministic claim set.

### 9.3 KPI card

Required anatomy:

- icon and business label;
- single primary value/status;
- delta with period/baseline;
- one-line meaning;
- source/period/freshness;
- status and partial/unknown state;
- evidence action;
- drill-down affordance.

Cards have fixed row heights within a group. Bare metrics are prohibited on P5
production surfaces.

### 9.4 Health card

Displays approved score or categorical state, direction, primary factor, coverage,
model version, and evidence. If no composite policy exists, use dimension state;
never calculate a page-local score.

### 9.5 Risk card

Displays consequence, affected business scope, trend, owner, mitigation/decision
state, evidence quality, and unknowns. Severity is not interchangeable with
materiality or likelihood.

### 9.6 Material change card

Displays observation, magnitude/timeframe, ranked drivers, consequence, comparison
checkpoint, and why it crossed the approved materiality rule.

### 9.7 Attention item

Compact row/card containing priority, consequence, subject, owner, due state,
evidence state, and one primary action. Maximum five in the executive first view.

### 9.8 Decision card

Only for actual governed Decisions. Shows decision state, authority scope, owner,
due date, recommendation/evidence package, policy status, and allowed next step.
Findings and proposals use different components.

### 9.9 Recommendation panel

Shows finding, proposed action, expected effect, alternatives, potential value,
risk, confidence, assumptions, evidence, and lifecycle state. Actions are `Review`,
`Compare`, `Simulate`, or `Package evidence`—never `Execute` directly.

### 9.10 Evidence indicator and Drawer

The indicator combines state, coverage/freshness, and accessible label. The Drawer
uses tabs:

`Summary | Sources | Lineage | Assumptions | Unknowns | Raw evidence`

It preserves current subject and closes back to the invoking component. Restricted
raw evidence is omitted with an entitlement explanation, not an empty panel.

### 9.11 Timeline

Event anatomy: occurred/observed time, event type, subject, concise change,
authority state, source, evidence, and affected scope. Filters include time, domain,
subject, materiality, and authority. Narrative interpretation is visually separate
from the authoritative event.

### 9.12 Chart panel

Every chart begins with a question, for example `What drove spend growth?` It
contains title, short answer, plot, timeframe/unit, legend, evidence/source, data
table toggle, and empty/partial state. Decorative donut charts and unexplained
composites are prohibited.

### 9.13 Data table

Stable business labels, sortable columns, keyboard-accessible row actions, visible
filters, hidden meaningless index, pagination/virtualization, export controls as
authorized, and an explicit empty state. Currency/unit/period belong in headers or
cells, never only in surrounding prose.

### 9.14 Filter bar

Displays active scope, supports `Clear all`, distinguishes global from local
filters, announces result changes accessibly, and includes filters in shared URLs,
narratives, exports, and evidence checkpoints.

## 10. Dashboard composition standard

P5 dashboards use this story order:

1. Page header and Data Trust
2. Executive Summary
3. Primary posture/KPIs
4. Material changes
5. Risks and opportunities
6. Trends/forecast
7. Recommendations and scenarios
8. Decisions/actions
9. Timeline
10. Evidence and version metadata

Sections with no supported data show an informative state; they are not silently
removed in a way that suggests completeness.

## 11. Interaction standards

### 11.1 Drill-down

- clicking a value opens the most business-relevant detail;
- current persona, scope, period, filters, checkpoint, and evidence context persist;
- breadcrumbs describe the canonical chain;
- every relationship hop is governed and explainable;
- missing paths stop with `Incomplete topology`, not a guessed destination.

### 11.2 Progressive disclosure

Use three levels:

1. executive meaning;
2. factors, options, and affected scope;
3. technical/raw evidence where authorized.

Tooltips define terms only; they do not hide material caveats.

### 11.3 Actions

Each surface has one primary action at most. Destructive or authority-bearing actions
display scope, consequence, policy/approval state, and confirmation in their owned
workflow. P5 presentation components do not create execution shortcuts.

### 11.4 Feedback

Success messages state what changed and its authority state. Errors state what did
not change, whether retry is safe, and where evidence is available. Optimistic UI
must not imply a Decision, Authorization, or Execution succeeded before the domain
confirms it.

## 12. AI experience

### 12.1 Entry

`Ask AI` opens with visible context chips for persona, scope, subject, time, and
filters. Users can remove or change context before submission. No hidden context
expansion is allowed.

### 12.2 Response anatomy

1. direct answer or supported refusal;
2. material meaning;
3. structured facts and drivers;
4. unknowns/limitations;
5. inline citations;
6. confidence/coverage/freshness;
7. actions: Explain, Compare, Simulate, Open evidence, Draft brief.

### 12.3 Mode language

- Ask: `Answer using governed enterprise context`
- Explain: `Explain this result`
- Compare: `Compare selected evidence-backed options`
- Simulate: `Run analysis-only scenario`
- Brief: `Draft from selected evidence`

AI cannot display Approve, Authorize, or Execute controls.

## 13. Search experience

Search offers a single enterprise input with recent/saved queries as authorized.
Results lead with an Answer Card, followed by canonical matches grouped by business
meaning rather than source system. Each match shows why it matched, canonical type,
owner/business context, trust state, and a persona-safe next step.

No-result states distinguish no canonical match, insufficient entitlement, and
unsupported question. Search never suggests that absent results prove absence.

## 14. Narrative experience

Narratives follow:

```text
Observation → magnitude/timeframe → drivers → consequence
→ options/recommendation state → unknowns → evidence
```

UI distinguishes deterministic claims from AI phrasing. Editing a Board narrative
uses tracked changes and cannot edit underlying facts. A changed fact requires a
new source checkpoint/regeneration, not manual overwrite.

## 15. Scenario and comparison UX

Scenario setup displays type, canonical subject, proposed change, horizon, scope,
depth, financial inputs, assumptions, included dimensions, and policy-preview
context. Inputs remain visible with results.

Comparison uses common rows for baseline, cost, business impact, risk, governance,
confidence, unknowns, and policy preview. It does not highlight a winner unless an
approved deterministic ranking policy explicitly permits it.

Every result carries the simulation-only banner and no execution control.

## 16. Recommendations and decision UX

The UI uses a visible state progression:

```text
Finding → Recommendation proposal → Scenario evidence
→ Evidence package → Human Decision → Policy/Authorization
→ Execution → Verified outcome
```

State changes use the owning domain workflow. Components show exactly which state
exists and which does not. Potential savings never use the visual treatment for
verified realized value.

## 17. Empty, partial, and failure patterns

Every state contains:

- named missing/unavailable content;
- why it matters;
- supported content that remains valid;
- coverage/freshness;
- safe next step or owner;
- evidence or diagnostic reference.

Examples:

- `Dependency impact unknown — no governed downstream relationships are recorded.`
- `Forecast unsupported for 12 months — the approved model supports 90 days.`
- `Financial posture partial — two accounts remain quarantined.`

Avoid `No data`, blank charts, zero substitution, or generic `Something went wrong`.

## 18. Accessibility standard

P5 targets WCAG 2.2 AA:

- keyboard access and logical focus order;
- visible focus with no keyboard trap;
- headings and landmarks reflect visual hierarchy;
- 44 × 44 px interactive targets where practical;
- semantic labels, descriptions, validation, and live-region announcements;
- text/icon/pattern status in addition to color;
- contrast validated in light/dark and export modes;
- charts have accessible summaries and table equivalents;
- motion reduction and no flashing content;
- drawer/modal focus returns to its trigger;
- screen-reader testing is part of release certification.

## 19. Content and terminology

### Voice

Calm, precise, concise, evidence-aware, and action-oriented. Do not use hype,
anthropomorphism, blame, or unsupported certainty.

### Preferred pattern

`Spend increased 7.1% in July, driven primarily by Production Analytics. The change
is material under policy M-2. One evidence-backed optimization proposal is under
review. No governed operational impact is currently recorded.`

### Terms

- use `Executive Summary`, not interchangeable Overview/Insights/Analysis;
- use `Data Trust`, `Evidence`, `Unknown`, and `Incomplete topology` consistently;
- use `Recommendation proposal`, not decision;
- use `Potential savings` and `Verified realized savings` exactly;
- use `Simulation — not authorization` exactly;
- spell out acronyms on first use in executive surfaces.

## 20. Board Report style guide

### 20.1 Format

- 16:9 landscape for PowerPoint; accessible paginated layout for PDF;
- consistent cover, section divider, content, decision, and appendix templates;
- one primary message per slide/page;
- maximum three supporting visuals per slide, usually fewer;
- slide title states the conclusion, not merely the topic;
- footer includes period, confidentiality, checkpoint, version, and page number.

### 20.2 Visual hierarchy

```text
Conclusion title
One-sentence consequence
Primary metric or visual
Drivers / options / decision required
Confidence, coverage, unknowns
Evidence reference footer
```

### 20.3 Evidence

Material claims carry compact evidence markers resolving into the appendix. The
appendix includes sources, lineage, methodology, model/policy versions, assumptions,
unknowns, reconciliation, and integrity hash. Raw secrets or restricted data are
never embedded.

### 20.4 Confidence and authority

Confidence/coverage appear near claims when material. Recommendation, Decision,
Authorization, and Verified Outcome use distinct labels. Draft AI text is clearly
marked until reviewed.

### 20.5 Quality gate

PowerPoint and PDF facts match; native-size rendering is visually inspected;
content does not clip; tables remain legible; charts have meaningful labels; reading
order and contrast pass accessibility review; confidentiality and sign-off are
present.

## 21. Component governance

### Lifecycle

```text
Proposed → Design reviewed → Accessibility reviewed → Implemented
→ Documented → Tested → Certified → Stable → Deprecated → Removed
```

Every component requires:

- purpose and prohibited uses;
- anatomy and states;
- responsive/accessibility behavior;
- content guidance;
- token usage;
- examples for healthy, critical, partial, unknown, stale, and unauthorized;
- unit, visual-regression, interaction, and accessibility tests;
- owner, version, and migration guidance.

New page-local styles require design-system review. Duplicate components are not
accepted because their colors or spacing differ.

## 22. UX validation and certification

### Required review modes

- content review;
- product-policy/authority review;
- design critique;
- accessibility audit;
- responsive inspection at defined breakpoints;
- light/dark inspection where supported;
- representative-data and empty/partial-state review;
- tenant/persona entitlement testing;
- browser/AppTest and screenshot comparison;
- PDF/PPTX native render review.

### Five priority prototypes

Before WP-002 implementation, validate:

1. CEO Command Center
2. CIO Command Center
3. CFO Command Center
4. Board Pack
5. Executive AI

Each prototype must cover default, material change, incomplete topology, partial
financial trust, unknown model, unauthorized evidence, and workflow-state examples.

## 23. P5 work-package boundaries

### WP-001 — Executive Design System

Tokens, shell, layout, cards, evidence, narrative, timeline, filters, charts, tables,
states, accessibility, and documentation. No business model formulas.

### WP-002 — Executive Command Center

Shared first viewport, posture, material changes, attention, decisions, forecast,
and trust using approved WP-001 components and Decision Framework outputs.

### WP-003 — Role Workspaces

CEO, CIO, CFO, Enterprise Architect, Operations, and FinOps lenses over the same
facts and components.

### WP-004 — Board Intelligence

Checkpointed report composition, review, evidence, sign-off, PowerPoint/PDF, and
visual/accessibility certification.

### WP-005 — Executive Narrative Platform

Structured claims, deterministic selection, AI phrasing, review, citations, and
narrative lifecycle.

## 24. Entry gate for implementation

WP-001 engineering begins only when:

- this UX specification is approved;
- the Product Specification and Decision Framework are frozen or formally versioned;
- five priority wireframes are approved;
- semantic token additions are reviewed in light and dark modes;
- field-level entitlement and authority labels are approved;
- accessibility acceptance and test tooling are agreed;
- Board Report confidentiality/sign-off rules have owners;
- manual P4.3 release-gate disposition is recorded;
- a bounded WP-001 engineering package is issued.

Until then, no executive UI implementation is authorized.
