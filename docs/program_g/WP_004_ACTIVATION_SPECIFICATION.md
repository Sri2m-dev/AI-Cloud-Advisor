# WP-004 Activation Specification

Status: Owner decisions recorded; documentation review and merge pending
Implementation authorization: No
Work package: WP-004 — Connector evidence certification
Increment: Increment 1 — Trusted Business Service context
Planning baseline: `main` at `4f0ab5c893f12694a5ce28e4c046b5d18869eef7`
Released foundation: `v1.2.0-data-fabric`
Delivery owner: Srikanth Mudaliar

## 1. Purpose

This document defines the execution controls for **WP-004 — Connector evidence
certification**. The authoritative catalog assigns WP-004 to Increment 1 and
requires WP-002 and WP-003 to be closed first. Both dependencies are closed.

This specification does not activate WP-004. It supplements, and does not
redefine, the ratified Program G catalog.

## 2. Objective

The catalog objective is to use the existing connector framework to produce and
certify an **observation envelope** and **checkpoint/reconciliation evidence**.
Certification must cover replay, duplicates, pagination, deletion handling, and
secret safety. It must not create a new connector capability or replace an
existing production path.

## 3. Execution scope

Upon separate owner activation, WP-004 may:

1. Define a versioned certification profile over existing `ConnectorRecord`,
   `ConnectorRuntimeContext`, `ConnectorSyncResult`, and
   `ConnectorExecutionResult` evidence.
2. Provide an offline certification harness that evaluates deterministic test
   fixtures without calling production systems. AWS and Microsoft 365 are the
   approved lighthouse connectors; their existing evidence behavior may be
   certified without changing their capabilities, authentication, source APIs,
   ingestion, or outputs.
3. Certify that every observation is attributable to one connector execution,
   organization, tenant authorization context, source record, observation time,
   content checksum, and contract version.
4. Certify checkpoint continuity, monotonic progress, replay determinism, and
   explicit terminal state across controlled multi-page fixtures.
5. Certify duplicate classification and prove that replay does not create a
   second effective observation for the same scoped evidence identity.
6. Certify an immutable, tenant-scoped, certification-only logical tombstone
   without physically deleting immutable evidence. The tombstone contains
   `source_system`, `source_entity_type`, `source_entity_id`, `tenant_id`,
   `organization_id`, `observed_at`, `deleted_at`, `checkpoint_reference`,
   `deletion_reason`, and `evidence_hash`.
7. Reconcile extracted, normalized, accepted, rejected, duplicate, deleted, and
   published counts for each controlled run.
8. Verify that secret values never appear in envelopes, reports, logs, errors,
   checkpoints, or serialized evidence.
9. Apply WP-002 deny-by-default organization and tenant authorization to every
   certification scenario.
10. Register the certification profile as an additive, backward-compatible
    WP-003 manifest without changing existing providers, consumers, or runtime
    event behavior.

All certification writes must use in-memory or temporary test-owned stores.
Live-source, Supabase, database, external-write, production-credential, customer
environment, cloud-account, and Microsoft 365 tenant access is prohibited.

## 4. Explicit exclusions

WP-004 does not authorize:

- changing Data Fabric contracts, canonical entities, relationships, identity
  resolution, lineage, provenance, quality, or version history;
- changing schemas, migrations, RLS, grants, Supabase configuration, or durable
  database objects;
- changing production connector extraction, normalization, publication,
  scheduling, retry, credential, or runtime behavior;
- adding a connector, provider integration, source endpoint, entity type, or
  production sync mode;
- replacing or migrating current connector execution paths;
- adding persistent connector registry, checkpoint, or evidence storage;
- changing public APIs, dashboards, Streamlit pages, or other UI;
- modifying Knowledge Graph projections or graph queries;
- adding canonical coverage or stewardship assigned to WP-005;
- adding Business Service behavior assigned to WP-006/WP-007;
- adding the evidence registry/use model assigned to WP-010;
- adding execution/action behavior assigned to WP-013;
- adding AI, agent, recommendation, decision, or Enterprise Memory behavior;
- resolving the migration 0018 relationship-history deferral;
- addressing unrelated CI/CD or Node.js action maintenance.

Discovery of a required change in an excluded area returns WP-004 to Program G
governance; it is not permission to broaden implementation.

## 5. Authorized repository areas

