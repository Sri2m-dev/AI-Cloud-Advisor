# WP-005 Activation Specification

Status: Draft for governance review
Normative: No
Implementation authorization: No
Work package: WP-005 — Canonical coverage and stewardship
Increment: Increment 1 — Trusted Business Service context
Planning baseline: `main` at `2db4d5a8d32635708797f9ffc96fafd2db001d43`
Released foundation: `v1.2.0-data-fabric`
Delivery owner: Srikanth Mudaliar

## 1. Purpose

This document proposes the execution controls for **WP-005 — Canonical coverage
and stewardship**. The authoritative Program G catalog assigns WP-005 an
authority matrix, identity and quality queues, and a coverage data product. Its
dependencies are WP-002 and WP-004.

This draft neither activates WP-005 nor changes the ratified architecture, Data
Fabric contracts, source authority, schemas, or runtime behavior. Unresolved
decisions in Section 8 must be made by the Owner before an activation record may
declare the package ready.

## 2. Catalog Objective

WP-005 must make canonical coverage measurable and unresolved canonicalization
work governable. It must:

1. identify which approved source is authoritative for each governed attribute;
2. expose tenant-scoped identity-resolution and quality-review queues;
3. provide a deterministic coverage and freshness data product;
4. record steward decisions and their evidence without silently merging,
   correcting, or deleting canonical records; and
5. preserve the released P3 Data Fabric and WP-001 through WP-004 guarantees.

The catalog acceptance summary is: **scoped quality/freshness and steward
workflow accepted**. Its primary catalog risk is unresolved identities.

## 3. Proposed Execution Scope

After a separate owner activation, WP-005 may implement:

1. A versioned authority-matrix model that assigns authority at an explicitly
   approved granularity and records organization, tenant, domain, entity type,
   attribute, source, steward role, effective interval, and rationale.
2. Deterministic evaluation of canonical coverage, identity disposition,
   quality status, and freshness using existing canonical, identity, ontology,
   provenance, lineage, and quality contracts as read-only inputs.
3. Tenant-scoped identity-review items for ambiguous, duplicate, no-match, and
   low-confidence resolution outcomes.
4. Tenant-scoped quality-review items for failed rules, insufficient evidence,
   stale observations, missing authority, and threshold breaches.
5. A steward workflow with explicit states, allowed transitions, actor,
   rationale, evidence references, timestamps, and optimistic revision.
6. A deterministic coverage data product that discloses numerator,
   denominator, excluded population, missing/unknown population, freshness
   policy, evaluated time, scope, and supporting evidence.
7. Replay-safe, auditable decisions that propose canonical action but do not
   bypass the existing atomic Data Fabric write boundary.
8. Offline fixtures and negative tests covering authorization, conflicts,
   authority gaps, stale data, replay, and cross-tenant isolation.

## 4. Explicit Exclusions

WP-005 does not authorize:

- a new canonical entity or relationship type;
- modification of P3 contracts, migrations `0001`–`0018`, RLS, grants,
  Supabase configuration, or database objects;
- direct or sequential mutation that bypasses approved atomic write RPCs;
- automatic canonical merges based only on a queue or coverage result;
- graph mutation, graph authority, or Knowledge Graph projection work;
- Business Service registry or posture behavior assigned to WP-006/WP-007;
- evidence registry/use behavior assigned to WP-010;
- recommendation, decision, execution, outcome, AI, or Enterprise Memory work;
- connector capability, extraction, scheduling, or runtime changes;
- public API, UI, dashboard, background-job, or event integration unless a
  later owner-approved amendment explicitly authorizes it;
- production or customer data access during implementation validation;
- resolving migration `0018` relationship-version history deferral;
- unrelated CI/CD, dependency, or repository maintenance.

Discovery of a required excluded change stops the package and returns it to
Program G governance.

## 5. Proposed Component Boundaries

### Authority matrix

- **Responsibility:** declare approved source authority and stewardship scope.
- **Inputs:** owner-approved authority assignments and effective dates.
- **Outputs:** immutable/versioned authority rules and deterministic lookup.
- **Constraint:** absence or conflict is explicit; no implicit authority is
  inferred from source order, volume, recency, or connector identity.

### Identity review queue

- **Responsibility:** surface unresolved identity outcomes for steward review.
- **Inputs:** existing WP-002 context, WP-004 evidence references, and P3
  identity-resolution results.
- **Outputs:** scoped review items and proposed dispositions.
- **Constraint:** a disposition is not itself a canonical merge or write.

### Quality review queue

- **Responsibility:** surface quality, authority, evidence, and freshness gaps.
- **Inputs:** existing P3 quality results plus approved authority/freshness
  policy.
