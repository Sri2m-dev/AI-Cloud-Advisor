# API Database Contract Closure — Implementation Report

**Result: PARTIAL CLASSIFICATION / V1 DATABASE CONTRACT NO-GO**

## Work performed

- Reconciled all 29 distinct missing literal-call objects in
  `docs/cmp/CMP-P6-DEF-001/schema_inventory.json` with the SC-001/SC-002
  contract evidence and the M0 route catalogue.
- Classified 2 objects V1 REQUIRED, 1 V1 SUPPORTING, 19 DEFERRED and 7
  UNKNOWN. The object-by-object register records callers, business function,
  journey relevance, contract evidence, reachability, security implications,
  proposed resolution, acceptance test and status.
- Confirmed that the five-table public baseline and the separate
  `v1_customer_workflow` contract do not define the legacy
  `approval_requests` / `approval_history` contracts used by
  `repositories/approval_repository.py`.
- Confirmed that the M0 catalogue is proposed; it explicitly says current
  navigation is broader and direct-route restriction is unfinished. No
  `NEXORA_PRODUCT_PROFILE`/V1 route gate was found in the prior targeted source
  review. Therefore deferred features cannot be claimed safely unreachable.
- Made no SQL, Python, route, migration or test-code changes. No guessed
  compatibility tables, permissive RPCs, synthetic return data or broad
  `SECURITY DEFINER` functions were added.

## Object disposition

| Classification | Count | Result |
|---|---:|---|
| V1 REQUIRED | 2 | `approval_history`, `approval_requests`; blocked on authoritative contracts |
| V1 SUPPORTING | 1 | `enterprise_data_fabric`; blocked on canonical Data Fabric authority decision |
| DEFERRED | 19 | No DDL added; route/job exclusion remains unenforced |
| UNKNOWN | 7 | Owner scope/contract decisions required; not treated as deferred |
| Resolved | 0 | No object reached an implementable, authoritative contract |

The old SC-001 matrix has eight unresolved V1_REQUIRED names. Only two overlap
the current 29. The other six—`application_registry`,
`application_spend_mapping`, `mart_application_spend`,
`mart_enterprise_spend`, `mart_enterprise_spend_v2`, and
`technology_inventory`—remain unresolved and are not made irrelevant by this
classification.

## Why implementation stopped before DDL

SC-001 and SC-002 explicitly state that approval keys, tenant semantics,
ownership, grants, RLS and lifecycle are incomplete. They also reject treating
`approval_audit` or the separate `nexora_v1_*` workflow schema as a substitute
for the legacy contracts. For `enterprise_data_fabric`, SC-001 forbids
duplicating canonical `data_fabric`, while the M0 route catalogue classifies
the page as controlled-supporting. Creating any of these definitions would
invent or conflict with an authoritative contract.

DEFERRED is a scope classification, not a successful exclusion. Several
deferred callers remain reachable because the current navigation and direct
routes are broader than the proposed catalogue. The owner must approve a
release allowlist before enforcement is introduced; the proposed catalogue
alone is not authorization to change product behavior.

## Validation evidence

- Targeted test run for this task: **65 passed, 0 failed, 0 skipped** in
  72.89 seconds. It covered current schema-contract checks, authentication and
  tenant-security tests, approval tests, and a fresh-cluster customer-workflow
  bootstrap/service test.
- The fresh-cluster test applied the existing 43 PostgreSQL migration inputs
  and exercised the namespaced synthetic customer workflow. It does **not**
  prove compatibility of the 29 legacy objects, the full FastAPI/Streamlit
  application, or browser access to the legacy approval page.
- No migration or application code changed in this closure; no new SQL replay
  or full browser journey was run.
- No cloud, Supabase or protected environment was accessed or modified.

## Decision

**V1 DATABASE CONTRACT: NO-GO.** Three required/supporting contracts remain
unresolved; seven objects remain unknown; and deferred routes are not
demonstrably inaccessible. The exact blockers and closure evidence are in
`REMAINING_BLOCKERS.md`.
