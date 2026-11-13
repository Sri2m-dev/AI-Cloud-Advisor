# Gate 1 Independent Recovery — Prepared Runbook

Status: **BLOCKED for Supabase execution; local PG17 compatibility passed**
Existing full-recovery implementation:
[independent recovery package](../../../deploy/operations/independent-recovery/README.md)
and [recovery verifier](../../../scripts/verify_customer_workflow_recovery.py).
Separate PG17 workflow-only implementation:
[postgres_v1_workflow_recovery.py](../../../scripts/postgres_v1_workflow_recovery.py).
No cloud operation or spend is authorized.

## Stop conditions

Do not begin until every item in
[Authorization Checklist](./AUTHORIZATION_CHECKLIST.md) is verified and
signed. In particular:

- The fixed project `nexora-p3-validation-restoration`
  (`uuqprdnqhbsmwubeqouw`) is a retained historical G07 project, not an empty
  target. Do not restore into it in place, reset it, or change its Auth/history.
- Do not create another project, upload an artifact, run DDL/DML or a restore,
  or spend funds under this assessment.
- Do not point an application at a target before database/package verification.
- Do not use real customer data or enable G08.

## Fixed destination compatibility decision

The current package is **not executable against this project**:

- The package was qualified on PostgreSQL 18; the project is PostgreSQL 17.11.
  `restore_backup_package` enforces equal major versions and rejects before
  role/database restore steps.
- The package captures the global role list (including `postgres`) and the
  restore helper fails on any role-name collision. Supabase already has a
  managed `postgres` role; the historical G07 catalog describes it as
  non-superuser. Full global-role restoration and the package's
  superuser-equivalent recovery contract are not supported here.
- The package restores a full database, while the fixed project contains
  retained G07 `data_fabric` history. Empty `public` and workflow schemas do
  not make the project empty.

Do not invoke the generic `restore.sh`, modify its version/role checks, or
attempt a schema-only workaround. The separate PG17 logical tool is qualified
only against a disposable local Supabase-like target. It is not yet qualified
for this project's current roles, grants, Auth integration, network, schema
inventory, or billing.

## Preflight

1. Identify the exact synthetic source instance and record its PostgreSQL major
   version, system identifier, database name, app/auth versions, and synthetic
   workflow IDs. Confirm no protected database or project is in the source
   configuration.
2. Read-only inspect the exact fixed project across every schema, relation,
   role, membership, owner, extension, migration, and dependency using
   [SUPABASE_READONLY_PREFLIGHT.sql](./SUPABASE_READONLY_PREFLIGHT.sql). This
   psql package runs in a read-only transaction, applies short statement and
   lock timeouts, selects catalog metadata and migration identifiers only,
   and rolls back. It does not read table row contents, secret values, or
   execute schema changes.

   No query was executed because no authorized read-only database credential,
   configured PostgreSQL connection, linked project reference, or `psql`
   executable was available. DNS resolved
   `db.uuqprdnqhbsmwubeqouw.supabase.co` to IPv6
   `2406:da1c:4c7:f800::90f8` at 2026-11-13 06:01:04 UTC; this is not proof of
   route availability. The earlier CLI attempt that failed DNS remains
   historical and did not produce catalog results. Do not infer the remaining
   catalog state.

   After an owner-authorized read-only connection is supplied, use a
   TLS-verified PostgreSQL service definition and a separate protected
   password file; never place credentials in the command, SQL file, or
   evidence. The command should be run from the repository root:

   ```powershell
   $env:PGSERVICEFILE = "<restricted pg_service.conf>"
   $env:PGPASSFILE = "<restricted pgpass file>"
   psql -X -w --set=ON_ERROR_STOP=1 --dbname "service=nexora-gate1-ro" --file "docs\release\nexora-v1-gate1-independent-recovery-2026-11-13\SUPABASE_READONLY_PREFLIGHT.sql"
   ```

   Preserve the sanitized result and connection time in restricted evidence.
   The command is a future read-only preflight template, not an instruction to
   connect or permission to write.