- **Outputs:** scoped review items and proposed remediation.
- **Constraint:** unknown and missing data remain visible and are never scored
  as healthy by omission.

### Steward workflow

- **Responsibility:** govern assignment, review, disposition, reopening, and
  closure with accountable actors and evidence.
- **Constraint:** deny by default, enforce optimistic revision, retain audit
  history, and prohibit self-authorized cross-tenant action.

### Coverage data product

- **Responsibility:** report canonical coverage and freshness transparently.
- **Constraint:** it is derived, reproducible, tenant-scoped, and never a source
  of canonical authority.

## 6. Repository Boundaries Proposed for Approval

The exact implementation allowlist cannot become authoritative until Section 8
is resolved. The proposed narrow areas are:

| Area | Proposed use |
| --- | --- |
| `canonical_stewardship/` | New isolated policy, queue, workflow, and coverage models |
| `tests/canonical_stewardship/` | Deterministic and negative-path tests |
| `scripts/check_canonical_coverage_stewardship.py` | Non-secret offline certification gate |
| `governance/manifests.json` | Additive WP-003 contract registration, only if required |
| `tests/governance/test_contract_event_governance.py` | Focused additive compatibility assertions |
| `docs/program_g/WP_005_*` | Governance, implementation evidence, and closure records |

Read-only integration inputs are expected to include `authorization/`,
`connector_certification/`, and the existing `data_fabric/` contracts,
identity, registry, quality, semantic, lineage, provenance, versioning, and
persistence interfaces.

No existing Data Fabric or runtime area is writable under this draft. Any need
to change one requires an amended specification and owner approval.

## 7. Proposed Deliverables

- approved and versioned authority matrix;
- identity-review queue contract and deterministic evaluator;
- quality/freshness review queue contract and deterministic evaluator;
- steward workflow with explicit transition and authorization policy;
- canonical coverage/freshness data-product contract and calculator;
- offline fixtures and a non-secret certification gate;
- focused security, replay, revision, authority-conflict, quality, freshness,
  coverage, and tenant-isolation tests;
- additive WP-003 manifest registration if an external contract is introduced;
- architecture-conformance and implementation-evidence report.

## 8. Owner Decisions Required Before Activation

The following are deliberately unresolved. No default is implied.

1. **Authority granularity:** entity family, entity type, attribute, source
   system, or an approved combination.
2. **Authority precedence:** how overlapping rules are rejected or explicitly
   ordered, including effective-time behavior.
3. **Steward roles:** accountable owner, permitted reviewer roles, assignment
   model, and separation-of-duties rules.
4. **Queue persistence:** isolated in-memory implementation, approved existing
   persistence abstraction, or separately governed durable storage.
5. **Workflow states:** final state names, transition authority, reopen policy,
   escalation, expiry, and service-level expectations.
6. **Freshness policy:** authoritative clock, per-domain thresholds, unknown
   timestamps, and late-arriving evidence.
7. **Coverage denominator:** eligible population, exclusions, inactive records,
   unresolved identities, and missing-source handling.
8. **Canonical action boundary:** whether steward dispositions remain proposals
   only or may invoke an existing secured atomic write through a separately
   approved adapter.
9. **Lighthouse domains:** the bounded entity families and synthetic fixtures
   used to prove the framework.
10. **Implementation branch and final repository allowlist.**

R-003 from the Program G risk register—ambiguous source authority—remains a
blocking risk until decisions 1 and 2 are recorded.

## 9. Definition of Ready

- [x] Exact catalog entry, title, increment, risk, and dependencies identified.
- [x] WP-002 closed.
- [x] WP-004 closed at merge commit
  `2db4d5a8d32635708797f9ffc96fafd2db001d43`.
- [x] Released foundation identified.
- [x] Relevant P3 contracts and ADRs inventoried.
- [x] Initial scope, exclusions, components, tests, and evidence proposed.
- [ ] Every Section 8 owner decision recorded.
- [ ] Source-authority matrix approved by governance/domain authority.
- [ ] Exact repository allowlist approved.
- [ ] Activation specification reviewed and merged.
- [ ] Separate Activation Record created, reviewed, and merged.
- [ ] Explicit owner implementation authorization recorded.

WP-005 remains **READY, NOT ACTIVE** until every unchecked item is satisfied.

## 10. Proposed Acceptance Criteria

### Authority and identity

1. Every evaluated governed attribute resolves to exactly one effective
   authority or an explicit missing/conflict result.
2. Cross-tenant and cross-organization authority lookup is denied.
3. Ambiguous, duplicate, no-match, and low-confidence outcomes create
   deterministic review items without mutating canonical state.
4. Replaying identical evidence produces the same review identity and no
   duplicate effective item.

