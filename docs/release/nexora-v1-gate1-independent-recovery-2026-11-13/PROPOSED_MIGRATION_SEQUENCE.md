# Gate 1 — Proposed V1 Migration Sequence

Status: **Review plan only; not executable or authorized.**
Target: fixed Supabase restoration project `uuqprdnqhbsmwubeqouw`.
Existing PG18 full-recovery implementation remains unchanged. PG17 logical
recovery remains separate and opt-in.

## Local implementation update

The local portion of steps 0, 3, 5–7 and 10 is now implemented and tested:
the versioned SQL contract uses `nexora_identity.memberships`, exact
extension-schema HMAC resolution, forced RLS, scoped policies, and a
production-disabled/synthetic-only JWT verifier. The PG17 recovery tool now
checks identity mappings and the exact installed `pgcrypto` function/grants.
The relevant local/auth/tenant suite completed **80 passed, 0 failed,
0 skipped**.

No Supabase DDL, role change, grant, identity provisioning, package upload or
restore is authorized. Steps 1–2 and 8–11 remain blocked on current
read-only catalog/privilege evidence, production JWT design, owner/security
approval, preserved snapshots, accepted RPO/RTO, verified budget and a
separate one-time recovery authorization. The pre-implementation text below
describes the planning baseline; it is superseded for local source behavior
by [LOCAL_COMPATIBILITY_ENGINEERING_REPORT.md](./LOCAL_COMPATIBILITY_ENGINEERING_REPORT.md).

## Design boundary

Do not run the current canonical migration unchanged. It requires absent
`public.users`, changes policies/grants in `public`, assumes extension
placement in `public`, and calls `public.hmac`. Recommended design is the
private application identity mapping in
[IDENTITY_CONTRACT_DECISION.md](./IDENTITY_CONTRACT_DECISION.md). The SQL
below is a sequence and review checklist, not executable SQL. Exact DDL must
be generated and reviewed only after the identity/JWT bridge, HMAC symbol,
managed role capability and migration ledger are resolved.

## Proposed ordered steps

| # | Preconditions / proposed action | Affected objects | Required privilege | Security impact / validation | Approval required |
|---|---|---|---|---|---|
| 0 | Fix and approve a versioned identity/JWT design; revise canonical migration, provisioner, auth adapter and recovery verifier locally; test on disposable PG17 matching extension placement and Supabase role semantics. | Local code and proposed V1 contract only | None on target | No target change. Compile/test exact claims, roles, RLS, key rotation, event/approval integrity, exports and A/B isolation. | Product, database and security owners approve design before target DDL is prepared. |
| 1 | Verify exact project/version and capture approved pre-change preservation snapshots. Verify database identity, all proposed names absent or compatible, all dependencies/grants and the existing migration version. | Existing schemas, `auth`, `data_fabric`, migrations, roles, extensions; read-only only | Authorized read-only catalog access; narrowly scoped historical fingerprints if approved | Any missing baseline or mismatch is a stop. Never interpret empty `public` as an empty database. | Database/recovery owner approves snapshot scope and custody. |
| 2 | Confirm actual `pgcrypto` extension schema, HMAC overload and execute permissions; confirm current migration principal capabilities without exposing secrets. | `extensions`, function ACLs, database/schema privileges | Read-only metadata inspection | No extension relocation. If the required function cannot be resolved through a safe, fixed qualified path, stop and revise the migration locally. | Database owner and security reviewer. |
| 3 | Prepare identity mapping schema contract. Option B: application-owned private namespace; mapping keyed by Auth UUID and organization UUID with constrained role and active status; no Auth passwords/tokens or writes into `auth`. | New private identity schema/table; no existing Auth/G07 objects | Dedicated approved schema owner/migration principal; DDL only to new namespace | Backend verifies Auth via supported API, obtains membership from private mapping, binds claims to subject and tenant. RLS, least-privilege resolver and no client role authority required. | Product, identity and security owner explicitly approve membership source and lifecycle. |
| 4 | Create required V1 group roles only if current metadata and platform permission allow; verify flags before ownership assignment. Do not change Supabase-managed roles. | `nxr_customer_workflow_owner`, `nxr_customer_workflow_runtime` | Exact role-admin capability permitted by Supabase; no assumed superuser | Both NOLOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOBYPASSRLS. No runtime membership in owner. Stop if platform refuses exact flags or authority is insufficient. | Database owner approves named roles and operator. |
| 5 | Create only the approved new V1 schema, versioned tables, constraints and indexes after asserting target names are free. Use the revised identity mapping; do not create `public.users` or use `auth.*`. | Private identity mapping and `nexora_customer_workflow` schema; four canonical tables | DDL/migration principal; schema owner role | Validate exact column types/order, tenant equality, event type/state checks, idempotency/composite keys, event/evidence/approval FKs, deferred last-event FK, and three canonical indexes. No pre-existing relation may be silently adopted by `IF NOT EXISTS`. | Separate written migration authorization naming exact project and migration hash. |
| 6 | Install fixed-search-path functions and triggers from reviewed revised contract; remove references to unresolved `public.hmac` or prove exact symbol. | Five workflow functions; four event/evidence triggers, including `customer_workflow_evidence_object_required` as a deferred constraint trigger | Owner of new V1 schema and functions | Verify object definitions and owner; append-only event/evidence, deferred evidence requirement, grounded Ask/decision, Finance→CIO→CEO sequence, actor and export linkage, constant-time signature comparison, no search-path injection. | Security/database owners sign reviewed SQL hash. |
| 7 | Enable and force RLS on the three workflow data tables; install the seven semantic policies against private membership mapping; set least-privilege grants. | V1 data tables, identity mapping table, V1 policies and ACLs | Owner of new objects; GRANT privileges limited to new objects | Runtime cannot update/delete/truncate events/evidence or mutate approval state directly; cannot read JWT secret or assume owner. No grants to PUBLIC/anon/authenticated/service_role unless separately proven essential and approved. Customer B denial required. | Security owner approves policies/ACL matrix. |
| 8 | Configure signing/verification settings from approved key custody using an atomic secret provision step; separately create/verify login role and its single runtime-role membership. | Secret settings row and `nxr_customer_workflow_app` login | Restricted secret provisioner and role-admin capability | Secret bytes never enter SQL files, arguments or logs. Verify role no SUPERUSER/CREATEDB/CREATEROLE/BYPASSRLS; key IDs/rotation and issuer/audience match the approved verifier. | Security/key custodians and database owner. |
| 9 | Record version and digest in the provider-approved migration ledger without changing the existing `20260904042847_enforce_relationship_timestamp_order` record. | New V1 migration-history entry only | Approved migration mechanism | Compare pre/post ledger and migration hash; reject duplicate version with different hash. Existing provisioner does not currently register this migration. | Database owner approves ledger mechanism and identifier. |
| 10 | Run read-only post-migration validation; no workflow rows or recovery are inserted. | All new V1 objects and snapshots of protected objects | Read-only catalog role with no BYPASSRLS if catalog grants suffice; protected snapshot reader for historical fingerprints | Check exact objects, owners, grants, policy/trigger/function hashes, extension resolution, RLS/forced flags, Auth/G07/migration/role preservation, and an empty workflow target. | Independent reviewer signs sanitized evidence. |
| 11 | Only after all prior validations, separately review and authorize synthetic PG17 logical recovery, keys, application/Auth endpoint, app credentials, cost, retention and measured RPO/RTO plan. | Synthetic rows in V1 workflow tables only | Runtime role for transactional restore; separate read-only BYPASSRLS preflight credential only if unavoidable and approved | Recovery tool must be updated for identity option B and exact migration hash. Validate encrypted evidence, approvals, exports, actor mappings, Customer A/B, and no Auth/G07 change. | Separate explicit one-time restore authorization; this plan grants none. |

