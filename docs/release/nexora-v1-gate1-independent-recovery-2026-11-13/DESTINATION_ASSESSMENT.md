# Gate 1 Independent Recovery — Destination Assessment

Assessment date: 2026-11-13
Decision: **BLOCKED for the fixed Supabase project; local PG17 logical
compatibility is qualified, but no cloud restore is authorized or claimed.**

The fixed project below is nominated for this assessment, not authorized for
DDL, DML, restore, upload, or spending. This supersedes the earlier
“destination not selected” blocker only; it does not waive preservation or
execution controls.

**Implementation update:** the local contract has since been revised to use
the private `nexora_identity.memberships` mapping, and the PG17 recovery
package now exports and validates that mapping without relying on
`public.users`. The section below describing the pre-refactor package and
legacy identity dependency is historical baseline, not the current source
contract. The current implementation and test evidence are summarized in
[LOCAL_COMPATIBILITY_ENGINEERING_REPORT.md](./LOCAL_COMPATIBILITY_ENGINEERING_REPORT.md).
The fixed Supabase project's actual mapping/migration privileges, production
JWT contract, cost, authorization and measured recovery remain unverified;
Gate 1 remains **BLOCKED**.

## Exact-delta update — supplied live catalog findings

The following target facts were independently confirmed by read-only Supabase
catalog queries and supplied for the 2026-11-13 assessment. They are treated
as point-in-time evidence; this documentation task did not run another cloud
query:

| Catalog item | Supplied live finding |
|---|---|
| Server | PostgreSQL 17.11 |
| `pgcrypto` | Installed in schema `extensions` |
| `data_fabric` | Ten historical G07 tables |
| G07 table RLS | Enabled; FORCE RLS disabled; zero policies |
| `auth` | Supabase-managed schema present |
| `nexora_customer_workflow` | Absent |
| `public.users` | Absent |
| V1 owner/runtime roles | Absent |
| V1 workflow tables | Absent |
| Recorded migration | `20260904042847_enforce_relationship_timestamp_order` |

This confirms the V1 workflow delta is additive in namespace, but not yet
safe to apply. The canonical migration aborts without `public.users` and
contains public-schema identity policy/grant changes. It requests
`pgcrypto` in `public` but calls `public.hmac`; `pgcrypto` is reported in
`extensions`, so the required callable symbol and permissions are unresolved.
The existing application also resolves membership from `public.users` and
`public.organizations`, and the latter is not covered by the supplied
findings.

The detailed object inventory, identity choice, security assessment,
migration sequence and preservation plan are:
[EXACT_MIGRATION_DELTA.md](./EXACT_MIGRATION_DELTA.md),
[IDENTITY_CONTRACT_DECISION.md](./IDENTITY_CONTRACT_DECISION.md),
[SECURITY_IMPACT_ASSESSMENT.md](./SECURITY_IMPACT_ASSESSMENT.md),
[PROPOSED_MIGRATION_SEQUENCE.md](./PROPOSED_MIGRATION_SEQUENCE.md), and
[PRESERVATION_AND_ROLLBACK_PLAN.md](./PRESERVATION_AND_ROLLBACK_PLAN.md).
The recommended Option B identity mapping is not implemented or approved.

**Technical suitability:** PostgreSQL 17.11 and the existing project make it
a conditional candidate for a future isolated logical path, but the target is
not compatible with the unmodified V1 migration/recovery verifier. Required
identity adapter changes, JWT/HMAC resolution, allowed managed-role
operations, exact migration tracking, protected-object snapshots, cost and
separate write authorization remain open. **Gate 1 remains BLOCKED.**

## Baseline

The latest [engineering-freeze decision](../nexora-v1-engineering-freeze-2026-11-13/ENGINEERING_FREEZE_DECISION.md)
is GO only for the isolated synthetic customer workflow and frozen route
profile. It explicitly leaves production recovery, off-host recovery, and
owner-approved RPO/RTO unqualified. This assessment does not repeat the route
freeze and makes no off-host recovery claim.

