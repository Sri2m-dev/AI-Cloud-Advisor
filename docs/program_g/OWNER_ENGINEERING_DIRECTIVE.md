# Nexora Owner Engineering Directive

## Document Control

| Field | Value |
| --- | --- |
| Program | Nexora Enterprise Platform |
| Governance model | Program G v2.0 — Streamlined Engineering Governance |
| Authority | Srikanth Mudaliar |
| Roles | Owner, Chief Architect, Program Sponsor |
| Decision date | 2026-07-20 |
| Effective baseline | `main` at `7d972796ceac76629d7fb26477e2f0220dffe4ef` |
| Released foundation | `v1.2.0-data-fabric` |
| Decision | Approved |
| Implementation authorization | Standing authority subject to this directive |
| Latest amendment | 2026-07-21 — WP-006 EMRP scope and dependency reclassification |

## Purpose

Program G established and successfully exercised enterprise engineering
governance through WP-001 to WP-004. This directive streamlines the delivery
model for WP-005 through WP-020 while retaining architecture, scope, quality,
evidence, review, merge, and closure controls.

This directive supersedes the requirement to create an individual Activation
Specification and Activation Record for WP-005 through WP-020. Existing
activation documents remain historical governance evidence; they do not impose
an additional activation gate after this directive becomes effective.

## Owner Decision

Effective when this signed directive is merged into `main` and its exact merge
commit passes hosted CI/CD, the Owner grants standing engineering authority for
the remaining approved work packages WP-005 through WP-020.

Standing authority means a work package may enter engineering without a separate
Activation Specification or Activation Record when all of the following are
true:

1. the package is defined by the ratified Program G Work Package Catalog;
2. every catalog dependency required for that package is complete;
3. every governing ADR required by the catalog is accepted and available to the
   implementation team;
4. the work remains within the catalog outcome and acceptance summary;
5. no restriction in this directive requires a separate Owner decision; and
6. it is the next package authorized by catalog sequencing or an approved
   parallel path.

Standing authority does not make all packages simultaneously active and does
not waive hard dependencies. A blocked predecessor blocks dependent
implementation. READY or ACTIVE does not satisfy a dependency that requires
completion.

## Authorized Scope

Standing engineering authority covers these catalog work packages:

```text
WP-005  Canonical coverage and stewardship
WP-006  Enterprise Metadata & Registry Platform (EMRP)
WP-007  Business Service posture product
WP-008  Knowledge projection control
WP-009  Governed query/explainability contracts
WP-010  Evidence registry/use model
WP-011  Recommendation and Decision package
WP-012  Policy and approval integration
WP-013  Execution authorization/outcome verification
WP-014  Financial decision product
WP-015  Portfolio/risk decision products
WP-016  Enterprise Memory
WP-017  AI evaluation and grounded reasoning
WP-018  Agent execution controls
WP-019  Role experience migration
WP-020  Platform scale and operations certification
```

The authoritative title, inputs, outputs, dependencies, key risk, acceptance
summary, and effort remain those in
`docs/program_g/NEXORA_WORK_PACKAGE_CATALOG.md`. This directive does not enlarge
any catalog row.

## Binding Authorities

Engineering remains bound by:

- the ratified Enterprise Architecture and its recorded governing principles;
- accepted ADRs and architecture invariants;
- the Program G Work Package Catalog and dependency map;
- Program G implementation and change governance;
- the released `v1.2.0-data-fabric` compatibility baseline;
- tenant isolation, least privilege, source authority, canonical stewardship,
  evidence traceability, and canonical-no-bypass rules;
- mandatory CI/CD, regression testing, implementation evidence, review,
  post-merge validation, and closure.

If an ADR named by the catalog is unavailable, unresolved, deferred, or
inapplicable, the dependent work package remains blocked until the architecture
authority dispositions it. This directive does not infer missing ADR content.

## Delivery Lifecycle

Each eligible package follows:

```text
Approved catalog work package
        ↓
Dependency and ADR verification
        ↓
Dedicated implementation branch
        ↓
Engineering within catalog scope
        ↓
Implementation evidence
        ↓
Program G review
        ↓
Explicit merge approval
        ↓
Merge
        ↓
Hosted and local post-merge validation
        ↓
Explicit work-package closure
```

An implementation branch is not merge authority. Program G review remains
mandatory and no work package may close before post-merge validation succeeds.

## Mandatory Engineering Requirements

Every work package must:

1. start from current, clean, synchronized `main`;
2. use a dedicated `feature/wp-###-...` branch;
3. modify only areas necessary for its catalog-approved outcome;
4. preserve backward compatibility unless a separately approved change says
   otherwise;
5. enforce WP-002 tenant identity and authorization at every applicable
   boundary;
6. comply with WP-003 contract/event governance for new or changed contracts;
7. preserve WP-004 evidence attribution and connector certification controls;
8. add deterministic positive and negative automated tests;
9. retain architecture, security, compatibility, and changed-file evidence;
10. produce `docs/program_g/WP_###_IMPLEMENTATION_EVIDENCE.md`;
11. pass dependency validation, Ruff, compile/import checks, full collection,
    full regression, applicable focused gates, and the P3 non-secret gate;