3. Before proposing any writes, verify the `nexora_customer_workflow` schema
   boundary and all current object dependencies. The logical restore does not
   create or migrate a schema and refuses non-empty V1 workflow tables. Stop
   if any object or dependency collides with Auth or historical G07 data.
4. The PG18 full-package contract remains incompatible. The separate PG17
   logical contract passed its local qualification; verify the exact
   target-side role mapping, grants, forced-RLS policies, functions, extension,
   and migration before considering a cloud run. The local contract is defined
   by `database/contracts/v1_customer_workflow/001_customer_workflow_postgres.sql`:
   it includes schema `nexora_customer_workflow`; tables
   `jwt_verification_settings`, `events`, `evidence_objects`, and `approvals`;
   `pgcrypto`; roles `nxr_customer_workflow_owner` and
   `nxr_customer_workflow_runtime`; functions `require_evidence_object`,
   `verified_subject`, `verified_scope`, `enforce_event_contract`, and
   `reject_event_mutation`; triggers `enforce_customer_workflow_event`,
   `customer_workflow_events_no_update`, and
   `customer_workflow_evidence_no_update`; and the seven policies
   `customer_workflow_profile_self`, `customer_workflow_profile_scope_guard`,
   `events_runtime_scope`, `events_owner_scope`, `evidence_runtime_scope`,
   `approvals_runtime_read`, and `approvals_owner_scope`. It also changes
   policies/grants on `public.users`, so existing identity authorization must
   be reviewed before any migration. Query results must identify which objects
   are missing or incompatible; do not assume the migration is absent, apply
   it speculatively, weaken package checks, or grant broad runtime privileges.
5. Confirm restricted network rules, TLS, storage encryption, destination
    access logging, and no unauthenticated/public database path. Check for
    extension jobs, triggers, or wrappers that could make external calls.
6. Confirm the encrypted backup key, workflow key, evidence key, key IDs,
   JWT issuer/signing configuration, fresh runtime DB credentials, and Auth
   setup are independently retrievable by named custodians. Do not put secret
   bytes in command arguments, logs, or evidence.
7. Measure package and restored-storage size, and confirm the exact marginal
   all-in cost including taxes is ≤₹1,000 with a run/cleanup window. Current
   billable compute and the old G07 estimate are insufficient.
8. Record the signed authorization, operator, UTC clock source, target
   resource identifiers, and evidence directory. Keep all existing projects
   and source data unchanged.

## Existing PostgreSQL 18 full-package path

The previous qualification's encrypted artifact was ephemeral and is not
retained. Reuse the qualified package implementation; do not rewrite it. If no
owner-approved synthetic source snapshot and package exists, create a new
synthetic capture only after authorization. This is not a repeat of the route
freeze or customer journey.

This existing command remains for the PostgreSQL 18 full-recovery contract
only. It is **not** compatible with the fixed PostgreSQL 17 project and must
not be used there. Coordinate its workflow/evidence filesystem snapshot with
a write fence and capture receipt; configure connection variables through
approved secret files, not shell history.

```sh
python -m scripts.postgres_recovery_package backup \
  --destination "$NEXORA_RECOVERY_PACKAGE" \
  --storage-root "$NEXORA_RECOVERY_STORAGE_SOURCE" \
  --key-file "$NEXORA_BACKUP_KEY_FILE" \
  --key-id "$NEXORA_BACKUP_KEY_ID" \
  --workflow-key-id "$NEXORA_WORKFLOW_KEY_ID" \
  --evidence-key-id "$NEXORA_EVIDENCE_KEY_ID" \
  --checkpoint-file "$NEXORA_CAPTURE_RECEIPT_FILE" \
  --migration-file database/contracts/v1_customer_workflow/001_customer_workflow_postgres.sql
```

Record `backup_started`, `backup_completed`, and the last committed synthetic
transaction in the restricted evidence file. Run the package verifier with the
same expected key ID and migration file. Record encrypted artifact size,
SHA-256, package manifest/checksum result, database major, role/ownership/RLS
inventory result, and storage/key IDs; do not log key bytes or plaintext
evidence. Only the encrypted artifact may cross the approved transfer channel.

