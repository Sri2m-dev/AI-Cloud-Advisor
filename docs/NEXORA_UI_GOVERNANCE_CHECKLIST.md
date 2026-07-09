# Nexora UI Governance Checklist

Version: Z1.1.1
Status: Draft baseline
Purpose: Acceptance criteria for every new or standardized Nexora page.

## Certification Status

Use certification status instead of informal completion labels.

| Status | Meaning |
| --- | --- |
| Certified | Meets architecture, UI, data, quality, documentation, and regression standards |
| Stable | Functional and usable, awaiting full standardization or certification |
| Development | Active implementation or active refinement |
| Prototype | Experimental, incomplete, or not production-ready |

## Page Identity

| Check | Status |
| --- | --- |
| Uses standard NEXORA shell | Not reviewed |
| Uses standard sidebar behavior | Not reviewed |
| Uses standard page title | Not reviewed |
| Uses standard page description | Not reviewed |
| Uses standard breadcrumbs where applicable | Not reviewed |
| Uses footer/version metadata | Not reviewed |

## Layout

| Check | Status |
| --- | --- |
| Uses standard wide dashboard content width | Not reviewed |
| Does not introduce custom max-width wrappers | Not reviewed |
| Uses shared layout helpers instead of page-specific layout code | Not reviewed |
| Does not use duplicate navigation | Not reviewed |
| KPI rows are balanced | Not reviewed |
| Text does not wrap awkwardly in cards/buttons | Not reviewed |
| Page is responsive at desktop and mobile widths | Not reviewed |

## Executive Experience

| Check | Status |
| --- | --- |
| Includes Executive Summary | Not reviewed |
| Explains what the user is viewing | Not reviewed |
| Shows good/warning/critical posture quickly | Not reviewed |
| Shows next action or recommendation | Not reviewed |
| Uses executive-friendly wording | Not reviewed |
| Avoids engineering-only labels in top-level cards | Not reviewed |

## KPI Cards

| Check | Status |
| --- | --- |
| Uses shared card components | Not reviewed |
| Does not implement custom page-level card HTML when shared cards exist | Not reviewed |
| Each KPI has icon, title, value, description, and status | Not reviewed |
| Status color matches semantic meaning | Not reviewed |
| No page-specific HTML KPI cards | Not reviewed |
| No bare title/value-only KPI cards | Not reviewed |

## Sections

| Check | Status |
| --- | --- |
| Uses standard section header pattern | Not reviewed |
| Every section has a concise description | Not reviewed |
| Section naming follows Nexora standards | Not reviewed |
| Spacing between sections is consistent | Not reviewed |

## Tables

| Check | Status |
| --- | --- |
| Uses standard table styling | Not reviewed |
| Uses business-facing column names | Not reviewed |
| Hides index unless meaningful | Not reviewed |
| Uses full available width | Not reviewed |
| Empty state is useful and specific | Not reviewed |
| Tables avoid unexplained zero values | Not reviewed |

## Charts

| Check | Status |
| --- | --- |
| Uses standard chart library/pattern | Not reviewed |
| Chart title is clear | Not reviewed |
| Legend and colors are consistent | Not reviewed |
| Chart answers a business question | Not reviewed |
| Chart uses full available width | Not reviewed |
| No cramped or unreadable chart labels | Not reviewed |

## Evidence

| Check | Status |
| --- | --- |
| Page ends with Evidence or Detailed Evidence | Not reviewed |
| Includes Source Data | Not reviewed |
| Includes Data Coverage | Not reviewed |
| Includes AI Interpretation | Not reviewed |
| Includes Raw Evidence | Not reviewed |
| Evidence supports KPIs and narratives | Not reviewed |

## Financial Model

| Check | Status |
| --- | --- |
| Uses Enterprise Financial Model when showing reconciled spend | Not reviewed |
| Shows Data Reconciliation Status when relevant | Not reviewed |
| Shows Allocation Coverage when relevant | Not reviewed |
| Shows Unallocated Spend when relevant | Not reviewed |
| Does not perform duplicate spend math on the page | Not reviewed |

## Platform Architecture

| Check | Status |
| --- | --- |
| Aligns with `docs/NEXORA_PLATFORM_ARCHITECTURE.md` | Not reviewed |
| Aligns with `docs/NEXORA_RELEASE_WORKFLOW.md` | Not reviewed |
| Aligns with `docs/NEXORA_SDLC.md` | Not reviewed |
| Aligns with `docs/NEXORA_PRODUCT_ROADMAP.md` | Not reviewed |
| Consumes services instead of duplicating business logic in the page | Not reviewed |
| Uses shared layout, cards, spacing, and evidence patterns | Not reviewed |
| Uses Enterprise Financial Model for financial allocation and reconciliation | Not reviewed |
| Documents any intentional exception to platform standards | Not reviewed |

## Empty and Loading States

| Check | Status |
| --- | --- |
| Empty states explain what is missing | Not reviewed |
| Empty states suggest a next action | Not reviewed |
| Loading states do not shift layout unexpectedly | Not reviewed |
| Missing data does not produce misleading success status | Not reviewed |

## Technical Validation

| Check | Status |
| --- | --- |
| Python compile passes | Not reviewed |
| Route returns 200 OK | Not reviewed |
| No new Streamlit traceback | Not reviewed |
| No unrelated files modified | Not reviewed |
| No untracked data files committed | Not reviewed |

## Certification Review

| Check | Status |
| --- | --- |
| Documentation updated | Not reviewed |
| Smoke test completed | Not reviewed |
| Regression impact reviewed | Not reviewed |
| UI review completed | Not reviewed |
| Certification status assigned | Not reviewed |

## Phase Review Template

Use this table when standardizing a page group.

| Page | Header | KPIs | Narrative | Tables | Charts | Evidence | Empty State | Width | Route | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Page Name | Not reviewed | Not reviewed | Not reviewed | Not reviewed | Not reviewed | Not reviewed | Not reviewed | Not reviewed | Not reviewed | Not reviewed |

## Completion Definition

A page is considered standardized only when:

- It passes every applicable checklist item.
- It compiles successfully.
- Its route returns 200 OK.
- It has no new tracebacks.
- It follows the design system without page-specific visual inventions.
- It follows the platform architecture standards without duplicating shared layout, card, evidence, or financial logic.
- It follows the release workflow and has an assigned certification status.
- Any exceptions are documented and intentionally approved.

No feature is complete until it is documented, standardized, regression-tested, and certified.