The reusable [recovery package](../../../scripts/postgres_recovery_package.py)
passed local synthetic PostgreSQL 18 restore verification. It contains a
custom database dump, password-free global-role dump, ownership/ACL/RLS/
function/extension inventories, migration hashes, workflow/evidence
fingerprints, and coordinated `application/`, `evidence/`, and `prospect/`
files. It is capped at 1 GiB and 20,000 members. Package encryption and
integrity checks passed locally. The encrypted artifact was temporary and was
not retained; the package implementation is reusable, but no verified
artifact is presently available to transfer.

## Fixed destination and evidence reconciliation

| Item | Evidence | Assessment |
|---|---|---|
| Project | `nexora-p3-validation-restoration`, ref `uuqprdnqhbsmwubeqouw`, region `ap-southeast-2`; `ACTIVE_HEALTHY`, PostgreSQL 17.11 | Owner-designated for this assessment only. Preserve the existing project and all historical objects. |
| Current preflight | Owner reports no tables in `public` or `nexora_customer_workflow`, and one recorded migration: `20260904042847_enforce_relationship_timestamp_order`. | This does not establish that the database is empty; it is consistent with the older G07 `data_fabric` content. |
| Historical G07 restore | The 18 October record says source PostgreSQL 17.6 was physically restored into this exact project at PostgreSQL 17.11. It records ten `data_fabric` base tables, 235 relationship rows, RLS enabled, FORCE RLS false, and zero policies. | Product Owner accepted database-only coverage. This is not a restore of the V1 package and does not establish full app/Auth recovery, independent technical/security acceptance, or measured RTO. |
| Ownership/roles | The historical G07 catalog evidence reports `postgres` as the observed role and owner of the recorded Data Fabric objects; the role was non-superuser with `CREATEROLE` and `BYPASSRLS`. | Historical, not a current full role/membership inventory. Do not treat managed `postgres` as a superuser recovery administrator. |
| Extensions, dependencies, full schema inventory (earlier assessment baseline) | Not established by the earlier owner-provided facts or archived G07 summary. | The later exact-delta update below confirms `pgcrypto` in `extensions`; all other unreported extension/dependency details remain unverified. |

The current remote catalog could not be refreshed from this workstation. A
prior `supabase db query --linked` invocation using a temporary local project
reference and a `SELECT`-only version query failed before connecting:
`lookup db.uuqprdnqhbsmwubeqouw.supabase.co: no such host`; the CLI reported
IPv6 unavailable. No project link was created in the repository and no remote
SQL completed in that attempt.

For the final preflight, an executable catalog-only package is now prepared
at [SUPABASE_READONLY_PREFLIGHT.sql](./SUPABASE_READONLY_PREFLIGHT.sql). It
uses an explicit read-only transaction, bounded timeouts, catalog metadata
and migration identifiers only, and ends with `ROLLBACK`. It does not read
table row contents or secrets. It covers schemas/relations/columns, owners,
roles/memberships, grants, RLS policies, constraints, indexes, extensions,
triggers, function security metadata, dependencies, V1 workflow columns, and
a catalog-estimate preservation summary for `auth`, `data_fabric`,
`nexora_customer_workflow`, `public`, and `supabase_migrations`.

That prior workstation preflight did not execute a query: its environment had
no configured PostgreSQL connection or linked project reference, no `psql`
executable, and no supplied read-only credential. At 2026-11-13 06:01:04 UTC
the database hostname resolved to IPv6 `2406:da1c:4c7:f800::90f8`, which did
not establish a usable route or database authorization. The independently
supplied live findings in the exact-delta update above supersede the earlier
unknown status for the specifically reported items; they do not establish the
unreported full role/grant/dependency/Auth/G07 baseline. No historical
catalog evidence is treated as current beyond the findings explicitly
provided for this assessment.

## Package compatibility and restore safety

Direct restore with the existing package and `restore.sh` is a deterministic
NO-GO:

1. The qualified package source is PostgreSQL 18; the target is PostgreSQL
   17.11. `restore_backup_package` compares major versions and rejects this
   target before role/database restore steps. No cross-major test or conversion
   is claimed.
2. The package records all roles except names beginning `pg_`, including
   `postgres`, and restores global roles before creating a new database.
   `_restore_global_roles` rejects any captured role already present. The
   target is a Supabase project with the built-in `postgres` role; the package
   also rejects a recovery administrator whose name is in the captured roles.
   Historical target evidence says managed `postgres` is not a superuser.
   Full global-role/role-attribute restoration is therefore unsupported by
   this package on this target.
