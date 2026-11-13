# Independent PostgreSQL recovery qualification

This package is prepared for an owner-approved recovery destination. It does
not provision cloud infrastructure, transfer data, create provider accounts,
or authorize access to customer data. Run only with disposable synthetic data
until the owner approves a separate host/account/region failure domain.

## Requirements and failure-domain separation

- PostgreSQL on a separately administered host/account/region, on the same
  major version as the backup source (PostgreSQL 16+).
- A fresh admin database and a temporary superuser recovery administrator
  distinct from all roles in the backup. Global role creation, source-owner
  restoration, and grant replay require superuser-equivalent authority on the
  disposable target. Restore rejects a source-equal host/port and existing
  database or storage targets.
- `pg_dump`, `pg_dumpall`, `pg_restore`, and `psql` matching the PostgreSQL
  server major version, plus Python dependencies from the approved release
  environment.
- An independently recoverable Fernet backup key and non-secret key ID.
  The application workflow key, evidence key, runtime DB credentials, and
  storage-provider credentials are separate recovery dependencies and are not
  embedded in the package. Login roles are restored without passwords; set
  fresh credentials through the approved secret manager before application
  traffic is enabled.
- A consistent, operator-coordinated snapshot of `application/`, `evidence/`,
  and `prospect/`, with a recent timezone-aware capture receipt. Writers must
  remain fenced until both the SQL dump and storage capture are complete.
- A destination storage path that is new and restricted to the recovery
  service. A second local volume on the source host is not independent.

The encrypted package contains a PostgreSQL custom database dump, a
password-free `pg_dumpall --roles-only` dump, role/membership/ownership and
database-object inventories, migration hashes, workflow/evidence fingerprints,
storage files, a keyed manifest, and SHA-256 member checksums. Restoration
recreates role attributes and effective memberships from catalog metadata
using the recovery administrator; grantor identity changes to that bootstrap
administrator. Database ACLs, schema/object owners, extensions, RLS policies,
function definitions/owners, workflow event history, and required key IDs are
compared after restore. Source role passwords are never captured.
Package construction and verification are bounded to 1 GiB and 20,000 members
and hold staged content in memory; qualify actual data volume before production
use or select an approved streaming backup mechanism for larger databases.

Backup-key rotation is a custody operation, not a change to the package format:
create and escrow a new Fernet key under a new key ID; verify a synthetic
package/restore with that key; switch scheduled packaging to the new key; retain
the old key while any retained artifact references its ID; and retire it only
after approved retention/deletion evidence confirms no remaining dependency.
Do not overwrite key files in place or log key bytes. Workflow/evidence keys
have separate application-specific rotation and data-re-encryption procedures.
No key rotation or independent escrow was performed in this qualification.

## Capture, transfer, verify, and restore

1. Obtain written authorization for the exact synthetic source and remote
   destination. Provision the independent PostgreSQL host and storage target
   through the approved infrastructure process. Do not use credentials from a
   protected environment.
2. Coordinate and record a consistent storage snapshot and writer fence. Set
   the source DB connection variables `PGHOST`, `PGPORT`, `PGDATABASE`,
   `PGUSER`, and `PGPASSWORD_FILE` through the approved secret mechanism.
   The password file is not a command-line argument and must be mode 0600 on
   POSIX systems. Set `NEXORA_BACKUP_KEY_FILE`, `NEXORA_BACKUP_KEY_ID`,
   `NEXORA_WORKFLOW_KEY_ID`, `NEXORA_EVIDENCE_KEY_ID`, and
   `NEXORA_CAPTURE_RECEIPT_FILE` separately.
3. Create and verify an encrypted package:

   ```sh
   python -m scripts.postgres_recovery_package backup \
     --destination /srv/nexora/backups/qualification.fernet \
     --storage-root /srv/nexora/snapshots/qualification \
     --key-file "$NEXORA_BACKUP_KEY_FILE" \
     --key-id "$NEXORA_BACKUP_KEY_ID" \
     --workflow-key-id "$NEXORA_WORKFLOW_KEY_ID" \
     --evidence-key-id "$NEXORA_EVIDENCE_KEY_ID" \
     --checkpoint-file "$NEXORA_CAPTURE_RECEIPT_FILE" \
     --migration-file database/contracts/v1_customer_workflow/001_customer_workflow_postgres.sql
   ```

4. Transfer only the completed encrypted artifact to the approved independent
   destination using its approved authenticated transfer mechanism. For an
   authorized SSH destination, for example:

   ```sh
   rsync --archive --partial --protect-args \
     /srv/nexora/backups/qualification.fernet \
     recovery-operator@approved-host:/srv/nexora/recovery-inbox/
   ```

   Confirm the destination is in a separate failure domain. A successful
   transfer is not proof of durability; run package verification on the
   destination using the separately recovered key.