### Quality and freshness

1. Quality items preserve rule, score, threshold, subject, evidence, and
   evaluation time.
2. Freshness uses the approved clock and threshold policy; missing timestamps
   produce unknown or failed status according to the approved decision.
3. Missing and excluded populations are reported separately and never hidden in
   a favorable aggregate.

### Steward workflow

1. Missing context, insufficient role, tenant mismatch, invalid transition,
   and stale revision are rejected.
2. Assignment and disposition preserve actor, rationale, evidence references,
   timestamps, prior state, and revision.
3. A queue disposition cannot directly bypass canonical write controls.

### Coverage product

1. Coverage is deterministic for identical inputs and policy version.
2. Results disclose scope, numerator, denominator, exclusions, unknowns,
   freshness, policy version, and evaluated time.
3. Drill-down reconciles exactly with aggregate counts.

### Compatibility and regression

1. WP-001 compatibility, WP-002 authorization, WP-003 governance, and WP-004
   certification gates pass.
2. Full collection has zero errors; the full suite has zero failures and only
   documented opt-in skips.
3. The P3 non-secret gate remains 94/94 unless separately governed.
4. Five gated Supabase integrations collect and produce five expected opt-in
   skips without secrets; no live validation runs.

## 11. Proposed Test and Evidence Strategy

Tests must be deterministic, tenant-scoped, offline, and synthetic. Required
categories are:

- authority lookup, absence, overlap, precedence, and effective-time cases;
- identity and quality queue creation, replay, deduplication, and isolation;
- workflow roles, transitions, revision conflicts, reopen/closure, and audit;
- coverage numerator/denominator reconciliation and freshness boundaries;
- missing, malformed, stale, and cross-tenant negative cases;
- compatibility and full regression gates from WP-001 through WP-004;
- compile/import, Ruff, `pip check`, full collection, full pytest, and P3 gate;
- hosted CI on the review commit and hosted CI/CD on the merge commit.

Evidence must record the approved authority policy, synthetic fixture identities,
exact operations and counts, changed-file/exclusion review, all test totals,
warnings, run IDs, merge commit, clean-main verification, and closure decision.

## 12. ADR Traceability

| Authority | Application to WP-005 |
| --- | --- |
| ADR-008 — Enterprise Data Fabric | Data Fabric remains canonical integration layer; source authority remains explicit. |
| ADR-009 — Canonical Entity Model | Canonical identity and source identifiers retain distinct meanings. |
| ADR-010 — Enterprise Semantic Layer | Coverage and stewardship use governed canonical concepts and mappings. |
| ADR-011 — Identity Resolution | Low-confidence and ambiguous matches require candidates/review, not silent merges. |
| ADR-012 — Data Lineage | Review and coverage results remain traceable to source-to-canonical events. |
| ADR-013 — Provenance Framework | Authority, trust, transformation, and evidence are explicit. |
| ADR-014 — Versioning Strategy | Policy, workflow, and externalized contracts require governed versions. |
| ADR-015 — Data Quality Framework | Quality evaluation is deterministic, explainable, and scoped. |
| ADR-016/017 — Persistence Architecture/Adapter | Existing stores and atomic boundaries are not bypassed or modified by default. |
| WP-001–WP-004 | Compatibility, authorization, contract governance, and connector evidence remain mandatory gates. |

## 13. Risks and Stop Conditions

| Risk | Impact | Required control |
| --- | --- | --- |
| Ambiguous source authority | High | Owner-approved matrix and conflict policy before implementation |
| Steward action becomes hidden canonical write | Critical | Proposal-only default; explicit secured adapter decision required |
| Cross-tenant queue or aggregate leakage | Critical | WP-002 authorization and negative tests at every operation |
| Coverage hides unknown or excluded data | High | Explicit denominator, exclusions, unknowns, and drill-down reconciliation |
| Queue creates an alternate source of truth | High | Derived workflow artifacts; canonical state remains in Data Fabric |
| Schema or migration creep | High | No existing Data Fabric changes; stop and return to governance |
| WP-006/WP-010 scope leakage | High | No Business Service or evidence-registry capability |

Any Critical failure, unresolved authority decision, required excluded change,
or need for live data stops activation or implementation.

## 14. Governance Sequence

1. Review this draft and answer every Section 8 decision.
2. Update the specification with the Owner's exact decisions.
3. Review and merge the documentation-only specification.
4. Create a separate WP-005 Activation Record against the resulting `main`.
5. Obtain explicit owner activation in that record.
6. Only then create the approved implementation branch.

Until that sequence completes, engineering remains blocked and WP-005 remains
**READY, NOT ACTIVE**. WP-006 through WP-020 remain inactive.
