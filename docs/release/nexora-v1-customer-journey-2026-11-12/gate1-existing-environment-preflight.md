# NEXORA V1 — Gate 1 Existing Environment Preflight

**Status: BLOCKED — historical projects identified; current approval and eligibility unverified**

Preflight date: 2026-11-12. This checklist records local, read-only
preparation only. It is not authorization to call provider APIs, provision
resources, transfer a backup, restore a database, write to an external
environment, or incur cloud spend. No production qualification verdict is
changed by this document.

## Phase 1 — Existing environment discovery

### Safe local discovery performed

- Confirmed the branch is `program/nexora-production-activation`; the existing
  worktree was already substantially modified. Those changes were preserved.
- Inspected `.env.example`, `.env.production.example`, and deployment
  qualification configuration references without printing or copying
  credentials.
- The templates contain AWS, Azure, GCP, and optional PostgreSQL variable
  names, but their values are placeholders. They do not identify an approved
  recovery account/project, endpoint, or region. Protected/live configuration
  values were not inspected.
- Historical, user-supplied Supabase evidence in
  `deploy/staging/NXR-CLOSE-016/evidence/G07/` identifies a source project and
  a separate database-recovery project in `ap-southeast-2`. The evidence is
  dated 17–18 October 2026; it is not a current provider inventory or current
  authorization. The closeout explicitly says the recovery project is retained
  and deletion is not authorized. Both resources are preserved and were not
  contacted.
- The archived recovery-cost confirmation shows **$10.18/month estimated
  incremental compute and disk** for restoring to a new project at that time.
  It is an estimate, not an invoice or proof of actual spend.
- The local qualification compose configuration references a PostgreSQL 17
  image supplied by an operator; the prior disposable local restore used
  PostgreSQL 18. These local targets do not establish an independent failure
  domain.
- No cloud CLI, provider API, remote host, or protected environment was
  contacted. No credentials were printed.

### Candidate inventory

| Candidate | Provider/platform | Account/project alias | Host/cluster reference | Region/location | PostgreSQL version | Private connectivity | Recovery storage | Failure-domain separation | Credentials/privileges | Incremental cost |
|---|---|---|---|---|---|---|---|---|---|---|
| Historical Supabase source | Supabase managed PostgreSQL/Auth project | `nexora-p3-validation` (`ageubmyosicypqqkdvox`) | Historical DB host `db.ageubmyosicypqqkdvox.supabase.co` | `ap-southeast-2` | PostgreSQL 17.6 | Not established by archived evidence | Managed DB and provider backups | Managed project; independent failure-domain properties not proven | Current credentials/roles unknown; no current access attempted | Actual billed amount not found |
| Historical Supabase recovery project | Supabase managed PostgreSQL project | `nexora-p3-validation-restoration` (`uuqprdnqhbsmwubeqouw`) | Historical managed recovery project; current endpoint unknown | `ap-southeast-2` per restore confirmation | PostgreSQL 17.11 | Not established by archived evidence | Managed DB; provider restore disk | Separate project, same organization and region; not proven independent of provider/region failure | Current credentials/roles unknown; restore package's global-role superuser contract is not verified compatible | Historical restore dialog: **$9.68/mo compute + $0.50/mo disk = $10.18/mo estimated additional cost**; not actual spend or current quote |
| Local PostgreSQL qualification cluster | Docker Desktop on this workstation | Local context | Disposable loopback cluster used for local recovery qualification | Local workstation; no cloud region | PostgreSQL 18 in the fresh-cluster restore | Loopback only (`127.0.0.1`) | Temporary local filesystem | **No — same workstation/host failure domain** | Synthetic test identities; temporary recovery superuser and non-production runtime/backup roles | INR 0 cloud spend; disqualified as an independent destination |

**Result:** historical Supabase projects are identifiable from archived
evidence, but neither is a currently approved or verified destination. Their
status, eligibility, private access, and package compatibility are unknown.
`.env.example` and `.env.production.example` remain templates, not approvals.
Local Docker Desktop is not treated as off-host recovery.

**Required owner input to resume:** confirm whether either exact historical
Supabase project may be inspected or name another approved provider/project;
identify the accountable operator and explicitly authorize read-only provider
inspection. The current task authorization explicitly prohibits cloud
connections, so no provider API operation is permitted now.

## Phase 2 — Recovery compatibility

- [x] Encrypted recovery package contract reviewed:
  `scripts/postgres_recovery_package.py` packages a PostgreSQL custom dump,
  password-free global-role dump, structured database/global metadata,
  migration inventory, encrypted storage members, checksums, and an
  authenticated Fernet manifest.