After separate activation, modifications are limited to:

| Area | Authorized use |
|---|---|
| `connector_certification/` | New offline certification profiles, result models, fixture protocols, and reconciliation rules |
| `tests/connector_certification/` | Focused deterministic and negative-path certification tests |
| `scripts/check_connector_evidence_certification.py` | One non-secret executable certification gate |
| `governance/manifests.json` | Additive registration of the approved certification profile under WP-003 policy |
| `tests/governance/test_contract_event_governance.py` | Focused assertions proving the additive manifest preserves existing providers and consumers |
| `docs/program_g/WP_004_*` | Activation, implementation evidence, and closure documentation |

The following are integration inputs and are read-only for WP-004:

- `connector_sdk/`;
- `connector_runtime/`;
- `connector_auth/` and `connector_secrets/`;
- `connector_registry/`, `connector_persistence/`, and
  `connector_observability/`;
- concrete packages under `connectors/`;
- `data_fabric/`, `migrations/`, `supabase/`, APIs, services, pages, and
  schedulers.

Any implementation need outside the authorized list requires an amended
specification and another owner decision.

## 6. Component boundaries

### Certification profile

- **Responsibility:** define the evidence fields and invariants being certified.
- **Inputs:** existing connector record, runtime context, execution/sync result,
  and verified WP-002 authorization context.
- **Outputs:** an immutable, versioned certification observation used only by
  the harness and evidence report.
- **Interface:** deterministic construction and validation functions with no
  network, database, or production publishing side effects.
- **Constraint:** it is not a new canonical Data Fabric entity or production
  event.

### Fixture source and pagination protocol

- **Responsibility:** model controlled pages, cursors, replay, duplicates, and
  deletion signals.
- **Inputs:** test-owned, deterministically ordered pages and an initial
  tenant-, connector-, and stream-specific checkpoint containing an opaque
  source-native cursor.
- **Outputs:** deterministic page results and the next checkpoint or terminal
  marker.
- **Interface:** certification-only protocol under `connector_certification/`.
- **Constraint:** it does not alter `BaseConnector.extract()` or vendor APIs,
  invent a universal cursor format, or advance a checkpoint until the complete
  page is validated and reconciled. Partial, expired, or invalid cursor paths
  fail without checkpoint advancement.

### Reconciler

- **Responsibility:** compare scoped source evidence with observed outcomes.
- **Inputs:** certification observations, page evidence, checkpoints, duplicate
  decisions, deletion decisions, and execution counters.
- **Outputs:** pass/fail result with exact counts and discrepancies.
- **Interface:** pure or in-memory evaluation.
- **Constraint:** no mutation of source, canonical, or graph records.

### Certification runner and report

- **Responsibility:** execute profiles and emit reviewable evidence.
- **Inputs:** named certification profile and controlled fixtures.
- **Outputs:** deterministic machine-readable result plus concise human summary.
- **Interface:** non-secret command-line gate.
- **Constraint:** secret material is never accepted as reportable evidence.

### Existing connector runtime

- **Responsibility:** remain the unchanged provider of current connector
  contracts and lifecycle results.
- **Inputs/outputs:** unchanged from ADR-007 and the released implementation.
- **Constraint:** WP-004 observes and certifies; it does not rewire runtime.

## 7. Deliverables

### Mandatory

- versioned connector evidence certification profile;
- deterministic observation-envelope validation;
- fixture pagination and checkpoint certification protocol;
- reconciliation engine and structured result;
- replay, duplicate, deletion, pagination, reconciliation, tenant, and secret
  negative tests;
- executable non-secret certification gate;
- additive WP-003 contract registration if a new externalized schema is needed;
- `docs/program_g/WP_004_IMPLEMENTATION_EVIDENCE.md`;
- architecture-conformance, changed-file, exclusion, and validation evidence.

### Optional, only if needed within authorized areas

- JSON output from the certification gate for CI artifact retention.

### Out of scope

Every item listed in Section 4, including live connectors, persistent storage,
runtime rewiring, and later-package capabilities.

## 8. Definition of Ready