3. The restore is database-wide, not a schema-only merge. Restoring into the
   existing project database risks historical `data_fabric`, migration,
   Auth, managed Supabase objects, and existing ownership/ACL state. An empty
   `public` or workflow schema is not proof that the database is empty.
4. The exact encrypted artifact and its extension/dependency manifest are not
   retained, so extension availability, object-level collisions, and exact
   package contents cannot be compared against PostgreSQL 17.11.

Supabase documents its restore-to-new-project operation as a complete
database clone into a **new** project, not into this retained project. Its
logical dump path applies Supabase-specific filtering and reserved-role
handling, but it is a different artifact/restore contract from this qualified
package. Neither option authorizes overwriting this project's historical
objects or Auth data.

## PG17 logical recovery compatibility — local qualification

The separate allowlisted implementation
[postgres_v1_workflow_recovery.py](../../../scripts/postgres_v1_workflow_recovery.py)
was added without changing the existing PostgreSQL 18 full-recovery path.
It captures only the V1 workflow event stream, encrypted evidence objects,
an approval-state verification snapshot, and the actor/org/role mappings
needed for authorization. The entire logical archive is Fernet-encrypted and
authenticated. It excludes global roles, Auth internals, `public.users` row
data, `jwt_verification_settings.signing_secret`, migration history, and
historical `data_fabric` objects.

Restore requires a separately provisioned PostgreSQL 17 V1 schema and
identity profiles. It verifies the canonical migration hash, catalog shape,
owners, forced RLS, seven required policies, append-only/evidence triggers,
security-definer authorization functions, `pgcrypto`, and least-privilege
runtime grants. A read-only, non-superuser BYPASSRLS preflight credential
checks the exact V1 workflow tables are empty; a distinct
`nxr_customer_workflow_app` credential performs a single serializable
transaction. Each event and encrypted evidence row is replayed through that
runtime role with a target-signed synthetic JWT. Approval rows are regenerated
by the canonical event triggers and compared to the encrypted package
snapshot. A failed operation rolls back; a repeat restore refuses a
non-empty target. The restore command does not create or alter target roles,
schemas, Auth records, public profiles, migration history, or G07 objects.

The test ran from the existing PostgreSQL 18 synthetic source to a newly
created, uniquely named PostgreSQL 17.11 container using the locally available
image digest
`postgres@sha256:73bedc9eaa0121b92b9b26bb52e5141b3f6f37479c7ef913c0160455763ca80a`.
The disposable target contained Supabase-like managed roles, `auth.users`,
historical `data_fabric` data, a prior migration record, and Customer A/B
profiles. The test passed **1/1** with no failures. It exercised wrong backup
key and key IDs, truncated package, changed migration hash, missing RLS
policy, invalid runtime credentials, wrong target JWT secret, injected
mid-restore interruption with zero partial rows, duplicate recovery denial,
Customer A workflow/evidence/approval/export validation, Customer B denial,
and before/after preservation snapshots for roles/memberships, schemas,
owners/ACLs, Auth, G07, migrations, and profiles. The encrypted package did
not contain synthetic evidence plaintext. The temporary container was
removed after the test.

This is **local schema-isolation and PostgreSQL 17 compatibility evidence**,
not evidence that the actual Supabase project permits the same role mapping,
credentials, migration, extensions, Auth integration, network access, or
cost. The test uses service-level contexts and target-signed synthetic JWTs;
it is not a Supabase Auth or browser test. No cloud connection, DDL, DML,
upload, restore, or spend occurred. The encrypted artifact and test
credentials were temporary and were not retained.

## Decision and bounded alternative

The existing PostgreSQL 18 full-database package remains **NO-GO** for the
PG17 Supabase project because of major-version, global-role, and database-wide
restore incompatibilities. The separate PG17 logical path is **COMPATIBILITY
GO for the isolated local target only**. **Gate 1 remains BLOCKED**; no safe
or authorized cloud restore is established by this local result.

