# Nexora Component Catalog v1.0

Status: **P5.1 IMPLEMENTATION CONTRACT — ENGINEERING NOT YET AUTHORIZED**

Applies to: Nexora v2.1 / P5.1 Executive Component Library

## 1. Purpose and authority

This catalog defines where every P5 component is used and the contract each
implementation must satisfy. It complements the Design System UX Specification,
which defines visual and interaction language. It introduces no business formula,
ranking, recommendation, policy, financial, or execution authority.

Authority order remains:

1. security, evidence, financial, and authority ADRs;
2. P4.3 RC1 public contracts;
3. Product Freeze v2.0 and approved PDRs;
4. Product and Decision Framework specifications;
5. Design System UX Specification;
6. P5.0.1 Executive UX Architecture;
7. this catalog.

Conflicts stop implementation and require an ADR/PDR disposition. This catalog
does not itself satisfy the P5 entry gate or authorize code.

## 2. Surface keys

| Key | Surface |
|---|---|
| ALL | All executive surfaces |
| SH | Executive Shell |
| CC | Executive Command Center |
| CEO | CEO Workspace |
| CIO | CIO Workspace |
| CFO | CFO Workspace |
| EA | Enterprise Architect Workspace |
| OPS | Operations Workspace |
| FO | FinOps Workspace |
| SD | Business Service Detail |
| XS | Executive Search |
| XAI | Executive AI |
| BI | Board Intelligence |

## 3. Common component contract

Every data-bearing component receives an immutable, typed presentation view. The
minimum envelope is:

```text
component_id, contract_version
tenant_id, persona, entitlement_context
subject_ref, scope_ref, checkpoint, observed_at, period
value_or_state, semantic_status, authority_state
evidence_summary, coverage, freshness
partial_reasons[], unknown_reasons[], allowed_actions[]
```

Components emit presentation intents, never domain commands:

```text
open_detail(subject_ref, preserved_context)
open_evidence(evidence_ref, preserved_context)
change_context(explicit_delta)
open_search(preserved_context)
open_ai(visible_context_chips)
compare(subject_refs, baseline_ref)
request_governed_workflow(workflow_ref)
```

The application layer authenticates tenant and persona, applies field-level
entitlement, and assembles the view before rendering. Components never receive a
repository, provider client, raw credential, unrestricted evidence object, or a
cross-tenant identifier.

## 4. State contract

All data-bearing components use `F06 Component State Frame` and implement these
states without changing layout meaning:

| State | Required presentation |
|---|---|
| Loading | Labelled skeleton preserving final geometry; no invented value |
| Empty | Valid zero-item result, scope and next permitted action |
| Partial | Available content plus missing scope/reason and coverage |
| Stale | Last observation, freshness threshold/source, refresh action if allowed |
| Conflicted | Competing governed values/sources; no silent precedence |
| Unknown | Explicit missing knowledge/evidence; never rendered as zero or healthy |
| Unsupported | Capability/model is not approved; no simulated placeholder |
| Unauthorized | Entitlement explanation without revealing restricted existence/data |
| Error | Safe correlation reference, retry if idempotent, no sensitive internals |

Individual rows below identify important state-specific behavior. All unmentioned
states inherit this contract. Restricted raw evidence is omitted with an entitlement
explanation rather than displayed as an empty result.

## 5. Permission profiles

| Profile | Rule |
|---|---|
| P0 Public chrome | Authenticated tenant user; contains no domain data |
| P1 Governed summary | Persona and scope entitlement required before assembly |
| P2 Evidence | Claim plus field-level source/lineage entitlement; raw evidence separately gated |
| P3 Financial | P1 plus financial scope, currency/period/source and reconciliation controls |
| P4 Decision | P1 plus governed workflow visibility; action is supplied only by WP-011 authority |
| P5 Board | Named report audience, confidentiality, checkpoint, export, and sign-off entitlement |
| P6 Administration | Explicit configuration/steward entitlement; never inferred from persona |

Persona affects vocabulary, priority, depth, and entitlement only. It cannot alter a
shared governed fact.