- [x] Ratified catalog entry and exact title identified.
- [x] Increment 1 placement confirmed.
- [x] WP-002 and WP-003 closure confirmed.
- [x] Baseline and released foundation confirmed.
- [x] Existing connector SDK/runtime/certification inventory completed.
- [x] Architecture and compatibility constraints recorded.
- [x] Authorized and prohibited repository areas proposed.
- [x] Test and evidence strategy defined.
- [x] AWS and Microsoft 365 lighthouse scope approved.
- [x] Certification-only logical tombstone representation approved.
- [x] Opaque cursor and post-reconciliation checkpoint semantics approved.
- [x] Additive WP-003 certification manifest approved.
- [x] Live-source certification prohibited.
- [x] Repository allowlist approved.
- [x] Exact implementation branch approved.
- [ ] Activation specification committed, reviewed, and merged into `main`.
- [ ] Explicit implementation activation recorded after merge.

WP-004 is not ready for activation until every unchecked item is dispositioned.

## 9. Definition of Done

- [ ] Implementation changes remain within Section 5.
- [ ] Every mandatory deliverable exists.
- [ ] All Section 10 acceptance criteria pass.
- [ ] Focused, negative, compatibility, full regression, and P3 gates pass.
- [ ] Secret-free integration gating produces only expected skips.
- [ ] Architecture conformance and explicit exclusions are evidenced.
- [ ] Dependency, compile/import, and Ruff checks pass.
- [ ] Hosted CI passes on the final review commit.
- [ ] Program G review approves merge.
- [ ] Hosted CI and CD pass on the exact merge commit.
- [ ] Local and remote `main` are synchronized and clean.
- [ ] Post-merge evidence is recorded and WP-004 receives a closure decision.

## 10. Acceptance criteria

### A. Functional acceptance

1. A valid controlled source record produces exactly one certification
   observation containing the approved evidence identity and timestamps.
2. Replaying an identical page from the same checkpoint produces the same
   effective evidence identity and checksum, with zero duplicate effective
   observations.
3. Two source records with the same approved scoped deduplication key are
   classified deterministically and reported with exact duplicate counts.
4. A multi-page fixture consumes every deterministically ordered page exactly
   once, preserves each opaque source-native cursor, advances the scoped
   checkpoint only after complete validation and reconciliation, and terminates
   without omission or loop.
5. Restarting from a recorded checkpoint yields the same remaining evidence and
   does not repeat accepted earlier evidence.
6. An approved deletion signal produces one immutable logical tombstone with
   all ten approved fields, is idempotent on replay, does not recreate or mutate
   the source record, and never physically deletes prior certification evidence.
7. Reconciliation accounts exactly for every extracted record as accepted,
   rejected, duplicate, or deleted and reports any count mismatch as failure.
8. Missing identity, checkpoint, page, checksum, or required evidence fields
   fail with a specific non-secret validation error.

### B. Security and tenant-isolation acceptance

1. Missing, malformed, untrusted, organization-mismatched, or tenant-mismatched
   WP-002 context is denied before certification processing.
2. Evidence identity and deduplication scope include organization and tenant;
   records from different tenants can never collapse into one observation.
3. Checkpoints created for one organization/tenant are rejected in another.
4. Secret sentinel values are absent from all serialized results, exceptions,
   logs, checkpoints, checksums, and CI artifacts.
5. Missing or unresolved secret references fail closed without revealing the
   reference value or secret material beyond an approved opaque identifier.

### C. Architecture acceptance

1. The implementation changes no Data Fabric, runtime, concrete connector,
   schema, migration, Supabase, graph, AI, UI, or scheduler file.
2. Certification observations remain non-canonical test/evidence artifacts.
3. No production write, publish, scheduling, retry, or extraction path invokes
   the certification harness.
4. Source evidence remains attributable to the existing connector and execution
   without claiming canonical authority.

### D. Compatibility acceptance

1. The WP-001 compatibility harness reports no released Data Fabric drift.
2. Existing connector public types and call signatures remain unchanged.
3. Any new externalized certification schema is additive, semantically
   versioned, registered, and accepted by the WP-003 gate.
4. Existing provider/consumer manifests remain compatible.

### E. Regression acceptance

1. Focused WP-001 through WP-004 tests pass with zero failures.
2. Full pytest collection completes with zero collection errors.
3. The full suite has zero failures and only documented opt-in skips.
4. The P3 non-secret gate remains 94/94 unless the certified gate itself is
   separately and legitimately changed.
5. Five gated Supabase integrations collect and skip for the expected opt-in
   reason when secrets are absent; no live Supabase validation runs.

