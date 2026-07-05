# Nexora Design System

Version: Z1.1.1
Status: Draft baseline
Scope: All Nexora pages, dashboards, workflows, and future product surfaces.

## Objective

Every page in Nexora should look, behave, and feel like one enterprise product. The design system exists to make page delivery consistent, executive-ready, and easier to validate before release.

## Design Principles

- Executive first: every page must answer what the user is looking at, whether the signal is good or bad, and what action should be considered next.
- Evidence-backed: every KPI, narrative, chart, and recommendation should have traceable source evidence.
- Consistent over clever: pages should use shared layout, cards, tables, chart patterns, and status language.
- Dense but readable: Nexora is an enterprise operating platform, not a marketing site. Prioritize scannable information and calm structure.
- No isolated page design: new pages must follow the shared shell, sidebar, header, section, card, table, chart, empty-state, and evidence patterns.

## Typography

| Element | Standard |
| --- | --- |
| Page Title | Clear product noun, title case, primary page intent |
| Page Description | One concise sentence describing business value |
| Section Title | Title case, 2-6 words when possible |
| Section Description | One sentence explaining what the section proves |
| KPI Title | Short, business-readable label |
| KPI Value | Numeric or status value, never buried in prose |
| KPI Description | Short explanation of why the metric matters |
| Narrative | Plain executive prose, complete sentences |
| Table Heading | Business-facing column names, title case |

Avoid mixed naming such as "Overview", "Insights", "Analysis", and "Summary" for the same concept. Use the standards in this document.

## Page Structure

Every major page should follow this order:

1. Page header
2. Executive Summary
3. Primary KPI cards
4. Reconciliation or governance status when relevant
5. Main explorer or portfolio table
6. Charts or relationship views
7. Recommendations or actions
8. Evidence
9. Footer/version metadata

## Spacing

Use consistent vertical rhythm:

| Area | Standard Spacing |
| --- | --- |
| Page header to first section | 32 px |
| Section to next section | 32 px |
| Section title to content | 24 px |
| KPI card row spacing | 20 px |
| Evidence section spacing | 24 px |
| Button group spacing | 12-16 px |

No page should introduce custom max-width containers, centered report wrappers, or page-specific spacing unless approved as a design-system change.

## Layout

- Pages should use the NEXORA shell and sidebar.
- Main content should use the standard wide dashboard width.
- Avoid nested cards.
- Avoid centered single-column report layouts for dashboards.
- Use balanced column groups for KPI cards.
- Charts and tables should stretch to available page width.
- No duplicate Streamlit default navigation.

## KPI Cards

Every KPI card should include:

1. Icon
2. Title
3. Value
4. Optional delta or status signal
5. Description
6. Status

Do not use bare `Title + Value` cards on production pages.

Standard statuses:

| Status | Meaning |
| --- | --- |
| healthy | Good posture, no material action required |
| info | Neutral or informational signal |
| warning | Review recommended |
| critical | Executive or operational action required |

## Section Headers

Every section should use:

```text
Section Title
Small description
```

Use the shared `render_section` pattern. Avoid ad hoc markdown headings as primary structure on production pages.

## Executive Summary

Every page should contain a section named:

```text
Executive Summary
```

The section should answer:

- What am I looking at?
- Is it good or bad?
- What should I do next?

Avoid alternate labels such as "Insights", "Overview", "Analysis", or "AI Summary" unless they describe a separate secondary section.

## Evidence Standard

Every page should end with:

```text
Evidence
Source Data
Data Coverage
AI Interpretation
Raw Evidence
```

Business Architecture pages already follow the expanded version:

```text
Detailed Evidence
Source Data
Data Coverage
Relationship Summary
AI Interpretation
Raw Evidence
```

Future standardization should converge all major pages on this evidence model.

## Empty States

Empty states should be explicit and useful.

Use:

```text
No Technology Health data available.
Connect a cloud account or upload inventory.
Current Coverage: 82%
```

Avoid:

```text
No data
```

## Tables

Every table should use:

- Business-facing column names
- Consistent row height
- Standard `use_container_width=True` or future `width="stretch"` when migrated
- Hidden index unless the index is meaningful
- Clear empty state
- Optional filters only when they are useful

Column names should be stable across pages. For example, use `Business Unit`, not `BU`, `Unit`, and `Department` interchangeably.

## Charts

Chart standards:

- Use Plotly for analytical charts.
- Use clear chart titles.
- Keep legend placement consistent.
- Use the same status colors as KPI cards where possible.
- Avoid decorative charts that do not answer a business question.
- Use full container width.
- Avoid small charts squeezed into narrow columns unless the chart is intentionally a sparkline.

## Colors

Semantic colors should map to status, not page preference.

| Token | Meaning |
| --- | --- |
| healthy | Good / reconciled / stable |
| info | Neutral / informational |
| warning | Review / partial / pending |
| critical | Action required / variance / unmapped |

Do not introduce page-specific color palettes.

## Icons

Use consistent icon meaning:

| Domain | Icon Concept |
| --- | --- |
| Business | Enterprise/building |
| Capability | Governance/map |
| Service | Service/network |
| Process | Workflow |
| Application | Application/window |
| Technology | Technology/chip |
| Cloud | Cloud |
| Cost | Currency |
| Savings | Optimization |
| Risk | Alert |
| AI | Brain/spark |
| Reports | Document |

Use the existing component icon vocabulary where possible.

## Naming Standard

Standard names:

| Concept | Use |
| --- | --- |
| Page top narrative | Executive Summary |
| Evidence section | Evidence or Detailed Evidence |
| Reconciliation | Data Reconciliation Status |
| Spend mapped to model | Allocated Spend |
| Spend not mapped | Unallocated Spend |
| Technology financial mismatch | Variance Detected |
| Business-to-tech model | Business Architecture |
| Canonical financial source | Enterprise Financial Model |

Avoid synonyms unless the business meaning is genuinely different.

## Executive Experience Rule

Within the first 10 seconds, an executive should understand:

1. What page they are viewing.
2. Whether the current posture is healthy, warning, or critical.
3. What action or review is implied.

If a page cannot answer those three questions quickly, it is not ready to be frozen.

## Standardization Phases

### Phase A: Executive Workspace

- Executive Dashboard
- Enterprise Spend
- Approval Center
- Reports

### Phase B: CIO Workspace

- CIO Dashboard
- Technology Health
- Technology Inventory
- Technology Digital Twin
- Knowledge Graph
- Applications
- SaaS Intelligence
- Risk & Governance

### Phase C: Business Architecture

- Business Architecture
- Business Units
- Business Capabilities
- Business Services
- Business Processes
- Enterprise Capability Map

### Phase D: Finance and Shared Pages

- Finance Dashboard
- Connector Studio
- Enterprise Data Fabric
- Entity Registry
- Twin Explorer
- Cost Upload / Enterprise Financial Hub

## Change Control

Any new component, status label, chart style, spacing rule, or evidence pattern should update this document before it becomes a page-level convention.
