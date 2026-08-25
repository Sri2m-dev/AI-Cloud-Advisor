# WP-005 Activation Record

## 1. Header

| Field | Value |
| --- | --- |
| Work Package ID | WP-005 |
| Exact title | Canonical coverage and stewardship |
| Record version | 1.0 |
| Record date | 2026-07-20 |
| Status | **READY, NOT ACTIVE** |
| Implementation authorization | **NO** |

This unsigned record verifies readiness against the merged WP-005 Activation
Specification. It does not authorize engineering or branch creation.

## 2. Baseline

| Field | Value |
| --- | --- |
| Current `main` commit | `7d972796ceac76629d7fb26477e2f0220dffe4ef` |
| Released foundation | `v1.2.0-data-fabric` |
| Program G catalog | Ratified and version controlled |
| WP-001 | Closed |
| WP-002 | Closed |
| WP-003 | Closed |
| WP-004 | Closed at `2db4d5a8d32635708797f9ffc96fafd2db001d43` |
| WP-005 | Ready, not active |
| WP-006–WP-020 | Inactive |

The WP-005 Activation Specification was merged by PR #14 at
`7d972796ceac76629d7fb26477e2f0220dffe4ef`. Hosted CI run `29716889565` and
hosted CD run `29716889568` passed on that exact commit.

## 3. Governing Documents

- `docs/program_g/NEXORA_WORK_PACKAGE_CATALOG.md`, row WP-005;
- `docs/program_g/WP_005_ACTIVATION_SPECIFICATION.md`;
- `docs/program_g/NEXORA_IMPLEMENTATION_GOVERNANCE.md`;
- ADR-008 through ADR-017 as traced by the Activation Specification;
- WP-001 through WP-004 compatibility, authorization, governance, and
  certification controls.

This record incorporates those controls without enlarging their scope.

## 4. Dependency Verification

| Dependency | Evidence | Result |
| --- | --- | --- |
| G1 architecture governance | Ratified architecture baseline | Complete |
| G2 release governance | Released `v1.2.0-data-fabric` | Complete |
| G3 delivery authorization | Program G governance and catalog | Complete |
| WP-002 | Tenant authorization foundation closed | Complete |
| WP-004 | Connector evidence certification merged, validated, and closed | Complete |
| Activation Specification | PR #14 merged; post-merge CI/CD passed | Complete |

Catalog dependencies are complete. Readiness evidence remains incomplete as
shown below.

## 5. Owner Decisions Incorporated

The Activation Specification records Srikanth Mudaliar's decisions for:

- Platform Owner, Domain Steward, Technical Steward, and automated-rule
  authority hierarchy;
- deterministic precedence and manual equal-authority conflict review;
- the auditable stewardship lifecycle;
- Technology and Applications lighthouse domains;
- stewardship-only canonical promotion through an existing approved atomic
  boundary;
- durable, replayable queues with immutable audit history;
- per-domain freshness policies;
- authoritative-inventory coverage denominators;
- the exact repository allowlist; and
- reserved branch `feature/wp-005-enterprise-stewardship`.

The reserved branch must not be created while this record is unsigned or its
readiness verdict is blocked.

## 6. Remaining Readiness Confirmations

### 6.1 Domain Freshness Policies — Pending

No approved numeric policy was found for the WP-005 Technology and Applications
domains. The following must be populated and approved:

| Domain | Expected refresh interval | Warning threshold | Stale threshold | Escalation threshold and owner | Result |
| --- | --- | --- | --- | --- | --- |
| Technology | Pending | Pending | Pending | Pending | Not satisfied |
| Applications | Pending | Pending | Pending | Pending | Not satisfied |

The generic freshness calculations and quality rules already in the repository
do not constitute these domain-governance decisions.

### 6.2 Initial Source-Authority Entries — Pending

The suggested names “Enterprise Technology Inventory” and “Enterprise
Application Registry” were examples, not recorded owner assignments. The
initial matrix must identify actual governed sources and scope:

| Domain | Governed subject/attributes | Authoritative source | Domain Steward | Effective date | Result |
| --- | --- | --- | --- | --- | --- |
| Technology | Pending | Pending | Pending | Pending | Not satisfied |
| Applications | Pending | Pending | Pending | Pending | Not satisfied |

No source may become authoritative through inference from recency, connector
identity, record volume, or this document.

### 6.3 Durable Queue Persistence — Not Satisfied