## 6. Accessibility profiles

All profiles require WCAG 2.2 AA, keyboard operation, visible focus, semantic HTML,
200% zoom/reflow, non-color status cues, light/dark contrast, reduced motion, and
screen-reader state announcements.

| Profile | Additional requirements |
|---|---|
| A0 Primitive | Stable accessible name/description, target size, disabled reason |
| A1 Card | Heading hierarchy, concise name/value/state, action order, no whole-card keyboard trap |
| A2 Overlay | Focus trap, Escape, labelled title, background inert, focus returned to invoker |
| A3 Data | Table alternative, units/period in headers, sortable state announced, chart description |
| A4 Navigation | Current location/lens/filter announced; skip target; deep-link context understandable |
| A5 Timeline/path | Ordered semantic list alternative; direction, type, time, and missing-hop text |
| A6 AI/narrative | Streaming does not steal focus; citations navigable; AI/simulation clearly labelled |
| A7 Board/export | Reading order, tagged output, alt text, contrast, pagination and confidentiality metadata |

## 7. Foundation and context catalog

| ID / component | Used in | Properties and inputs | Outputs | Services consumed | Permission | State / accessibility |
|---|---|---|---|---|---|---|
| F01 Semantic Tokens | ALL | theme, semantic role, density, status, authority, evidence | CSS/theme variables only | None | P0 | Token fallback is build error; A0 |
| F02 Responsive Grid | ALL | breakpoint, columns, span, order, region label | layout regions | None | P0 | Content order remains logical at every breakpoint; A0 |
| F03 Focus/Overlay Foundation | ALL drawers/modals | invoker ref, title, modality, close policy | close/return-focus intent | None | P0 | Safe close on error; A2 |
| F04 Icon and Label Vocabulary | ALL | governed semantic key, visible label, icon, assistive text | labelled symbol | None | P0 | Unknown key uses explicit neutral label; A0 |
| F05 Formatting | ALL | typed value, unit, currency, locale, period, precision | display plus machine-readable value | Financial rules for financial values | P0/P3 | Missing unit is invalid/unknown, never guessed; A0 |
| F06 Component State Frame | ALL data components | state, reason, coverage, freshness, retry/next action | retry or permitted next-action intent | None | Inherits child | Implements all section 4 states; A0 |
| N01 Executive Page Header | SH, CC, personas, SD, XS, XAI, BI | workspace, purpose, persona, scope, period, trust summary | lens/filter/trust/search/AI intents | Registry; evidence summary | P1 | Partial context visibly marked; A4 |
| N02 Persona Lens Selector | SH | authorized lenses, active lens | explicit lens-change intent | RBAC/tenant context | P1 | Unauthorized lenses absent, not disabled/revealed; A4 |
| N03 Global Filter Bar | SH, CC, personas, SD, XS, BI | filter schema, selected values, allowed values | apply/clear filter delta | Registry; Query Engine | P1, P3 where financial | Empty value sets explained; A4 |
| N04 Breadcrumb/Deep Link | SH, SD, XS | canonical path, checkpoint, preserved context | navigate intent | Registry; Relationship Intelligence | P1 | Stops at missing governed path; A4/A5 |
| N05 Data Trust Control | ALL data surfaces | trust summary, coverage, freshness, unknown counts | open Evidence Drawer | WP-010 Evidence; source services | P1/P2 | Always visible for partial/stale/conflict; A1 |
| N06 Search Launcher | SH, CC, personas, SD | query seed, visible authorized context | open search intent | Enterprise Search | P1 | Search unavailable state is explicit; A4 |
| N07 AI Launcher | SH, CC, personas, SD, XS | removable visible context chips, allowed modes | open AI intent | Enterprise Copilot | P1 | No hidden context; unavailable modes omitted; A4/A6 |

## 8. Executive card catalog