## Required read-only post-migration assertions

Before any recovery, independently verify:

- PostgreSQL major 17; schema/function references resolve to the intended
  `pgcrypto` installation, with no change to the extension itself.
- Exact table columns, types, nullability, constraints, indexes and expected
  row emptiness; no unexpected object is accepted through `IF NOT EXISTS`.
- Exact owner/runtime/application role flags and memberships; no role has
  `BYPASSRLS` except an explicitly approved short-lived read-only preflight
  role, and no `service_role`/`anon`/`authenticated` grant was added.
- Forced RLS is on for `events`, `evidence_objects`, and `approvals`; all
  reviewed policies are present with expected command, roles, USING and
  WITH CHECK expressions.
- Function owner, `SECURITY DEFINER`, fixed search path, definition hash and
  execute ACL; exact trigger definitions and enablement.
- The target event/evidence/approval tables are empty; identity mappings are
  only synthetic and explicitly authorized.
- Protected-snapshot comparison proves Auth, G07, old migration, existing
  roles/memberships/grants and extensions were not changed.

## Proposed SQL status

No cloud SQL is included as an executable copy. The checked-in migration is
not an exact safe proposal for this target and must not be run unchanged. Once
Option B and the JWT/extension resolution are accepted, a new migration
artifact should be reviewed as a whole, have a unique version and SHA-256,
contain explicit collision/shape checks, operate only on new application
objects, and be tested transactionally against PG17 before separate
authorization. No target migration is authorized now.

## Stop conditions and rollback limits

Stop on missing permissions, unknown object collisions, changed protected
snapshot, unresolved extension symbol, unsupported JWT algorithm/rotation,
identity mismatch, RLS/policy discrepancy, failed rollback test, cost above
₹1,000 or absent written authorization. Do not retry on a partially populated
target without forensic review.

## Recovery readiness conditions remain open

The separate PG17 logical package remains opt-in; its schema verifier and
profile export currently require `public.users` and the seven legacy policy
locations. Option B therefore requires a versioned recovery-tool contract
change and local regression before use. The PG18 full-recovery implementation
is unchanged and is not suitable for this PG17 target.

Before any independently authorized synthetic restore, all of the following
must be re-proven:

- The encrypted package contains workflow events, ciphertext evidence,
  approval-state verification material and stable actor/org/role mappings;
  verify integrity and keys without exposing evidence plaintext or secrets.
- Finance/CIO/CEO approval events and evidence-linked export references
  survive restore; the approvers are distinct authorized identities.
- Customer A can recover its workspace and evidence; Customer B remains
  denied under JWT, membership mapping and forced RLS.
- Backup, workflow, evidence, target JWT/application key and recovery
  credential custody are separate, named and rehearsed; source/Auth and
  managed Supabase credentials are not embedded.
- Proposed RPO ≤24h and RTO ≤4h remain **unapproved and unmeasured**. Record
  backup start/completion, last committed transaction, failure, recovery
  initiation, database restore completion, application availability and
  customer validation; distinguish database duration from full-service RTO.
- Exact incremental compute, disk, application/Auth, transfer, storage,
  minimum billing, tax and settlement cost remains **unverified**. The all-in
  cap is ₹1,000, not spending authority.

No recovery drill, upload, key operation, restore or cost-incurring action is
authorized by this sequence.

Transactional DDL may roll back before commit if all statements and provider
operations are in one transaction. It cannot undo external side effects,
already committed migration steps, independent secret rotation, audit logs,
or provider-managed actions. Do not drop a schema or reverse historical
objects as a rollback. A failed operation requires freeze, evidence capture,
and explicit owner-led recovery.