12. collect secret-gated integrations and verify their approved no-secret
    behavior;
13. pass hosted CI on the final review commit;
14. receive Program G review and explicit merge approval;
15. pass hosted CI/CD and required local validation on the exact merge commit;
16. leave synchronized `main` clean; and
17. receive an explicit closure decision before a dependent package begins.

Exact test totals may grow as packages add coverage. Existing certified gates
must not be weakened merely to obtain a pass.

## Evidence Requirements

Each implementation evidence record must include:

- work package, catalog scope, dependencies, baseline, branch, and commits;
- architecture and ADR conformance;
- changed files and explicit scope-exclusion review;
- contracts, compatibility impact, and migration impact;
- tenant, authorization, security, privacy, and secret-handling evidence;
- exact tests, passes, failures, skips, warnings, commands, and operations;
- rollback, replay, idempotency, reconciliation, and audit evidence where
  applicable;
- hosted CI/CD run IDs and tested commits;
- merge commit, post-merge results, retained debt, and closure decision.

Evidence must distinguish implemented behavior from documentation, mocks,
proposals, deferred scope, and unexecuted live scenarios.

## Dependency and Sequencing Rules

- WP-005 may begin under this directive because its catalog dependencies WP-002
  and WP-004 are closed. Its previously identified freshness, authority, and
  durable stewardship requirements become implementation acceptance work, not
  separate activation paperwork.
- Owner amendment dated 2026-07-21 accepts ADR-024 and reclassifies WP-006's
  WP-005 dependency. WP-005 engineering is complete, so WP-006 engineering may
  proceed in parallel. WP-006 merge and release remain blocked until WP-005
  release validation completes and WP-005 closes.
- Every later package remains subject to the exact dependency edges in the
  ratified catalog and dependency map.
- Only one new package should be active at a time unless the dependency map
  identifies an independent parallel path and the Owner explicitly selects it.
- A package may perform bounded discovery necessary to implement its approved
  catalog scope. Discovery that reveals scope expansion or an architectural
  change triggers the stop rules below.

## Restrictions Requiring Explicit Owner Approval

Standing authority does not authorize:

- a new work package or removal/reordering of a hard dependency;
- scope expansion beyond a catalog row;
- architectural deviation or a change to an invariant;
- a new or modified ADR that changes architectural direction;
- a public contract break or released-baseline incompatibility;
- platform-wide refactoring or unrelated cleanup;
- production, customer, or live external-system access not expressly included
  in the package's approved validation boundary;
- weakening tenant isolation, authorization, evidence, audit, append-only,
  replay, rollback, or canonical-write controls;
- deleting immutable or durable evidence merely for cleanup;
- a schema, migration, RLS, grant, Supabase, or database-object change unless it
  is demonstrably necessary for the package's catalog outcome and the Owner
  explicitly approves the exact database scope before mutation;
- release milestones, release tags, or major-version declarations such as
  v1.3.0 or v2.0;
- merging a work package without Program G review and explicit merge approval.

## Stop Rules

Engineering stops and returns to the Owner when:

- a required dependency is incomplete;
- a governing ADR is missing, unresolved, or conflicts with implementation;
- the package requires an excluded or materially broader capability;
- a Data Fabric or database change lacks exact prior authorization;
- tenant isolation, source authority, or canonical ownership cannot be proven;
- safe rollback, compatibility, or evidence preservation cannot be demonstrated;
- mandatory CI, regression, security, or post-merge validation fails.

A stop does not revoke this directive for other eligible work; it blocks the
affected package until disposition.

## Effect on Existing Governance Artifacts

- WP-001 through WP-004 remain closed under their original governance records.
- The merged WP-005 Activation Specification remains historical evidence and
  useful execution guidance, but its individual Activation Record is no longer
  required for engineering authorization.
- The unmerged WP-005 Activation Record and WP-006 readiness assessment may be
  closed without merge as superseded procedural artifacts once this directive
  becomes effective.
- Implementation evidence, Program G review, merge approval, post-merge
  validation, and closure remain mandatory for every package.

## Immediate Portfolio Effect

After this directive is merged and validated:

```text
WP-001–WP-004: CLOSED

WP-005:
STANDING ENGINEERING AUTHORITY
ELIGIBLE TO BEGIN ON A DEDICATED FEATURE BRANCH

WP-006:
ENGINEERING AUTHORIZED BY OWNER AMENDMENT AND ADR-024
MERGE AND RELEASE BLOCKED BY WP-005 RELEASE VALIDATION AND CLOSURE

WP-007–WP-020:
AUTHORIZED BY STANDING DIRECTIVE
INACTIVE UNTIL THEIR CATALOG DEPENDENCIES ARE SATISFIED
```

## Signature

```text
Srikanth Mudaliar
Owner
Chief Architect
Program Sponsor

Decision: APPROVED
Date: 2026-07-20
```

This is the final governance-process refinement for the v1.x development
stream unless the Owner issues a later superseding directive.