| ID / component | Used in | Properties and inputs | Outputs | Services consumed | Permission | State / accessibility |
|---|---|---|---|---|---|---|
| C01 Executive Narrative Card | CC, CEO, CIO, CFO, BI | NarrativeView: claims, drivers, consequence, trust, version, review state | explain, cite, open evidence; draft-review intent where allowed | Copilot over governed claims; Query Engine; WP-010 | P1; P5 in Board | Unsupported until narrative PDR rules approved; A1/A6 |
| C02 KPI Card | CC, CEO, CIO, CFO, EA, OPS, FO, SD, BI | MetricView: label, value, delta, period, meaning, unit, source | detail/evidence intent | Query Engine; Financial Data Fabric when financial | P1/P3 | No value without unit/period/source; A1 |
| C03 Health Card | CC, persona workspaces, SD | approved state/model, trend, factors, coverage, version | factor/detail/evidence intent | Query Engine; approved Decision Framework output | P1 | Unapproved health model renders Unsupported; A1 |
| C04 Risk Card | CC, CEO, CIO, EA, OPS, SD, BI | consequence, scope, owner, trend, mitigation, evidence | detail/path/evidence intent | Query Engine; Relationship Intelligence | P1 | Missing topology blocks blast-radius assertion; A1 |
| C05 Material Change Card | CC, CEO, CIO, CFO, OPS, FO, SD, BI | change, magnitude, drivers, consequence, materiality rule/version | driver/detail/evidence intent | Query Engine; Financial Data Fabric; Relationship Intelligence | P1/P3 | Unsupported until materiality rule is approved; A1 |
| C06 Attention Item | CC, CEO, CIO, CFO, OPS, FO | AttentionView: priority supplied by service, subject, consequence, owner, due/evidence state | detail/evidence/workflow intent | Decision Intelligence | P1/P4 | Component never computes or changes priority; A1 |
| C07 Finding Card | CIO, CFO, EA, OPS, FO, SD | FindingView: type, severity, subject, evidence, lifecycle | detail/evidence intent | Decision Intelligence | P1 | Must not use recommendation/decision styling; A1 |
| C08 Recommendation Card | CC, CEO, CIO, CFO, EA, OPS, FO, SD | RecommendationView: proposal, alternatives, value states, assumptions, actions | compare/simulate/package-evidence/workflow request | Decision Intelligence; WP-010; Scenario Intelligence | P1/P4 | Proposal never shown as decision or authorization; A1 |
| C09 Scenario Card | CIO, CFO, EA, FO, SD, XAI | ScenarioView: baseline, immutable inputs, impacts, confidence, unknowns | compare/evidence-package intent | Scenario Intelligence | P1/P3 | Permanent analysis-only banner; no implicit winner; A1/A6 |
| C10 Decision Card | CC, CEO, CIO, CFO, OPS, BI, SD | DecisionView: WP-011 id/state, authority scope, evidence, actor, next step | open governed decision intent only | WP-011 Decision | P4/P5 | Actions exactly match server-supplied authority; A1 |
| C11 Outcome Card | CC, CEO, CFO, CIO, FO, SD, BI | OutcomeView: execution ref, verified status/value, method, evidence | detail/evidence intent | WP-013 Execution/Outcome; Financial Data Fabric | P1/P3/P5 | Projected/potential value never labelled realized; A1 |

## 9. Explanation and exploration catalog