## PostgreSQL 17 V1 logical package — local qualification passed

The separately qualified tool packages only encrypted V1 workflow rows and
does not execute DDL, role changes, migration SQL, Auth changes, or profile
imports. It requires the canonical V1 schema to be provisioned first. It
requires three independent encryption key IDs and stores no backup,
workflow, evidence, or JWT secret bytes in the archive. Target JWT signing
material is supplied separately and is used only to replay rows through the
least-privilege runtime role.

The local qualification passed on the digest recorded in
[Destination Assessment](./DESTINATION_ASSESSMENT.md). For an authorized
future run, use secret files with restricted access. These commands are
templates only; they do not authorize any cloud write:

```powershell
$env:NEXORA_V1_LOGICAL_SOURCE_DSN_FILE = "<source-dsn-secret-file>"
python -m scripts.postgres_v1_workflow_recovery backup `
  --destination "<encrypted-package-path>" `
  --backup-key-file "<backup-fernet-key-file>" `
  --backup-key-id "<backup-key-version>" `
  --workflow-key-id "<workflow-key-version>" `
  --evidence-key-id "<evidence-key-version>" `
  --migration-file "database/contracts/v1_customer_workflow/001_customer_workflow_postgres.sql"
```

Transfer only the encrypted artifact through an approved encrypted,
access-controlled channel. Before restore, separately provision and verify the
canonical V1 schema, matching synthetic profiles, the read-only preflight
credential (non-superuser, BYPASSRLS, SELECT-only), target JWT settings, and
the application login `nxr_customer_workflow_app` with runtime-role membership
and no owner/BYPASSRLS/CREATE privileges. These steps require explicit project
authorization and are not part of the restore command.

```powershell
$env:NEXORA_V1_LOGICAL_PREFLIGHT_DSN_FILE = "<read-only-preflight-dsn-file>"
$env:NEXORA_V1_LOGICAL_RUNTIME_DSN_FILE = "<runtime-dsn-secret-file>"
python -m scripts.postgres_v1_workflow_recovery restore `
  --package "<encrypted-package-path>" `
  --backup-key-file "<backup-fernet-key-file>" `
  --backup-key-id "<backup-key-version>" `
  --workflow-key-id "<workflow-key-version>" `
  --evidence-key-id "<evidence-key-version>" `
  --target-jwt-key-id "<target-jwt-secret-version>" `
  --jwt-signing-secret-file "<target-jwt-secret-file>" `
  --jwt-issuer "<target-auth-issuer>" `
  --migration-file "database/contracts/v1_customer_workflow/001_customer_workflow_postgres.sql"
