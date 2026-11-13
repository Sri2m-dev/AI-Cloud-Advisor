# Gate 1 Independent Recovery — Authorization Checklist

Status: **BLOCKED — the revised private identity contract and PG17 local
logical restore are implemented and tested. Production JWT/role/extension
compatibility, cost, owner authorization and off-host execution remain
unverified. No execution is authorized.** No cloud query, provisioning,
upload, restore, project write, or spend was performed for this update.

## Exact migration and identity assessment (2026-11-13)

The supplied live findings establish PostgreSQL 17.11, `pgcrypto` installed
under `extensions`, ten historical G07 `data_fabric` tables with RLS enabled,
FORCE RLS off and zero policies, Supabase-managed `auth` present, and
`nexora_customer_workflow`, `public.users`, V1 owner/runtime roles and V1
workflow tables absent. The only reported migration is
`20260904042847_enforce_relationship_timestamp_order`. These are point-in-time
read-only findings, not authorization.

The current canonical migration is not safe to run unchanged: it raises when
`public.users` is absent, changes policies/grants on that relation, requests
`pgcrypto` in `public`, and calls `public.hmac`, while the extension is
reported in `extensions`. Active Supabase JWT algorithm/key rotation,
`public.hmac` resolution, migration-principal role-creation ability,
`public.organizations`, and complete Auth/G07 grant/dependency snapshots are
not established.

See the five review artifacts:

- [EXACT_MIGRATION_DELTA.md](./EXACT_MIGRATION_DELTA.md)
- [IDENTITY_CONTRACT_DECISION.md](./IDENTITY_CONTRACT_DECISION.md)
- [SECURITY_IMPACT_ASSESSMENT.md](./SECURITY_IMPACT_ASSESSMENT.md)
- [PROPOSED_MIGRATION_SEQUENCE.md](./PROPOSED_MIGRATION_SEQUENCE.md)
- [PRESERVATION_AND_ROLLBACK_PLAN.md](./PRESERVATION_AND_ROLLBACK_PLAN.md)

Option B is now implemented locally: `nexora_identity.memberships` is
application-owned and separate from `public` and `auth`; Supabase Auth remains
the authentication authority. The implementation is synthetic/local-only
until the production JWT contract and managed-role compatibility are
established. See
[LOCAL_COMPATIBILITY_ENGINEERING_REPORT.md](./LOCAL_COMPATIBILITY_ENGINEERING_REPORT.md).

## Must be resolved before a run can be authorized

### Fixed project and isolation

- [x] Exact project nominated for this assessment: Supabase
  `nexora-p3-validation-restoration`, ref `uuqprdnqhbsmwubeqouw`, region
  `ap-southeast-2`, PostgreSQL 17.11.
- [x] Preserve the historical G07 project, `data_fabric` objects, migration
  history, Auth data/configuration, and evidence. No in-place restore/reset.
- [ ] Preserve the supplied partial read-only catalog findings as the current
  baseline. Do not repeat general discovery. Obtain only the additional
  read-only checks listed in
  [EXACT_MIGRATION_DELTA.md](./EXACT_MIGRATION_DELTA.md): exact `hmac`
  overload/schema/execute rights, migration principal capabilities,
  `public.organizations` metadata if still used, V1 migration-ledger
  mechanism, and non-secret Auth JWT algorithm/key/issuer/audience metadata.
  Complete protected-object snapshots are also required before any proposed
  write.
- [ ] Verify on the exact project that the V1 workflow schema boundary,
  required relations, and empty event/evidence/approval tables do not collide
  with or mutate historical data/Auth. The local test does not establish this
  remote catalog state.
- [ ] Prove current-project security controls (TLS/network/access logs) and
  a separately configured synthetic Auth/application path without changing
  historical identities.

### Data, identity, and key custody

- [ ] Identify the exact synthetic source and create an owner-authorized,
  retained encrypted package. The PG17 test artifact was ephemeral and is
  not available for cloud transfer.
- [x] A separate PG17 logical contract is implemented and passed local
  PostgreSQL 17.11 qualification; the existing PG18 full-recovery path is
  unchanged. This does not qualify the actual Supabase project's grants,
  role mapping, extensions, or Auth configuration.
- [ ] Verify target owner/runtime/preflight role mapping, grants, extension
  state, migration/catalog compatibility, and target identity profiles on the
  exact project. Do not restore global or managed roles.
