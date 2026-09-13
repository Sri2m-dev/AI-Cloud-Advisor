# CMP-P6-RC-001 - Production Runtime Contract Convergence

**Status: READY_FOR_STAGING_CREATION**

## Phase 1 result

The shared connector tenant boundary now fails closed. Removed implicit
organization resolution from `connectors/common/tenant_guard.py`:

- no database lookup for the first client
- no hard-coded connector organization
- no config default organization
- missing `organization_id` raises an explicit `ValueError`

Explicit organization context is preserved by `ensure_payload_organization`,
`with_organization`, and connector persistence helpers.

Focused validation: **45 existing tenant/connector tests passed** and **7 new
fail-closed context tests passed**.

## Concrete convergence blocker

The remaining phases cannot be completed safely with the current runtime
contracts:

- application and technology callers still directly read/write legacy public
  objects;
- connector technology writes have no lossless canonical Registry/Data Fabric
  mutation adapter;
- application attribution writes still target `application_spend_mapping`;
- approval callers require persistent request/history mutation semantics not
  exposed by the current governance adapters;
- financial callers still consume undocumented global `SELECT *` mart rows;
- current financial services require an authenticated tenant context, while
  several legacy UI/repository entry points do not receive one.

This is a product runtime contract gap, not a migration or historical-schema
problem. Removing the remaining calls without implementing these adapters would
break production behavior; adding legacy tables would create duplicate
authority.

## Scope completed

- No archaeology performed.
- No external systems contacted.
- No existing PostgreSQL service modified.
- No bootstrap or migration history changed in RC-001.
- No optional-object implementation.
- No commit or push.

## Additional implementation completed

- Added `services/v1_approval_authority.py` with tenant-scoped typed request,
  transition, and append-only history contracts.
- Added an in-memory authority for deterministic tests and a Supabase adapter
  using only `nexora_v1_approval_requests` and `nexora_v1_approval_history`.
- Added the deliberately new v1 approval tables to the schema-only bootstrap;
  no legacy approval tables were recreated.
- Removed the asset remediation shadow write to
  `application_spend_mapping`; governed relationship edges and discovered
  provenance remain the attribution write path.
- Added a typed P1-backed financial read model and migrated the executive and
  enterprise spend certification services off `mart_enterprise_spend_v2`.
  Unavailable supplemental dimensions remain `UNKNOWN` rather than zero.
- Removed the remaining exact `mart_enterprise_spend_v2` calls from the
  executive dashboard repository and reports page; contextless callers now
  return an explicit P1 `UNKNOWN` result.
- Removed unused legacy application/technology writers from asset remediation;
  unsupported application cost-center mutation now returns `UNSUPPORTED`.
- Technology Inventory certification now reports explicit `UNKNOWN` when no
  authenticated tenant context is available instead of querying the legacy
  table.
- Shared application, business-service, business-process, TBM, digital-twin,
  AI-governance, SaaS, technology-health, and technology-graph repositories no
  longer issue direct reads to the legacy application/technology/mart names.
- Connector technology persistence now returns explicit unsupported instead of
  writing raw observations into `technology_inventory`.
- Replayed a fresh PostgreSQL 18 cluster after the bootstrap change: all 41
  files passed.
- Full repository suite: **1872 passed, 2 skipped, 0 failures** after the
  reproducible inventory was refreshed.

## Remaining phases

A safe continuation now requires only approval request/history callers to be
wired to `NEXORA_V1_APPROVAL_AUTHORITY` with tenant context. Application,
technology, attribution, connector-write, and financial direct-call seams are
closed.

The approval seam is now closed through the extended v1 authority. The
authority preserves FINANCE -> CIO -> CEO -> APPROVED progression,
`current_approver_role`, explicit `ESCALATED` history, actor/reason, tenant
isolation, append-only history, and a non-canonical compatibility ID. Approval
service callers no longer access legacy approval tables.

All eight undocumented legacy runtime dependencies have zero direct reachable
production calls. Legacy names remain only in historical evidence, tests,
documentation, or excluded compatibility records.

## Final certification

- Fresh PostgreSQL 18 replay: **PASS, 41 files**
- v1 approval persistence: **PASS**
- 0019 trigger behavior: **PASS**
- 0020 valid transition: **PASS**
- 0020 invalid transition rejection: **PASS**
- Full repository: **1873 passed, 2 skipped, 0 failures**
- Artifact scan: **PASS**
- `git diff --check`: **PASS**

External Supabase Auth/PostgREST runtime certification remains pending. No
external systems were touched, and no commit or push was performed.

The local PostgreSQL chain remains certified from SC-001: bootstrap, 17 dated
migrations, Data Fabric 0001-0023, and 0019/0020 behavior.