- [x] Restore rejects invalid key/key ID, malformed or incomplete packages,
  source-equal endpoints, existing database/storage targets, incompatible
  server major versions, and role collisions. It needs a fresh target and a
  temporary superuser-equivalent recovery operator distinct from captured
  roles.
- [x] The target must use the **same PostgreSQL major version recorded in the
  package**. The previously qualified disposable restore was PostgreSQL 18;
  that does not prove a future source package is also version 18. Record the
  approved source and target versions during read-only verification.
- [x] Migration compatibility is checked against the exact required migration
  file hashes, including
  `database/contracts/v1_customer_workflow/001_customer_workflow_postgres.sql`.
- [x] `scripts/recovery_measurement.py` requires eight unique timezone-aware
  UTC milestones and reports RPO, full-service RTO, database restore time,
  customer-validation time, and backup duration separately.
- [x] `scripts/verify_customer_workflow_recovery.py` verifies Customer A
  access, workspace/evidence integrity and decryption, Ask/decision, Finance,
  CIO and executive approval history, evidence-linked export, and Customer B
  denial. It emits status and counts, not plaintext evidence or key material.
- [x] `deploy/operations/independent-recovery/README.md` and `restore.sh`
  provide the current recovery contract and execution entry point.
- [ ] Destination PostgreSQL major version, required PostgreSQL binaries,
  private network path, target administrator, target storage, and provider
  limits remain unverified until the owner names the destination.
- [ ] Managed Supabase recovery projects have not been tested for compatibility
  with this package's cluster-global role creation and superuser-equivalent
  restore requirements. Do not assume a managed `postgres` login satisfies
  that contract.

Local validation for this preflight: package/job tests **15 passed, 0 failed,
0 skipped**; CLI help for package verify/restore, customer validation, and
recovery measurement succeeded; `restore.sh` passed Git Bash syntax validation.
These checks do not constitute an independent restore or cloud verification.

## Phase 3 — Cost and safety plan

**Spend ceiling:** INR 1,000 incremental qualification spend. No spend or
provisioning is authorized by this preflight. The owner must separately
authorize any subsequent mutation or spend.

Before any future execution:

- [ ] Obtain a provider quote or documented zero-incremental-cost confirmation
  covering database compute by hour, storage/IOPS, backup/snapshot storage,
  transfer/egress, private networking, logs/monitoring, applicable tax, and
  minimum billing duration.
- [ ] Record the planned maximum duration and a written total estimate no
  greater than INR 1,000. Do not treat a budget alert as a hard cap.
- [ ] Stop before provisioning if the total cannot be bounded, the destination
  is shared/protected, permissions are broader than required, or ownership and
  cleanup are ambiguous.
- [ ] Use only synthetic data and a dedicated disposable target. No real
  customer records or protected-environment credentials.
- [ ] Require private connectivity (private endpoint/VPC/VNet/VPC network or
  approved private tunnel); no public PostgreSQL ingress. Enforce TLS and
  narrow source network identity.
- [ ] Keep source, transfer staging, target database, target storage, and
  evidence locations inventoried. Use least privilege for read-only discovery
  and temporary restore administration; revoke temporary access after
  verification.

| Resource inventory item | Required value before execution |
|---|---|
| Provider/account or project, owner, region | Not identified |
| Recovery database instance/cluster and target database | Not provisioned; identifiers pending approval |
| Private network, subnet, firewall/security-group rules | Not verified; must remain private and narrowly scoped |
| Encrypted package transfer staging and destination storage | Not identified; new restricted path required |
| Temporary recovery admin, runtime login, and secret references | Not provisioned; credentials must be managed, never placed in arguments/logs |
| Synthetic recovery evidence directory and retention/deletion owner | Not designated |
| Cost estimate and maximum billable run window | Cannot be calculated before destination/SKU/location are known |

### Cleanup plan for an authorized future run

1. Stop application/test processes and revoke the temporary recovery
   administrator and any temporary provider role/session.
2. Verify evidence required for owner review is sanitized and copied to its
   approved restricted location; do not retain key bytes, passwords, tokens,
   or plaintext evidence.
3. Delete only the task-created disposable database/cluster, storage objects,
   transfer staging copy, private endpoint/firewall rules, temporary
   identities, and temporary snapshots, using the provider-specific resource
   IDs captured in the inventory. Preserve any pre-existing shared resource.
4. Confirm provider inventory shows the task-created resources deleted and
   check billing usage after provider reporting catches up.
5. If ownership or resource identity is ambiguous, stop and leave the resource
   untouched for owner resolution; never use broad/project-wide deletion.

No cleanup command is executable yet because no destination or task-created
resource IDs exist.

## Phase 4 — Ready-to-run execution procedure (prepared, not executed)

The following are command templates. Replace placeholders only after the
owner identifies and authorizes the exact destination. Do not put secret
values in the shell history or command line. Supply credentials through the
approved CLI identity/secret manager and protected password/key files.