### F. Documentation acceptance

1. Implementation evidence lists exact files, commands, totals, exclusions,
   risks, and decisions.
2. Any certification contract includes field definitions, identity scope,
   lifecycle, version, and compatibility policy.
3. No document describes WP-005 or later capability as delivered by WP-004.

### G. Evidence acceptance

1. A deterministic report records input fixture identity, profile version,
   counts, checkpoints, reconciliation result, and non-secret failures.
2. Evidence demonstrates replay, duplicate, pagination, deletion, tenant, and
   secret behavior independently.
3. Hosted and post-merge run IDs are recorded against exact commits.

### H. CI/CD acceptance

1. Hosted CI succeeds on the final review commit and exact merge commit.
2. Hosted CD succeeds on the exact merge commit without altering WP-004 scope.
3. CI logs and artifacts contain no fixture secret sentinel.

### I. Explicit non-goals

Passing certification does not claim production source completeness, canonical
coverage, graph correctness, realized outcomes, or authorization to execute
connector actions.

## 11. Test strategy

The implementation plan must include:

1. focused unit tests for envelope fields, identity, checksum, and validation;
2. table-driven replay, duplicate, pagination, checkpoint, deletion, and
   reconciliation tests;
3. negative WP-002 organization/tenant/service-context tests;
4. secret sentinel tests across reports, exceptions, and serialization;
5. WP-003 schema, compatibility, and additive manifest tests;
6. the WP-001 compatibility harness;
7. existing WP-002 authorization regression;
8. existing WP-003 governance regression;
9. full compile/import, Ruff, `pip check`, collection, and pytest execution;
10. the 94-test P3 gate;
11. collection of five gated integrations and five expected secret-free skips;
12. hosted CI, hosted CD after merge, and clean-main verification.

No live source, cloud account, Microsoft 365 tenant, Supabase, database, or
production test is authorized in WP-004. A future controlled live-source test
requires a separate owner authorization outside this specification.

## 12. Evidence requirements

The WP-004 evidence package must retain:

- activation decision, baseline, branch, owner, scope, and governing ADRs;
- changed-file inventory and diff review;
- explicit confirmation that every Section 4 area remained unchanged;
- certification profile/schema and version;
- fixture identities and non-secret configuration;
- exact focused, negative, regression, P3, and integration-gating totals;
- exact replay, duplicate, page, checkpoint, deletion, and reconciliation
  operations and results;
- architecture and tenant-isolation review;
- dependency, compile/import, lint, and package-resolution results;
- hosted CI/CD run IDs and exact tested commits;
- merge commit, post-merge validation, clean worktree, and closure decision;
- all exceptions, failed gates, remediation, and retained debt.

## 13. ADR traceability

| Authority | Application to WP-004 |
|---|---|
| ADR-007 — Universal Connector Framework | Governs existing connector lifecycle, SDK contracts, secret references, runtime seams, and provider-specific boundaries. WP-004 certifies these interfaces without expanding them. |
| ADR-008 — Enterprise Data Fabric | Prevents connector evidence from becoming canonical authority or bypassing canonical mapping. Data Fabric remains unchanged. |
| ADR-013 — Provenance Framework | Requires source system, collection method, connector/transformation version, timestamps, confidence/quality context, and retained source evidence. Certification verifies traceability without writing provenance records. |
| ADR-014 — Versioning Strategy | Requires a versioned certification profile and governed compatibility for any externalized evidence schema. |
| WP-001 compatibility baseline | Prohibits unapproved released Data Fabric contract drift. |
| WP-002 authorization foundation | Requires deny-by-default organization and tenant scope at the connector boundary. |
| WP-003 contract/event governance | Governs any additive certification schema and its compatibility/deprecation behavior. |

No recovered catalog row assigns a P4 ADR directly to WP-004. Adding another
governing ADR requires explicit architecture-governance confirmation.

## 14. Risk register