```

The command requires PostgreSQL 17, verifies the migration hash and target
catalog/grants/RLS, confirms that all three workflow tables are empty through
the read-only preflight connection, verifies target actor/org/role mappings,
and then restores events/evidence transactionally through runtime JWT/RLS.
Approval state is rebuilt by the canonical triggers and checked against the
package. The tool excludes all global/managed roles, `auth.*`,
`data_fabric`, `public.users` rows, migration records, JWT secrets, and other
schemas. Restore-created approvals are materialized from the append-only event
history; the original event timestamps and encrypted export payloads remain
the recovery source of truth.

## Fixed-project execution plan — blocked, no commands authorized

**Do not transfer or restore any package to this project yet.** The full
`restore.sh` path is not valid for PostgreSQL 17.11 because it requires
PostgreSQL 18 and global-role recreation. The logical tool is locally qualified
but has not been run against the project. Do not retry with `pg_restore`, edit
the full-package checks, or restore over the existing `postgres` database.

If an authorized run is later approved for this exact project, proceed only
after the blockers in the [Authorization Checklist](./AUTHORIZATION_CHECKLIST.md)
are closed, using this sequence:

1. Preserve the existing G07 database and external evidence. Obtain a current,
   complete read-only inventory for all schemas, tables, roles/memberships,
   owners, extensions, migration records, Auth objects, and dependencies.
   Reconcile the current one-migration record and empty `public`/workflow
   schemas without treating them as proof that the project is empty.
2. Verify that the exact project can support the canonical V1 schema,
   non-superuser owner/runtime roles, restricted preflight credential, and
   separately configured synthetic JWT/application path without changing
   historical Auth/G07 objects. Stop if schema isolation or role mapping is
   not proven.
3. Obtain the actual project-specific incremental cost, including minimum
   billing, storage, transfer, application/Auth, tax, FX, and cleanup. The
   total must stay within the approved ₹1,000 ceiling; the current estimate is
   not sufficient.
4. Obtain written owner acceptance of RPO/RTO targets, named operator and key
   custodians, an encrypted evidence location, and exact one-time
   authorization for package transfer, required schema provisioning, and
   restore. Preparation approval is not execution approval.
5. Capture the synthetic source package with the logical `backup` command,
   record the backup start/completion and last committed transaction, verify
   its encrypted hash and key IDs, then transfer only the artifact.
6. Apply/verify the canonical schema and roles only under separately signed
   DDL authorization. Run the logical `restore` command once. On any failure,
   preserve sanitized logs, verify transaction rollback, and do not retry a
   non-empty target.
7. Record all eight UTC milestones and run the recovered service/Auth checks
   for workspace resume, evidence decryption, Ask, decision, Finance/CIO/CEO
   history, evidence-linked export, and Customer B denial. Browser validation
   is still required for a customer-service recovery claim.

No step above is authorized by the current request. The present qualification
stops before cloud inspection, transfer, DDL/DML, upload, or restore.

## Customer-service validation

Run these checks only after a separately qualified and authorized isolated
recovery target is available; none is currently available in the fixed
historical project.

Use the existing verifier as the service-level first pass:

```sh
python -m scripts.verify_customer_workflow_recovery \
  --workspace-id "$NEXORA_RECOVERY_WORKSPACE_ID" \
  --evidence-event-id "$NEXORA_RECOVERY_EVIDENCE_EVENT_ID"
```

It verifies synthetic Customer A workspace/evidence integrity, Ask, decision,
Finance/CIO/executive approval history, approved evidence-linked export, and
Customer B denial. It creates authenticated tenant contexts for service
verification; it is **not** a browser login test. Before declaring customer
service available, run the separately configured synthetic Auth/browser smoke
checks for Customer A login, workspace resume, evidence decryption/hash,
approval/export history, and Customer B cross-tenant denial. Do not repeat the
route-freeze journey unless a specific recovery defect requires it.

After each required gate passes, record `application_available` and
`customer_validation_completed`, then summarize all timestamps using
[`scripts/recovery_measurement.py`](../../../scripts/recovery_measurement.py).
Keep database restore time distinct from application availability and
customer-validation time.

## Failure, evidence, and cleanup

- Stop on failed package checks, wrong/missing keys, invalid credentials,
  incompatible version, privilege mismatch, unexpected extension side effects,
  or cost-cap risk. Preserve the source and immutable evidence. For any future
  separately isolated target, freeze it on failure and preserve its sanitized
  logs/catalog evidence; do not retry, repair, or drop it without separate
  exact authorization. Never retry against a non-empty target.
- Store signed authorization, UTC JSONL timing evidence, package hashes,
  sanitized restore logs, catalog/RLS/role results, Auth/browser results,
  validation report, resource IDs, and invoice/usage evidence in a restricted
  location. Exclude credentials, tokens, key bytes, and plaintext evidence.
- After evidence is secured, stop only task-created app/database/storage
  resources identified by exact IDs. Delete a disposable target only if its
  owner explicitly authorized deletion. Keep the encrypted artifact and keys
  according to the approved retention policy; do not delete, reset, or clean up
  the fixed historical Supabase project or its G07 evidence.
- Reconcile the final bill to the approved ≤₹1,000 cap. Any overage or
  unrecognized resource blocks closeout.