### 1. Verify account, destination identity, private access, and cost

Run **only after** the owner has named the provider/account and explicitly
permitted read-only provider verification. Select the applicable provider
block; these commands were not run:

```sh
# AWS RDS — caller identity and instance metadata (read-only)
aws sts get-caller-identity --output json
aws rds describe-db-instances \
  --db-instance-identifier "$APPROVED_DB_INSTANCE" \
  --query 'DBInstances[0].{Arn:DBInstanceArn,Engine:Engine,Version:EngineVersion,Host:Endpoint.Address,Port:Endpoint.Port,Public:PubliclyAccessible,SubnetGroup:DBSubnetGroup.DBSubnetGroupName,VPC:DBSubnetGroup.VpcId,Status:DBInstanceStatus}' \
  --output json

# Azure Database for PostgreSQL Flexible Server — account and server (read-only)
az account show --query '{subscription:id,tenant:tenantId,name:name}' --output json
az postgres flexible-server show \
  --resource-group "$APPROVED_RESOURCE_GROUP" \
  --name "$APPROVED_SERVER" \
  --query '{id:id,location:location,version:version,host:fullyQualifiedDomainName,publicNetworkAccess:network.publicNetworkAccess,state:state}' \
  --output json

# GCP Cloud SQL — account/project and instance (read-only)
gcloud config get-value project
gcloud sql instances describe "$APPROVED_INSTANCE" \
  --project "$APPROVED_PROJECT" \
  --format='json(name,region,databaseVersion,ipAddresses,settings.ipConfiguration,connectionName,state)'
```

Confirm returned account/project exactly matches the owner's approval,
resource is non-production and disposable, region/location is acceptable,
server is healthy, and PostgreSQL version matches the package. Verify private
connectivity and failure-domain separation from authoritative provider
metadata/network topology. Obtain the provider cost estimate and total
qualification cost before any write. Any mismatch or unknown result is a stop.

### 2. Validate recovery credentials without exposing them

After read-only permission is granted, validate the approved identity using
the provider's identity command above. Do not attempt a database login until
the owner separately authorizes it and supplies managed credentials. Store
the recovery password in a restricted file/secret-manager reference and set
only the file path:

```sh
export TARGET_PGHOST='<verified-private-host>'
export TARGET_PGPORT='5432'
export TARGET_PGDATABASE='postgres'
export TARGET_PGUSER='<temporary-recovery-admin>'
export TARGET_PGPASSWORD_FILE='<restricted-password-file>'
python -c 'import psycopg2; from scripts.postgres_recovery_package import DatabaseConfig; c=DatabaseConfig.from_env("TARGET_"); db=psycopg2.connect(host=c.host, port=c.port, dbname=c.database, user=c.user, password=c.password, connect_timeout=5); cur=db.cursor(); cur.execute("SELECT version(), current_user"); print(cur.fetchone()); db.close()'
```

The custom command reads the plain-text password file through
`DatabaseConfig.from_env("TARGET_")`; no password is an argument or printed
value. Keep the file restricted (mode 0600 on POSIX). Confirm the login is a
temporary recovery administrator with sufficient authority to recreate
cluster roles, database ownership, and grants on the disposable target only.

### 3. Check separation and destination readiness

Use the provider metadata outputs from step 1 to record account/project,
region, instance ID, private endpoint, network/subnet, database version, and
public-access state. Compare source and destination account/project, host,
region, and network failure domains. Record the target system identifier
before restore if accessible. Do not proceed if public access is enabled, the
target overlaps a protected/shared system, or independent separation cannot be
proven.

### 4. Transfer only the encrypted artifact

After the owner authorizes transfer and identifies the endpoint:

```sh
rsync --archive --partial --protect-args \
  '<approved-local-path>/qualification.fernet' \
  '<approved-operator>@<approved-private-transfer-host>:<restricted-inbox>/'
```

Use the approved private authenticated transfer mechanism instead if `rsync`
is not available. Record source and destination artifact SHA-256 values and
transfer timestamps; do not transfer plaintext evidence or key material.

### 5. Verify the encrypted package at the destination

On the recovery host, use the separately recovered backup-key file and exact
key ID from secret custody:

```sh
python -m scripts.postgres_recovery_package verify \
  --source "$NEXORA_RECOVERY_PACKAGE" \
  --key-file "$NEXORA_BACKUP_KEY_FILE" \
  --key-id "$NEXORA_BACKUP_KEY_ID" \
  --migration-file database/contracts/v1_customer_workflow/001_customer_workflow_postgres.sql
```

Proceed only on `PACKAGE_VERIFIED`; capture sanitized status, package hash,
key ID (not key bytes), migration identity, and verification time.