- [ ] Backup key and key ID are independently retrievable.
- [ ] Workflow and evidence keys/key IDs are separately retrievable.
- [ ] Synthetic Auth identities, stable actor UUIDs, JWT issuer/signing secret,
  and fresh runtime credentials are available through named custodians; the
  PG17 package records no JWT secret and does not restore Auth service
  configuration. Target JWT signing material must be provided separately.
- [ ] Source passwords and service-role/API secrets are not embedded in the
  package, copied into the browser, or placed in evidence logs.
- [ ] Retention, deletion, and evidence-storage periods are approved.

### Objectives, budget, and operations

- [ ] Owner accepts or replaces proposed RPO ≤24 hours and RTO ≤4 hours.
- [ ] A date-stamped incremental estimate covers existing-project compute,
  database disk/storage growth, app/Auth, transfer, retention, minimums,
  taxes, FX/settlement, and cleanup.
- [ ] The quoted all-in maximum, including contingency, is ≤₹1,000.
- [ ] An evidence-based execution duration and run window, spend monitor,
  recovery operator, and key custodians are named.
- [ ] A write authorization separately covers the exact transfer and restore
  operation after these checks pass. The current instruction authorizes
  preparation/read-only assessment only.
- [ ] G08 remains disabled and fail-closed.

## Current evidence and blockers

- Local compatibility test: **1 passed, 0 failed** using a new PostgreSQL
  17.11 container and a PostgreSQL 18 synthetic source. It validated schema
  and migration checks, Supabase-like role/schema collisions, transaction
  rollback, repeat refusal, A/B isolation, exact event/export payload
  recovery, evidence decryption, and preservation snapshots. No browser,
  Supabase Auth, cloud, RPO/RTO, or off-host destination test was performed.
- Owner reports this fixed project is ACTIVE_HEALTHY, with no tables in
  `public` or `nexora_customer_workflow` and one migration record:
  `20260904042847_enforce_relationship_timestamp_order`.
- Historical G07 evidence for this exact project records a PG17.6-to-17.11
  physical restore, ten `data_fabric` tables, 235 relationship rows, RLS on,
  FORCE RLS off, zero policies, and a Product Owner database-only acceptance.
  It does not certify V1 recovery, Auth/app recovery, independent review, or
  measured RTO.
- The existing full package source is PG18; its restore rejects PG17.11 before
  modifying roles/database. Its `postgres` global-role capture is incompatible
  with managed-role restoration. The separate PG17 logical tool avoids that
  full-database/global-role path but is not yet remotely qualified.
- No approved encrypted artifact from this new logical path was retained; the
  local test artifact was temporary.
- Earlier workstation connectivity failures remain historical. The current
  target baseline above is based on the independently confirmed findings
  supplied for this assessment; this assistant did not repeat cloud queries.
  The full role/membership/grant inventory, exact extension symbol,
  `public.organizations`, function/dependency snapshots and complete
  Auth/G07 preservation baselines remain unverified.
- The older G07 UI estimate ($10.18/month) is for a different configuration,
  not the current project's marginal cost. Exact billing/tax/storage/transfer
  and application/Auth costs remain unverified.
- Proposed RPO/RTO values are not accepted or measured.

## Smallest owner decision

Provide the minimum **read-only, non-secret compatibility evidence** for the
active Auth JWT algorithm/key IDs/issuer/audience/rotation and the exact
Supabase migration principal's role/schema privileges. Option B is already
implemented locally and does not need another design-selection cycle. This
is not permission to migrate. Separate exact-project DDL and recovery
authorizations, accepted RPO/RTO and verified ≤₹1,000 cost are still
required. The PG18 full-package restore remains blocked for this destination.

## Latest local engineering result

The revised migration no longer requires, reads, changes or creates
`public.users`; it creates the private identity table and checks the
pre-existing `pgcrypto` HMAC symbol in its installed schema. The backend
authenticates through Supabase Auth, then resolves one active mapping through
the application database. Missing, revoked, ambiguous, workspace-mismatched
and cross-tenant mappings deny access. Production JWT provisioning is
fail-closed; only explicitly marked synthetic HS256 local/test configuration
is enabled.

The local regression command completed **80 passed, 0 failed, 0 skipped**,
including the isolated PostgreSQL 17.12 recovery target (the reported cloud
project is PostgreSQL 17.11), the workflow suite, Supabase
auth, API tenant authorization, token revocation and tenant-scoped access
tests. This replaces the earlier 1-test report as the latest local evidence.
It does not establish a Supabase migration privilege, JWT key/rotation
contract, retained encrypted artifact, all-in cost, accepted/measured RPO or
RTO, or off-host cloud recovery. Gate 1 remains **BLOCKED**.