The fixed project still needs execution of the prepared read-only inventory,
confirmation that its `public.users` identity contract and required
PostgreSQL 17 roles/grants/extensions can be provisioned without affecting
Auth/G07 history, owner authorization for any required migration and the
synthetic restore, separately configured target Auth/application keys, and a
date-stamped all-in cost estimate within ₹1,000. The locally qualified
canonical migration
`database/contracts/v1_customer_workflow/001_customer_workflow_postgres.sql`
defines this expected target contract:

- Schema `nexora_customer_workflow`; tables `jwt_verification_settings`,
  `events`, `evidence_objects`, and `approvals`; extension `pgcrypto`.
- Roles `nxr_customer_workflow_owner` and
  `nxr_customer_workflow_runtime` with the migration's non-login,
  non-superuser, non-BYPASSRLS attributes and ownership/grants.
- Functions `require_evidence_object`, `verified_subject`, `verified_scope`,
  `enforce_event_contract`, and `reject_event_mutation`; triggers
  `enforce_customer_workflow_event`,
  `customer_workflow_events_no_update`, and
  `customer_workflow_evidence_no_update`.
- Seven policies: `customer_workflow_profile_self`,
  `customer_workflow_profile_scope_guard`, `events_runtime_scope`,
  `events_owner_scope`, `evidence_runtime_scope`, `approvals_runtime_read`,
  and `approvals_owner_scope`, including forced RLS for the three workflow
  data tables.
- The `public.users` identity/profile dependency and its policy/grant
  integration; the separately provisioned login role
  `nxr_customer_workflow_app` must receive only the approved runtime-role
  membership.

This is the locally qualified target contract, not a finding that any object
is absent remotely. The read-only inventory must determine the exact delta
before a migration is proposed. If the project lacks an object, applying the
canonical migration or separately provisioning a role/profile is a
write-bearing operation requiring exact owner authorization. In particular,
the migration changes policies/grants on `public.users`, so its effect on
existing identity authorization must be reviewed before approval. The logical
restore does not create schema, roles, extension, policies, or profiles. The
target must meet the qualified empty-workflow precondition before restore. If
any condition fails, stop and preserve the project unchanged. No cloud DDL/DML,
upload, restore, or spending is authorized by this assessment.

## Remaining qualification requirements for this fixed destination

Before any transfer or restore could be reconsidered, all of the following
must be established without altering the historical project:

1. A current, complete read-only inventory of every schema, relation, role,
   membership, owner, extension, migration, and cross-object dependency.
2. Verify the locally qualified PostgreSQL 17 logical contract against the
   fixed project's actual catalog, role mapping, grants, extensions, and
   allowed schema boundary; do not use the global-role full restore.
3. Verify target identity/profile and application configuration, and authorize
   the exact migration/restore operation; preserve existing Auth and G07 data.
4. A retained encrypted package, separately recoverable backup/workflow/
   evidence keys, and a separate storage target; source passwords and service
   keys are not in the package.
5. A separately configured synthetic Auth/application path with stable actor
   IDs, least-privilege runtime credentials, and verified tenant/RLS controls.
6. Exact incremental billable estimate, execution window, measurable RPO/RTO
   objectives, explicit restore authorization, evidence custody, and cleanup
   authority.

Until these controls are proven, preserve the project unchanged. **Gate 1
remains BLOCKED; no off-host recovery GO is claimed.**

## Sources

- [Local recovery qualification](../nexora-v1-customer-journey-2026-11-12/qualification.md)
- [Historical G07 recovery path and limitations](../../../deploy/staging/NXR-CLOSE-016/RECOVERY_PATH.md)
- [Historical G07 evidence inventory](../../../deploy/staging/NXR-CLOSE-016/evidence/G07/INVENTORY.md)
- [Independent recovery package instructions](../../../deploy/operations/independent-recovery/README.md)
- [Supabase restore to a new project](https://supabase.com/docs/guides/platform/clone-project) (read-only documentation review, 2026-11-13)
- [Supabase PostgreSQL roles](https://supabase.com/docs/guides/database/postgres/roles) (read-only documentation review, 2026-11-13)
- [Supabase platform-to-self-hosted logical restore](https://supabase.com/docs/guides/self-hosting/restore-from-platform) (filtered roles/schema/data dump; not the NEXORA package, read-only review, 2026-11-13)
- [PostgreSQL 18 pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html)