### 6. Restore into the authorized disposable target

Set `TARGET_PGHOST`, `TARGET_PGPORT`, `TARGET_PGDATABASE`, `TARGET_PGUSER`,
and `TARGET_PGPASSWORD_FILE` from the approved managed configuration. Set
`NEXORA_RECOVERY_PACKAGE`, `NEXORA_BACKUP_KEY_FILE`,
`NEXORA_BACKUP_KEY_ID`, `NEXORA_RECOVERY_DATABASE` (new name), and
`NEXORA_RECOVERY_STORAGE_ROOT` (new private path). Then run:

```sh
deploy/operations/independent-recovery/restore.sh
```

Restore creates database/global objects and writes destination storage. This
is a mutating operation; it has not been authorized or run. Do not point an
application at the target unless restore returns `RESTORE_VERIFIED`.

### 7. Run customer and tenant-security validation

Set the recovery app DSN, workflow/evidence key file paths, evidence root, JWT
secret/issuer, and synthetic Customer A/B identity fields through restricted
environment/secret management. Supply the synthetic workspace and evidence
event identifiers:

```sh
python -m scripts.verify_customer_workflow_recovery \
  --workspace-id "$NEXORA_RECOVERY_WORKSPACE_ID" \
  --evidence-event-id "$NEXORA_RECOVERY_EVIDENCE_EVENT_ID"
```

Require `CUSTOMER_WORKFLOW_RECOVERY_VERIFIED`, Customer A success, complete
evidence/approval/export checks, Customer B denial, and no secret/plaintext
output. Any mismatch is a failed drill.

### 8. Measure RPO/RTO and database restore separately

Record each actual UTC event exactly once in a new restricted JSONL file; use
synchronized clocks and record the newest verified commit, not merely backup
completion:

```sh
EVIDENCE='<restricted-evidence-path>/recovery.jsonl'
python -m scripts.recovery_measurement record --evidence-file "$EVIDENCE" --event backup_started
python -m scripts.recovery_measurement record --evidence-file "$EVIDENCE" --event backup_completed
python -m scripts.recovery_measurement record --evidence-file "$EVIDENCE" --event last_committed_transaction
python -m scripts.recovery_measurement record --evidence-file "$EVIDENCE" --event simulated_failure
python -m scripts.recovery_measurement record --evidence-file "$EVIDENCE" --event recovery_initiated
python -m scripts.recovery_measurement record --evidence-file "$EVIDENCE" --event database_restore_completed
python -m scripts.recovery_measurement record --evidence-file "$EVIDENCE" --event application_available
python -m scripts.recovery_measurement record --evidence-file "$EVIDENCE" --event customer_validation_completed
python -m scripts.recovery_measurement summarize --evidence-file "$EVIDENCE"
```

Use actual observed milestones, not these command invocation times if delayed;
`record --at <timezone-aware-ISO-8601>` is available for recording measured
timestamps. Compare RPO/RTO only to owner-approved objectives. No approved
objectives or measured independent values currently exist.

### 9. Collect restricted evidence

Capture only sanitized account/resource metadata, cost estimate, private
connectivity and failure-domain proof, PostgreSQL versions/system identifiers,
manifest verification status and hashes, restore verification output,
customer-validator status/counts, UTC milestones/summary, and cleanup
confirmation. Store evidence in an owner-approved restricted location. Exclude
passwords, key bytes, tokens, DSNs containing passwords, plaintext evidence,
and sensitive provider outputs not needed to substantiate the checks.

### 10. Clean up

Use the provider-specific deletion commands only after confirming every
resource ID against the task's approved inventory and retaining authorized
evidence. Delete only the disposable resources listed in the cleanup plan;
remove temporary identities/network rules and verify absence afterward.
Provider and resource identifiers are not yet known, so no external cleanup
commands are prepared for execution at this stage.

## Phase 5 — Exit criteria

**Outcome: BLOCKED.** Historical Supabase project aliases/IDs are known from
archived evidence, but no current destination has been designated or
authorized for inspection. Current provider/resource state, private
connectivity, independent failure-domain separation, credentials/privileges,
and package compatibility remain unverified. The INR 1,000 ceiling cannot be
demonstrated from a historical USD monthly estimate without a current quote,
currency conversion, billing duration, and all-in cost components. No cloud
API, provisioning, transfer, restore, external write, or spend occurred.

To re-enter preflight, obtain owner confirmation of the exact approved
historical project (or another provider/account/project), current resource
identifier and region, an owner-designated operator, and explicit read-only
inspection permission. Separately authorize credential/connectivity checks
and obtain a complete cost estimate bounded within INR 1,000 before any
mutation authorization. Gate 1 remains **not passed** until a separately
authorized independent recovery is executed and verified.