| ID / component | Used in | Properties and inputs | Outputs | Services consumed | Permission | State / accessibility |
|---|---|---|---|---|---|---|
| E01 Evidence Indicator | ALL claims/cards | evidence state, coverage, freshness, authority | open evidence intent | WP-010 Evidence | P1/P2 | Text plus icon, never color alone; A0 |
| E02 Evidence Drawer | ALL | EvidenceView: claim, sources, lineage, assumptions, unknowns, raw refs | source/lineage navigation, close | WP-010; originating public service | P2 | Restricted fields explained; preserves invoking context; A2 |
| E03 Factor Breakdown | C03, C04, recommendations | approved factors, contributions, model version, evidence refs | factor evidence/detail intent | Approved Decision Framework outputs | P1/P2 | Unsupported without approved model/version; A3 |
| E04 Driver List | CC, CFO, FO, SD, BI | ordered service-supplied drivers, amounts, units, evidence | driver detail/evidence intent | Query Engine; Financial Data Fabric | P1/P3 | Ordering source/rule disclosed; component does not rank; A3 |
| E05 Relationship Path | CIO, EA, OPS, SD, XS | governed nodes/edges, direction, evidence, completeness | node/edge/evidence navigation | Relationship Intelligence; Registry | P1/P2 | Explicit stop at incomplete topology; A5 |
| E06 Timeline | CC, all personas, SD, BI | TimelineEventView: event, occurred/observed time, source, authority, evidence | event detail/evidence intent | Registry/versioning; WP-010–013; source services | P1/P2/P5 | Both timestamps exposed; chronological list alternative; A5 |
| E07 Comparison Matrix | CIO, CFO, EA, FO, SD, XAI | baseline, up to three alternatives, common dimensions/units/unknowns | select/detail/evidence intent | Scenario Intelligence; Query Engine | P1/P3 | No visual or semantic implicit winner; A3 |
| E08 Chart Panel | CC, personas, SD, BI | business question/answer, series, unit, period, source, table data | table toggle/detail/evidence intent | Query Engine; Financial Data Fabric | P1/P3/P5 | Table alternative mandatory; never decorative; A3/A7 |
| E09 Executive Table | persona workspaces, SD, XS, BI | columns, rows, stable keys, sort/page state, row actions | sort/page/row/evidence intent | Query Engine; Search; Financial Data Fabric | P1/P3/P5 | Server-authorized columns/actions only; semantic headers/caption; A3 |

## 10. AI, Search, and Board catalog

| ID / component | Used in | Properties and inputs | Outputs | Services consumed | Permission | State / accessibility |
|---|---|---|---|---|---|---|
| A01 Executive Answer Card | XS, XAI | answer, consequence, governed facts, unknowns, citations, subject refs | detail/evidence/Ask AI intent | Enterprise Search; Query Engine; Knowledge Graph | P1/P2 | No-result differs from unknown/unauthorized; A1/A6 |
| A02 AI Context Bar | XAI | tenant-safe persona/scope/subject/time/filter chips, removable flags | remove/reset context intent | Application composition only | P1 | All model context visible; required chip removal explains impact; A4/A6 |
| A03 AI Response | XAI | answer, claims, citations, trust, supported actions/modes | explain/compare/simulate/draft-brief intent | Enterprise Copilot; governed source services | P1/P2 | AI-labelled; partial/unknown/citation state announced; A6 |
| A04 Scenario Input Panel | XAI, CIO, CFO, EA, FO, SD | scenario type, explicit input schema, immutable baseline, assumptions | validate/run-analysis intent | Scenario Intelligence | P1/P3 | Invalid/unsupported assumptions block run with reason; A3/A6 |
| B01 Report Builder | BI | report type, scope, period, checkpoint, coverage, sections | validate/create-draft intent | Registry; Query Engine; WP-010 | P5 | Blocks draft when checkpoint/coverage policy fails; A7 |
| B02 Review Workspace | BI | deterministic facts, narrative draft, revisions, comments, reviewers | propose text edit/comment/review intent | Copilot for draft phrasing; report composition | P5 | Fact fields immutable; AI text and human edits attributable; A6/A7 |
| B03 Sign-off Panel | BI | reviewers, state, confidentiality, integrity, authority actions | governed sign-off request | Board workflow/sign-off authority | P5 | Actions server-authorized; separation of duties visible; A7 |
| B04 Presentation Template | BI | approved template, sections, content views, branding, pagination | preview/export request | Report composition only | P5 | Native reading order and overflow validation; A7 |
| B05 Evidence Appendix | BI | claim-to-source map, methodology, unknowns, integrity metadata | evidence navigation/export | WP-010; source services | P5/P2 | Redactions and unresolved claims explicit; tagged export; A7 |

## 11. Surface composition matrix