| Risk | Likelihood | Impact | Mitigation | Validation |
|---|---|---|---|---|
| Architecture drift into production runtime | Medium | High | Read-only existing framework boundary and changed-file allowlist | Diff and architecture review |
| Incomplete or fabricated evidence | Medium | High | Deterministic fixtures, exact counts, discrepancy failure | Reconciliation negative tests |
| Connector-specific assumptions enter common certification | Medium | High | Provider-neutral profile; lighthouse-specific adapters stay in tests | Run common profile across approved fixtures |
| Replay creates duplicate effective evidence | Medium | High | Stable scoped identity and checksum | Repeat identical page/run tests |
| Pagination omits or loops pages | Medium | High | Monotonic checkpoint rules and visited-page detection | Omission, repetition, and cycle tests |
| Deletion erases historical evidence | Medium | High | Approved tombstone-only semantics | History-retention and replay tests |
| Cross-tenant evidence collision | Low | Critical | WP-002 authorization and tenant-scoped identity/checkpoints | Cross-organization and cross-tenant negatives |
| Secret leakage | Medium | Critical | References only, sentinel scan, redacted failures | Serialized report/log/error tests |
| Backward compatibility break | Low | High | No existing public contract edits; WP-001/WP-003 gates | Compatibility and full regression |
| Schema, Supabase, or Data Fabric creep | Low | High | Explicit prohibition and changed-file allowlist | Diff review and P3 gate |
| Hidden dependency on WP-005/WP-010/WP-013 | Medium | High | Certify evidence only; no stewardship, registry, or execution | Scope and deliverable review |
| Existing framework cannot express approved deletion or pagination semantics | High | Medium | Owner decisions before activation; certification-only adapter | Definition-of-Ready gate |

Any Critical risk failure blocks merge. Any required modification outside the
allowlist requires owner approval before work continues.

## 15. Activation checklist

- [x] Owner decisions in this specification are recorded.
- [ ] Status changes from `READY, NOT ACTIVE` to `ACTIVE` in an explicit record.
- [ ] Delivery owner and engineering executor are recorded.
- [ ] Baseline is refreshed to the then-current clean `main` commit.
- [ ] WP-002 and WP-003 closure remains verified.
- [x] AWS and Microsoft 365 lighthouse scope is selected.
- [x] Deletion, pagination, checkpoint, and manifest decisions are recorded.
- [ ] No excluded-area change is required.
- [x] Branch `feature/wp-004-connector-evidence-certification` is approved for
  creation only after this document is merged and activation is explicit.
- [ ] Acceptance, evidence, CI/CD, rollback, and stop conditions are accepted.

## 16. Post-merge validation

On the exact merge commit on `main`:

1. verify clean and synchronized local/remote `main`;
2. run the WP-004 certification gate and focused tests;
3. run WP-001 compatibility and WP-002/WP-003 regression tests;
4. run compile/import, Ruff, `pip check`, full collection, and full pytest;
5. run the 94-test P3 non-secret gate;
6. collect five gated integrations and verify five expected secret-free skips;
7. verify hosted CI success;
8. verify hosted CD success for all required images;
9. record exact commits, run IDs, counts, warnings, and exceptions;
10. issue a separate Program G closure decision before WP-005 activation.

## Assumptions

- WP-004 is certification of existing framework evidence, not connector feature
  development.
- Certification begins offline with deterministic fixtures.
- Existing runtime and canonical contracts remain immutable for this package.
- WP-002 and WP-003 remain the mandatory authorization and compatibility gates.

## Owner decision record

Authority: Srikanth Mudaliar, Owner of Nexora
Decision date: 2026-07-20

1. WP-004 will implement a reusable certification framework with AWS and
   Microsoft 365 as lighthouse connectors.
2. Deletion uses an immutable, tenant-scoped, certification-only logical
   tombstone. No production schema or Data Fabric contract change is authorized.
3. Pagination preserves opaque source-native cursors. A checkpoint advances
   only after complete validation and reconciliation; replay is idempotent.
4. Certification metadata uses an additive, backward-compatible WP-003 manifest
   profile without changing runtime event behavior.
5. Live-source testing is prohibited. Only deterministic offline fixtures and
   synthetic credentials are permitted.
6. The approved implementation branch, after explicit activation, is
   `feature/wp-004-connector-evidence-certification`.
7. Repository modifications are restricted to Section 5. Scope expansion
   requires a separate owner decision.

## Remaining governance gates

1. Commit and review this documentation-only specification.
2. Merge the approved specification into `main` and complete post-merge CI/CD.
3. Record a separate, explicit implementation activation decision.
4. Only then create the approved implementation branch.

Until all remaining gates are complete, WP-004 remains **READY, NOT ACTIVE**.