5. On the recovery host, load `TARGET_PGHOST`, `TARGET_PGPORT`,
   `TARGET_PGDATABASE`, `TARGET_PGUSER`, and `TARGET_PGPASSWORD_FILE` from
   approved secret custody. Set `NEXORA_RECOVERY_PACKAGE`,
   `NEXORA_BACKUP_KEY_FILE`, `NEXORA_BACKUP_KEY_ID`,
   `NEXORA_RECOVERY_DATABASE`, and `NEXORA_RECOVERY_STORAGE_ROOT` to new
   target locations, then run:

   ```sh
   deploy/operations/independent-recovery/restore.sh
   ```

   The restore command validates the archive, migration, key ID, checksums,
   version compatibility, and target credentials before creating roles and a
   new database. It fails closed for invalid credentials, existing role or
   database names, incompatible major versions, wrong keys, and existing
   storage destinations. The application must not be pointed at the target
   until restore verification succeeds.

## Application reconfiguration and customer validation

1. Re-provision/rotate runtime DB credentials on the recovered PostgreSQL
   target. Confirm the application role is non-superuser, has no
   `CREATEROLE`/`CREATEDB`/`BYPASSRLS`, and has only the required runtime-role
   membership. Preserve forced RLS and the migration's security-definer
   ownership/grants. Do not enable G08; its authorization remains fail-closed.
2. Update the qualification application's secret-manager reference for
   `NEXORA_CUSTOMER_WORKFLOW_DSN` to the recovered database. Restore the
   original workflow/evidence keys and storage credentials through their
   separate custody paths. Never put secrets in command arguments, a manifest,
   or the evidence log.
3. Use a disposable synthetic Customer A workspace, evidence event ID, and
   Customer B identity. Set `NEXORA_RECOVERY_APP_DSN`,
   `NEXORA_RECOVERY_WORKFLOW_KEY_FILE`,
   `NEXORA_RECOVERY_EVIDENCE_KEY_FILE`,
   `NEXORA_RECOVERY_EVIDENCE_ROOT`,
   `NEXORA_CUSTOMER_WORKFLOW_JWT_SECRET`,
   `NEXORA_CUSTOMER_WORKFLOW_JWT_ISSUER`, and the `NEXORA_RECOVERY_CUSTOMER_A_*`
   and `NEXORA_RECOVERY_CUSTOMER_B_*` identity variables from the approved
   synthetic fixture. Then run:

   ```sh
   python -m scripts.verify_customer_workflow_recovery \
     --workspace-id "$NEXORA_RECOVERY_WORKSPACE_ID" \
     --evidence-event-id "$NEXORA_RECOVERY_EVIDENCE_EVENT_ID"
   ```

   This verifies Customer A's JWT-backed tenant scope, workspace, evidence
   decryption/hash, Ask and decision records, Finance/CIO/executive approval
   history, evidence-linked approved export, and Customer B denial. Output
   contains counts/status only, not plaintext evidence, tokens, or key bytes.

## Timing evidence, monitoring, and retention

Record UTC events in a restricted JSONL evidence file using
`python -m scripts.recovery_measurement record --evidence-file <file> --event
<event>`. Record `backup_started`, `backup_completed`,
`last_committed_transaction`, `simulated_failure`, `recovery_initiated`,
`database_restore_completed`, `application_available`, and
`customer_validation_completed`. Then run
`python -m scripts.recovery_measurement summarize --evidence-file <file>`.
RPO is failure time minus the latest verified commit; RTO is failure time to
application availability. Database restore duration and full validation
duration are reported separately. Use synchronized UTC clocks and do not
substitute database completion for customer-service recovery.

`deploy/operations/nexora-backup.timer` is a prepared daily 03:30 UTC schedule;
`backup_job.py` creates and verifies a local encrypted PostgreSQL package after
a coordinated snapshot. `monitor.py` exposes freshness/failure metrics and the
prepared alert rules include stale and failed backups. These controls are not
installed/enabled here, and alert delivery is not demonstrated.

Retention is dry-run by default. Review the candidate artifact names, then
explicitly opt in to deletion:

```sh
python -m scripts.enforce_backup_retention \
  --directory /srv/nexora/backups --older-than-days <owner-approved-days> --keep-newest 2
python -m scripts.enforce_backup_retention \
  --directory /srv/nexora/backups --older-than-days <owner-approved-days> --keep-newest 2 --apply
```

Only direct `.fernet` files older than the chosen threshold and beyond the
protected newest count can be deleted. Approve retention duration, immutable
copy policy, alert receiver, schedule installation, and named operator/key
custodians before activating production controls.