This matrix is normative for reuse. A component outside a listed surface requires a
catalog amendment and, where behavior changes, a PDR.

| Surface | Required component families |
|---|---|
| Executive Shell | F01–F06, N01–N07 |
| Command Center | N01, N03, N05–N07; C01–C06, C08, C10–C11; E01–E04, E06, E08 |
| CEO | C01–C06, C08, C10–C11; E01–E04, E06, E08–E09 |
| CIO | C01–C10; E01–E09; A04 |
| CFO | C01–C02, C04–C11; E01–E04, E06–E09; A04 |
| Enterprise Architect | C02–C04, C07–C09; E01–E09; A04 |
| Operations | C02–C08, C10; E01–E06, E08–E09 |
| FinOps | C02, C04–C09, C11; E01–E04, E06–E09; A04 |
| Business Service Detail | N04–N07; C02–C11; E01–E09; A04 |
| Executive Search | N03, N05, N07; A01; E01–E02, E05, E09 |
| Executive AI | A01–A04; E01–E03, E07; relevant C08–C09 |
| Board Intelligence | B01–B05; C01–C05, C10–C11; E01–E04, E06, E08–E09 |

## 12. Service ownership constraints

| P4.3 source | Allowed component use | Catalog-wide prohibition |
|---|---|---|
| Registry | Canonical identity, version, ownership, filter values | Creating UI identity authority |
| Relationship Intelligence | Governed paths and explicit zero-edge state | Inferring topology or blast radius |
| Knowledge Graph | Read-only context for answers/details | Persisting a second graph |
| Query Engine | Bounded facts/findings and partial states | Page-local query/business semantics |
| Enterprise Search | Canonical ranked discovery | A second index or ranking engine |
| Enterprise Copilot | Grounded cited phrasing/explanation | Scores, decisions, approval, execution |
| Decision Intelligence | Existing findings/proposals/priority | UI recommendation or ranking logic |
| Scenario Intelligence | Explicit analysis-only alternatives | Mutation, automatic winner, execution |
| Financial Data Fabric | Authoritative periods/spend/reconciliation | UI-authored authoritative totals |
| Classification | Versioned classification/evidence | UI inference |
| WP-010–013 | Evidence through verified outcome | Skipping or relabelling governed states |

## 13. P5.1 component definition of done

Each component PR must provide:

- a typed interface and contract-version compatibility statement;
- catalog-linked stories for default and every applicable section 4 state;
- representative, boundary, long-content, localization, and reduced-motion fixtures;
- tenant, persona, field-entitlement, evidence, and authority tests;
- unit, interaction, keyboard, screen-reader, automated accessibility, responsive,
  browser, light/dark, and visual-regression evidence;
- proof that no page-local business formula, rank, financial truth, or workflow
  authority was introduced;
- documentation of supported and explicitly unsupported behavior;
- screenshots at approved desktop, tablet, and mobile breakpoints;
- hosted CI and an explicit Product Freeze/ADR/PDR conformance statement.

## 14. Mini-release map

| Product release | Work package | Deliverable |
|---|---|---|
| v2.1 | P5.1 | Certified Executive Component Library |
| v2.2 | P5.2 | Executive Shell and Navigation |
| v2.3 | P5.3 | Executive Command Center |
| v2.4 | P5.4 | Persona Workspaces |
| v2.5 | P5.5 | Board Intelligence |

Each is independently reviewable, reversible, demonstrable, and gated. A release
does not authorize the next work package.

## 15. Remaining gate before component code

P5.1 coding begins only after the Product Freeze v2.0 entry conditions are recorded
as satisfied and a bounded engineering package names:

- the authorized component IDs and PR boundary;
- approved tokens, breakpoints, tooling, and reference browsers;
- approved field-level evidence entitlements;
- the P4.3 manual browser-gate disposition;
- required PDRs and accountable reviewers;
- acceptance fixtures, test commands, screenshots, and hosted-CI checks;
- commit/push/PR/merge/tag authority.

Until then, P4 remains frozen except for separately authorized bug, security,
performance, and compatibility work.