Repository inspection found:

- `data_fabric.persistence.interfaces.IdempotencyRepository`, which is specific
  to durable idempotency and is not a stewardship queue repository;
- Data Fabric current-state and immutable evidence repositories, none of which
  define the approved WP-005 review-item and transition lifecycle;
- legacy application queue repositories/services outside the WP-005 allowlist;
  these do not provide the approved WP-002 tenant-scoped, replayable,
  immutable-audit stewardship contract;
- `repositories.dashboard_repository`, whose approval queue is documented as a
  global governance snapshot and therefore cannot satisfy WP-005 isolation.

**Verdict:** the existing persistence surface has not been proven sufficient.
The approved specification prohibits treating an in-memory queue as complete
and does not authorize a schema, migration, Data Fabric, Supabase, RLS, grant,
or database-object change.

Required disposition before activation:

1. identify an existing approved durable abstraction and demonstrate every
   required lifecycle, replay, audit, revision, and tenant-isolation property;
   or
2. return to Owner governance for a narrowly scoped specification amendment
   authorizing the required persistence work.

Codex must not select or create durable storage under this unsigned record.

## 7. Definition of Ready

| Mandatory criterion | Result |
| --- | --- |
| Catalog entry and Increment 1 placement | Satisfied |
| WP-002 and WP-004 closed | Satisfied |
| Baseline and released foundation | Satisfied |
| Architecture constraints and exclusions | Satisfied |
| Technology and Applications lighthouse scope | Satisfied |
| Governance authority and workflow lifecycle | Satisfied |
| Exact repository allowlist | Satisfied |
| Test and evidence strategy | Satisfied |
| Reserved implementation branch | Satisfied, not creatable |
| Domain freshness intervals and thresholds | **Not satisfied** |
| Initial source-authority entries | **Not satisfied** |
| Approved durable queue persistence without excluded changes | **Not satisfied** |
| Explicit Owner Activation | **Not recorded** |

**Readiness verdict: BLOCKED.** WP-005 remains READY, NOT ACTIVE. Engineering
and implementation-branch creation remain prohibited.

## 8. Scope and Exclusions

The approved scope, allowlist, exclusions, stop conditions, acceptance criteria,
and test/evidence requirements are incorporated from
`WP_005_ACTIVATION_SPECIFICATION.md`. This record does not redefine them.

In particular, no Data Fabric contract, existing persistence adapter, schema,
migration, Supabase configuration, runtime connector, API, UI, graph, AI, or CI
change is authorized.

## 9. Required Validation After Future Activation

If readiness is later satisfied and the Owner activates WP-005, implementation
and closure must include:

- authority lookup, conflict, precedence, and effective-time tests;
- identity and quality queue durability, replay, audit, revision, and isolation
  tests;
- steward role, lifecycle, rejection, and invalid-transition tests;
- deterministic coverage denominator and drill-down reconciliation;
- domain freshness boundary, missing timestamp, stale, and escalation tests;
- WP-001 compatibility, WP-002 authorization, WP-003 governance, and WP-004
  certification gates;
- full collection and regression suite;
- P3 94-test non-secret gate;
- five gated integrations and five expected secret-free skips;
- `pip check`, Ruff, active-source compile/import, hosted CI/CD, clean synchronized
  `main`, implementation evidence, and explicit closure.

No live customer, cloud, Microsoft 365, Supabase, or database validation is
authorized by this record.

## 10. Activation Decision

### Owner Approval — Unsigned

```text
Authority:
Srikanth Mudaliar
Owner of Nexora

Decision:

Status:

Implementation Authorization:

Approval Date:

Implementation Baseline:

Approved Branch:
feature/wp-005-enterprise-stewardship

Conditions / Exceptions:
```

An approval is invalid unless Sections 6 and 7 are complete or a separately
approved governance amendment explicitly dispositions each blocker.

### Owner Rejection — Unsigned

```text
Decision:

Reason:

Required Remediation:

Action Owner:

Due Date:
```

## 11. Current Authority

```text
WP-001: CLOSED
WP-002: CLOSED
WP-003: CLOSED
WP-004: CLOSED

WP-005: READY, NOT ACTIVE
Readiness: BLOCKED
Engineering: NOT AUTHORIZED
Implementation branch: NOT CREATED

WP-006–WP-020: INACTIVE
```

Merging this unsigned documentation record, if approved for accuracy, does not
change that state.
