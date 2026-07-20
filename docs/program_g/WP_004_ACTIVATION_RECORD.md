# WP-004 Activation Record

## 1. Header

| Field | Value |
|---|---|
| Work Package ID | WP-004 |
| Exact title | Connector evidence certification |
| Record version | 1.0 |
| Record date | 2026-07-20 |
| Status | **READY FOR OWNER APPROVAL** |

This is an authorization record. It does not activate WP-004 unless the Owner
Approval section is completed through governance and the approved record is
merged into `main`.

## 2. Baseline

| Field | Value |
|---|---|
| Current `main` commit | `42b45c531bb23c45005c21a89e2b6381f3f4eb41` |
| Released baseline | `v1.2.0-data-fabric` |
| Program G planning catalog | Ratified and version controlled |
| WP-001 | Closed |
| WP-002 | Closed |
| WP-003 | Closed |
| WP-004 | Ready, not active |
| WP-005–WP-020 | Inactive |

## 3. Dependency verification

| Dependency | Evidence | Result |
|---|---|---|
| G1 — Architecture Ratification | Ratified architecture baseline and Program G catalog metadata | Complete |
| G2 — v1.2.0 Release Governance | Released `v1.2.0-data-fabric` baseline | Complete |
| G3 — Delivery Authorization | Program G work-package governance established | Complete |
| WP-001 | Release baseline and compatibility harness merged and closed | Complete |
| WP-002 | Tenant identity and authorization foundation merged and closed | Complete |
| WP-003 | Contract and event governance toolkit merged and closed | Complete |

No catalog dependency remains unresolved.

## 4. Definition of Ready

The authoritative readiness criteria are in
`docs/program_g/WP_004_ACTIVATION_SPECIFICATION.md`, Section 8.

| Mandatory criterion | Result |
|---|---|
| Ratified catalog entry, exact title, and Increment 1 placement | Satisfied |
| WP-002 and WP-003 closure | Satisfied |
| Current baseline and released foundation | Satisfied |
| Existing connector framework inventory | Satisfied |
| Architecture and compatibility constraints | Satisfied |
| Authorized and prohibited repository areas | Satisfied |
| Test and evidence strategy | Satisfied |
| AWS and Microsoft 365 lighthouse scope | Satisfied |
| Certification-only logical tombstone | Satisfied |
| Opaque cursor and post-reconciliation checkpoint rules | Satisfied |
| Additive WP-003 certification manifest | Satisfied |
| Live-source prohibition | Satisfied |
| Repository allowlist | Satisfied |
| Approved implementation branch name | Satisfied |
| Activation specification reviewed, merged, and post-merge validated | Satisfied at `42b45c531bb23c45005c21a89e2b6381f3f4eb41` |
| Explicit implementation activation | Pending this record's owner disposition |

**Readiness verdict:** all prerequisites for owner disposition are satisfied.
WP-004 remains not active until this record receives an Owner Approval and the
approved record is merged into `main`.

## 5. Owner decisions

The owner decisions are incorporated by reference without restatement or
modification from
`docs/program_g/WP_004_ACTIVATION_SPECIFICATION.md`, **Owner decision record**:

- decisions 1–6 define the lighthouse scope, logical tombstone, pagination and
  checkpoint rules, additive WP-003 profile, live-source prohibition, and
  approved implementation branch;
- decision 7 restricts repository modifications to the approved allowlist and
  prohibits scope expansion without a separate owner decision.

Those recorded decisions are indivisible conditions of any activation.

## 6. Approved scope

The scope is incorporated by reference from:

- `docs/program_g/NEXORA_WORK_PACKAGE_CATALOG.md`, row `WP-004`;
- `docs/program_g/WP_004_ACTIVATION_SPECIFICATION.md`, Sections 2, 3, 5, 6,
  and 7.

This record does not redefine or enlarge that scope.

## 7. Explicit exclusions

All exclusions in
`docs/program_g/WP_004_ACTIVATION_SPECIFICATION.md`, Section 4, are mandatory.
Any excluded-area change stops implementation and returns WP-004 to governance.

## 8. Approved implementation branch

The approved branch name is:

```text
feature/wp-004-connector-evidence-certification
```

> Branch shall not be created until this activation record is approved and
> merged.

Branch approval does not permit work outside the activation specification.

## 9. Required validation

WP-004 implementation and closure require all of the following:

- focused WP-004 tests;
- replay tests;
- duplicate tests;
- pagination tests;
- checkpoint tests;
- deletion/tombstone tests;
- reconciliation tests;
- tenant-isolation and secret-redaction negative tests;
- WP-001 compatibility harness;
- WP-002 authorization regression;
- WP-003 contract/event governance regression;
- full collection and regression suite;
- P3 non-secret gate;
- Ruff and active-source compile/import checks;
- `pip check`;
- secret-free gated integration collection and expected skips;
- hosted CI on the final review and merge commits;
- hosted CD on the exact merge commit;
- clean and synchronized post-merge `main` validation.

Live-source, Supabase, database, customer-environment, cloud-account, and
Microsoft 365 tenant testing remains prohibited.

## 10. Evidence required

The evidence package must reference and retain:

- `docs/program_g/WP_004_IMPLEMENTATION_EVIDENCE.md`;
- exact baseline, branch, commits, approvers, and decisions;
- changed-file inventory and allowlist review;
- architecture and ADR conformance;
- explicit exclusion verification;
- focused, negative, compatibility, regression, P3, and integration-gating
  results with exact totals;
- replay, duplicate, pagination, checkpoint, tombstone, reconciliation, tenant,
  and secret-safety evidence;
- dependency, compile/import, Ruff, and `pip check` results;
- hosted CI and CD run IDs and conclusions;
- merge commit and post-merge validation;
- exceptions, remediation, retained debt, and closure decision.

## 11. Activation decision

### Owner Approval

```text
Status:
ACTIVE

Authority:

Date:

Approved Branch:

Comments:
```

### Owner Rejection

```text
Status:
NOT ACTIVE

Reason:

Next Action:
```

These sections are intentionally unsigned and unfilled. Neither section may be
completed by an implementation agent without an explicit owner disposition.

## 12. Governance traceability

| Governance layer | Authoritative evidence |
|---|---|
| Program G planning | `docs/program_g/NEXORA_WORK_PACKAGE_CATALOG.md` |
| Execution contract | `docs/program_g/WP_004_ACTIVATION_SPECIFICATION.md` |
| Governing architecture | ADR-007, ADR-008, ADR-013, and ADR-014 as traced by the activation specification |
| Delivery governance | `docs/program_g/NEXORA_IMPLEMENTATION_GOVERNANCE.md` |
| Owner authorization | This record after signed owner disposition and merge |
| Implementation evidence | `docs/program_g/WP_004_IMPLEMENTATION_EVIDENCE.md` when authorized work is complete |
| Closure evidence | Program G review, merge, post-merge validation, and explicit closure decision |

## Current authority

This draft authorizes nothing automatically. Until an Owner Approval is
recorded and the approved record is merged into `main`:

```text
WP-004: READY, NOT ACTIVE
Engineering: BLOCKED
Implementation branch creation: BLOCKED
```
