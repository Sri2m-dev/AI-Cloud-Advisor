# CMP-P6-SC-002 - V1 Required Contract Closure

**Status: BLOCKED_V1_REQUIRED_CONTRACT**

## Count correction

SC-001 reported nine required objects, but its disposition table and current
contract contain eight. The exact unresolved matrix does not contain
`approval_audit`; it must not be added merely to repair the count.

The eight actual `V1_REQUIRED` objects are:

- `application_registry`
- `application_spend_mapping`
- `approval_history`
- `approval_requests`
- `mart_application_spend`
- `mart_enterprise_spend`
- `mart_enterprise_spend_v2`
- `technology_inventory`

The count discrepancy is itself recorded as a contract blocker.

## Resolution analysis

| Object | Resolution | Result |
| --- | --- | --- |
| `application_registry` | C candidate | Current consumers read incompatible field sets, but no proven primary key, tenant key, write contract, or canonical projection mapping exists. No DDL added. |
| `application_spend_mapping` | C candidate | Current code inserts and reads only name pairs; key, tenant scope, uniqueness, and authority are not proven. No DDL added. |
| `approval_history` | C candidate | Current code writes stage events and reads by request ID, but `approval_audit` is a different object and does not establish this table's contract. No projection added. |
| `approval_requests` | C candidate | Current code reads and updates workflow/SLA fields directly; no complete persistent contract or tenant key is established. No DDL added. |
| `mart_application_spend` | B candidate | Current consumers use `SELECT *`; no stable output contract or canonical P1/P2 mapping is proven. No projection added. |
| `mart_enterprise_spend` | B candidate | Existing financial services expose canonical posture, but the legacy row shape and all callers are not equivalent. No projection added. |
| `mart_enterprise_spend_v2` | B candidate | Current dashboards and tests depend on a legacy shape, while canonical financial posture exposes different semantics. No projection added. |
| `technology_inventory` | B candidate | Connector code performs durable upserts, while Enterprise Registry/Data Fabric own canonical identity. A read-only projection cannot satisfy current connector writes without a proven write adapter. No DDL added. |

No object reached a valid A or B resolution. No C object reached sufficient
E1-E4 evidence for minimum authoritative DDL. All proposed shortcuts would
require speculative keys, columns, tenant semantics, or financial mappings.

This is no longer a historical-recovery blocker. It is a concrete current-code
incompatibility:

- application and technology paths still perform direct legacy-table reads and
  writes, including connector upserts to `technology_inventory`;
- application and approval paths require persistent mutation contracts that the
  current in-memory/canonical services do not expose as equivalent adapters;
- financial pages and repositories consume global `SELECT *` mart rows, while
  the canonical P1 service exposes typed tenant-scoped posture/RPC results with
  different semantics;
- no current service wiring proves a lossless mapping from those legacy result
  shapes to Enterprise Registry, Data Fabric, P1, P2, or governance objects.

Changing these callers without first defining those adapters would be a
behavioral redesign, not bounded dependency removal. Therefore SC-002 has a
new, concrete product contract blocker rather than merely preserving unknown
historical schemas.

## Canonical authority result

- Enterprise Registry/Data Fabric: canonical enterprise identity and
  relationships exist, but current application/technology callers still use
  direct public table contracts that are not shape-compatible.
- P1 financial authority: canonical financial posture exists, but the legacy
  mart consumers require undocumented `SELECT *` row shapes.
- P2 optimization authority: no proven mapping exists for the legacy mart
  output contracts.
- Governance/approval: current approval repository uses `approval_requests`
  and `approval_history`; `approval_audit` is not a substitute.
- SourceFacts: authoritative observations exist, but they do not define the
  missing public compatibility objects or their write behavior.

## Optional and legacy objects

The 19 optional objects remain excluded from the v1 bootstrap and are not
staging blockers unless a required path is later proven to depend on them. The
six legacy-unreachable objects remain excluded and no DDL was created for them.

## Database execution status

SC-002 did not change migration files or bootstrap DDL. The SC-001 local
PostgreSQL 18 evidence remains valid:

- fresh bootstrap: PASS
- 17 dated public migrations: PASS
- Data Fabric 0001-0023: PASS
- 0020 valid and invalid transition behavior: PASS
- schema-only snapshot: PASS, zero COPY and INSERT

No new replay was needed because no database execution artifact changed in
SC-002.

## Tests and checks

- SC-001 contract coverage after count correction: **3 passed**
- Full repository baseline: **1862 passed, 2 skipped, 0 failures**
- Migration chain evidence retained from SC-001
- No application consumer changes were made
- No new public DDL was added
- External systems: none
- `git diff --check`: required final worktree check remains clean apart from
  the existing line-ending warning

## Decision

**BLOCKED_V1_REQUIRED_CONTRACT**

Concrete blockers only:

1. SC-001's required-object count is inconsistent; the source disposition has
   eight required objects, not nine.
2. All eight required objects still lack a non-speculative A/B/C resolution:
   application/approval contracts lack complete keys and tenant semantics;
   technology has write requirements that a read-only projection cannot satisfy;
   financial marts have undocumented `SELECT *` result contracts and no proven
   canonical mapping.

The correct next step is an explicitly authorized contract decision for these
specific eight paths, not another archaeology or migration checkpoint. The
final implementation pass confirmed the concrete missing piece is runtime
adapter wiring and complete tenant-aware contracts, not permission to add
legacy-shaped tables. No consumer was changed because no lossless adapter was
available for the current direct writes and `SELECT *` financial reads.

No staging project was created. No commit or push was performed.
