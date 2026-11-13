# Nexora M3 operational bundle

**PREPARED FOR CONTROLLED STAGING. NOT DEPLOYED OR OPERATIONALLY ACCEPTED.** All commands below require the named target/daemon/operator scope. This task ran only offline tests, synthetic file/process checks and Compose CLI schema validation. Do not use real customer data or protected restoration projects.

## Configuration and prerequisites

`docker-compose.production.yml` includes this guarded bundle (Compose >=2.20). The older `docker-compose.yml`, `docker-compose.deploy.yml` and telemetry stack are retained legacy/development configurations, not this production candidate. Do not combine them with the M3 file: that can reintroduce public ports, default credentials and duplicate schedulers.

Supply reviewed cached image **digests** using `NEXORA_{FRONTEND,API,WORKER,BEAT,NGINX,REDIS,PROMETHEUS,ALERTMANAGER}_IMAGE`. No image is built or pulled by validation; the bundle has no `build`. API/frontend/worker/Beat images must include the current runtime changes and existing dependencies; an old M1 image is not qualified merely because it starts. Existing exact-source CI/publication and packaging guards remain unchanged. Operational helpers/configuration are explicit separate artifacts, mounted individually read-only, never a workspace mount over `/app`. Verify `artifact-manifest.json` and candidate provenance before use.

Provide `NEXORA_PUBLIC_ENV_FILE` outside the repository, containing **non-secret** configuration such as `SUPABASE_URL=https://<approved-project>`, `SCHEDULER_TZ=UTC`. Credentials, connector secrets and DSNs do not belong in that file. Set `NEXORA_SUPABASE_URL` for the monitoring availability probe and `NEXORA_PUBLIC_HOST` to the canonical TLS hostname. The entrypoint enforces production account mode, stable encryption keys, durable absolute paths and disabled API APScheduler. No configuration flag enables the unresolved M2 identity/owner paths.

Managed file references (outside the repository, never print their contents):

| Variable | Content / granted services |
|---|---|
| `NEXORA_CREDENTIAL_KEY_FILE` | Stable valid Fernet credential key; frontend/API/worker only |
| `NEXORA_PROSPECT_KEY_FILE` | Stable valid prospect master Fernet key; frontend/API/worker only |
| `NEXORA_SUPABASE_ANON_FILE` | Approved scoped public Auth key; frontend server only |
| `NEXORA_SUPABASE_SERVICE_FILE` | Approved backend authority; API/worker, not browser or Beat |
| `NEXORA_JWT_FILE`, `NEXORA_API_ACCOUNTS_FILE` | Managed signing key (>=32 characters), current configured API-account JSON; API only |
| `NEXORA_REDIS_PASSWORD_FILE` | Independent high-entropy alphanumeric password >=32 characters; Redis bootstrap/health only |
| `NEXORA_BROKER_URL_FILE` | Managed `redis://:<broker-password>@redis:6379/0`; API/worker/Beat |
| `NEXORA_REDIS_MONITOR_PASSWORD_FILE` | Different high-entropy alphanumeric password >=32 characters; Redis bootstrap only |
| `NEXORA_REDIS_MONITOR_URL_FILE` | Managed `redis://monitor:<monitor-password>@redis:6379/0`; operations agent. ACL permits PING only |
| `NEXORA_TLS_CERT_FILE`, `NEXORA_TLS_KEY_FILE` | Canonical ingress certificate chain/private key, readable by nginx UID 10001 |
| `NEXORA_PG_MONITOR_FILE` | Approved least-privilege connection JSON: host, port, dbname, user, password, `sslmode=verify-full`, `sslrootcert=/run/secrets/pg_ca`; operations only |
| `NEXORA_PG_CA_FILE` | Approved PostgreSQL CA; operations and optional local qualifier |
| `NEXORA_ALERT_WEBHOOK_FILE` | Approved HTTPS operational notification destination; Alertmanager only |

Secret files are bind-mounted by Compose. Source filesystem permissions must make them readable only to the intended service UID/group; validate this on the actual Linux host. Runtime loads application secret files into the service process environment without logging values. This is not permission to dump process environments or inspect secret files into evidence.

All nine base named volumes are **external**, explicitly named with `NEXORA_{APPLICATION,EVIDENCE,PROSPECT,REDIS,SCHEDULER,OPS_STATUS,EDGE_CONFIG,PROMETHEUS,ALERTMANAGER}_VOLUME`. Custodian must provision fresh/specified volumes, verify their identity and ownership before startup. The application/Redis/edge/status/scheduler paths need UID/GID 10001; Prometheus/Alertmanager need their configured UID/GID 65534. Never recursively chown an existing data volume by inference. Missing or wrongly owned volumes fail; there is no automatic local data fallback.

Application/evidence/prospect data volumes require qualified **host/storage-provider encryption at rest** and durable single-host storage. Prospect payloads/wrapped tenant keys and stored credentials also have application-level encryption. The SQLite lifecycle/application database as a whole is not encrypted by Fernet; do not claim it is. Compose does not prove host disk encryption. Supply actual storage/key-custody evidence before any customer production use. Network/shared-filesystem SQLite and multi-host replicas are not qualified.

`NEXORA_BACKUP_ROOT` and `NEXORA_BACKUP_STATUS_DIR` are dedicated external host directories. The operations agent mounts both read-only. The host packaging job must write its status to that same status directory. Backup archives must be encrypted; plaintext quiesced snapshots belong in a separate restricted encrypted staging area, never the monitor mount.

## Local preflight and controlled startup

From the repository root, safe source-only checks:

```powershell
.venv/Scripts/python.exe -m deploy.operations.preflight
.venv/Scripts/python.exe -m scripts.run_m3_verification
.venv/Scripts/python.exe -m scripts.validate_m3_compose
```

The last command uses synthetic managed paths, dummy image digests and an isolated Docker CLI config/allowlisted child environment. It invokes `config` only, not a daemon, image build/pull, container, database or webhook. Its PASS is schema validation, not runtime availability.

After separately authorized staging resources, immutable images, secret files, external volumes, encryption and permissions are ready:

```text
python -m deploy.operations.preflight --validate-managed-inputs
docker compose --env-file <managed-non-secret-interpolation-file> -f docker-compose.production.yml config --quiet
docker compose --env-file <managed-non-secret-interpolation-file> -f docker-compose.production.yml up --no-build --pull never -d
```

Do not put credentials into the interpolation file or record a resolved configuration containing secrets. The interpolation file contains image references, file/volume references, approved hostname/URL and disabled feature flags. Preflight validates references and digest shape; it does not certify image contents, operator identity or provider permissions.

Default exposure is loopback only: HTTP health/redirect on 8512 and TLS frontend on 8513. The redirect targets the canonical hostname on standard HTTPS 443; for direct local TLS testing use the explicit 8513 URL/SNI. A separately approved public load-balancer/bind/DNS change is needed before public release. There is no automatic public publication. Unknown TLS Host requests are rejected. `/api`, `/docs`, `/redoc`, `/openapi.json`, `/metrics`, `/ready`, `/admin`, `/auth`, `/realms` remain blocked at ingress. No API, Redis, PostgreSQL or monitoring ports are published.

Startup order: Redis healthy → API live → frontend live; successful edge-config render + frontend healthy → nginx. Operations probes run separately; Prometheus waits for the probe service's liveness. Application `/health` is liveness. `/ready` is infrastructure availability from a fresh private probe record and always reports protected execution disabled; absent/stale/future/incomplete records return 503. Compose does not treat liveness as M2 security qualification.

## Monitoring, alerts and jobs

`monitor.py` probes private API/frontend, authenticated Redis PING, filesystem free space for application/evidence/prospect/backups and recorded backup attempts. `NEXORA_EXTERNAL_PROBES_ENABLED=false` by default: PostgreSQL/Auth remain unverified and infrastructure readiness is false. Set it only after authorization for those exact targets. PostgreSQL probes use one bounded, verified-TLS, default-read-only connection, fixed `SELECT 1`, a three-second connect timeout and statement timeout. Auth health is availability only, never operator/session/MFA assurance. If the provider requires a special authenticated health projection, retain failure until that real scoped adapter is qualified; do not bypass TLS or substitute a service key as identity proof.

Prometheus scrapes private API/operations/Alertmanager; it does not try to parse `/health` JSON as metrics. Alert rules cover missing scrape/dependencies, stale probes, blocked infrastructure readiness, low storage, stale/missing/failed backup packaging, API/unhandled errors and notification-delivery failure. Backend metric paths are route templates, not caller identifiers. Logs are bounded by size/count; ingress access logs omit URLs, query strings and authorization headers. Live notification delivery, promtool/amtool validation and incident-routing acknowledgement have NOT been tested. Use an explicitly approved test receiver first; no messages were sent by this task. Managed PostgreSQL disk/replication/PITR monitoring still needs the provider's own metrics integration.

Application scheduling authority is **one foreground Celery Beat on a single host**. API/legacy APScheduler start paths refuse production. Beat holds a nonblocking shared-volume process lock, retains its schedule database/PID and receives only broker credentials. Worker health uses a node-specific ping; Beat health is PID liveness, not proof of successful job execution. Do not daemonize Beat, share the lock on an unqualified remote filesystem or claim a multi-host singleton guarantee.

Jobs profile is off. Activation requires separate tenant/job/provider qualification, `NEXORA_SCHEDULED_JOBS_ENABLED=true`, and a unique comma-separated `NEXORA_ENABLED_PERIODIC_JOBS` list. Workers consume `nexora-qualified` and recheck the allowlist before running a queued task, so stale disabled tasks cannot execute merely because a worker starts. These controls are not a replacement for each job's business authority/idempotency.

| Registry entry | Schedule (UTC unless reviewed SCHEDULER_TZ) |
|---|---|
| cost-ingestion-hourly | 3600 seconds |
| discovery-hourly | 3600 seconds |
| anomaly-scan-hourly | 3600 seconds |
| alert-engine-hourly | 3600 seconds |
| escalation-hourly | 3600 seconds |
| alert-processor-hourly | 3600 seconds |
| kpi-refresh-15m | 900 seconds |
| optimization-daily | 02:00 |
| report-generation-daily | 03:00 |

Do not also run `scheduler.py`, `scheduler/scheduler_manager.py`, API background scheduling, worker `-B`, or another Beat for these jobs. Dataclass/connector schedule descriptions are data, not additional running schedulers. Retries/redelivery and task success semantics require per-job qualification; no exactly-once execution claim is made.

## Coordinated backup, key recovery and restore

The host `nexora-backup.timer` is prepared for 03:30 UTC daily but is **not installed/enabled**. `backup_job.py` now creates and verifies the complete encrypted PostgreSQL package, including database dump, password-free cluster globals, metadata, and the coordinated storage snapshot. The job still does not fence writers or capture the storage volumes; a custodian coordinator must supply a fresh snapshot and keep every writer fenced until the SQL dump finishes. Do not describe the prepared timer as active unattended backup automation.

Capture procedure:

1. Authorize the exact synthetic source and remote destination; fence application, worker, scheduler, and all external database/Auth writers. Stopping containers alone does not fence an external provider.
2. Capture the three durable storage directories `application/`, `evidence/`, and `prospect/` in the same coordinated window as the PostgreSQL dump. The package job performs `pg_dump` and `pg_dumpall --roles-only --no-role-passwords` itself; the snapshot directory does not contain a separate database dump. Do not copy arbitrary live WAL/database files.
3. Store the operator capture receipt separately with mode `OPERATOR_QUIESCED_CAPTURE`, `snapshot_id`, `database_snapshot_id`, `file_snapshot_id`, `operator_ref`, and timezone-aware `captured_at`. Package within 15 minutes. These values are traceability, not proof that writers were fenced.
4. Configure source libpq credentials via a restricted `PGPASSWORD_FILE`; use a synthetic, non-superuser backup identity with read-only data access and only the catalog/global visibility required by the qualification. The role password is never exported.
5. Use a separate stable managed backup Fernet key and non-secret key ID. Keep the application workflow/evidence keys, runtime DB credentials, wrapped tenant keys, and storage-provider recovery keys in separately approved custody. Never regenerate a production key to make startup work.

Use the complete PostgreSQL package commands and independent-host restore workflow in [the independent recovery package](independent-recovery/README.md). Package verification checks encryption, checksums, migration hashes, role inventory/password policy, and required storage roots. Restore recreates role attributes/memberships, the database and ACLs, then compares owners, schema objects, RLS policies, functions, extensions, workflow fingerprints, and key references. The recovery storage destination must be new. A successful local package is not proof of off-host durability or service recovery.

The host unit runs as restricted `nexora-backup`, with read-only snapshots/config and write access only to archive/status/evidence-log directories. The secret file references (not secret values) belong in `/etc/nexora/backup-public.conf`: `NEXORA_BACKUP_STATUS_FILE`, `NEXORA_RECOVERY_EVENT_LOG`, `NEXORA_QUIESCED_SNAPSHOT_ROOT`, `NEXORA_BACKUP_ROOT`, `NEXORA_BACKUP_KEY_FILE`, `NEXORA_BACKUP_KEY_ID`, `NEXORA_WORKFLOW_KEY_ID`, `NEXORA_EVIDENCE_KEY_ID`, and `NEXORA_CAPTURE_RECEIPT_FILE`. Source PG connection settings use managed environment references, including `PGPASSWORD_FILE`. Install/enable the timer only after the capture coordinator, destination permissions, alert receiver, independent transfer, and restore drill are qualified.

For a timed drill, use `python -m scripts.recovery_measurement` to record UTC backup start/completion, latest verified commit, failure, recovery start, database restore completion, application availability, and customer-validation completion. RTO ends only after authenticated workflow validation; database restore duration alone is not RTO. Use `python -m scripts.enforce_backup_retention` in dry-run mode first and require explicit `--apply` after owner approval. Do not touch protected restoration projects. Promote recovered data or keys only after operator acceptance.

## Disposable M2 PostgreSQL qualification

The prepared package includes all six retained files plus accepted offline A022. `staging-qualification/qualification-manifest.json` records exact source hashes. No migrations run at normal application startup.

After separate authorization for an isolated disposable cluster, use the optional `compose.postgres.yaml` and `compose.qualification.yaml` with both `local-postgres` and `qualification` profiles. Supply `NEXORA_POSTGRES_IMAGE` (inspected PostgreSQL 17 digest), `NEXORA_POSTGRES_DATABASE` with `nexora_m2c_` prefix, `NEXORA_POSTGRES_VOLUME`, local server password/certificate/key files, approved CA and a restrictive managed `NEXORA_PGPASS_FILE`. Server certificate SANs must cover the qualified names/IPs; the qualifier uses verified TLS on 127.0.0.1 in the PostgreSQL service's network namespace, so the retained local-target guards are not weakened. PostgreSQL bootstrap superuser credentials never go to the application/monitor.

Set `NEXORA_SOURCE_ROOT` to the manifest-checked candidate root. Only the contract and synthetic test directories are mounted read-only, not the whole workspace. Future command:

```text
docker compose --env-file <managed-references> -f docker-compose.production.yml -f deploy/operations/compose.postgres.yaml -f deploy/operations/compose.qualification.yaml --profile local-postgres --profile qualification up --no-build --pull never qualification
```

This installs/tests only on the specifically authorized fresh fixture; bootstrap fails on existing schema/history or missing local acknowledgement. The minimal Auth FK schema is not Supabase Auth or real identity assurance. Apply stop-on-error and retain outputs. Then use the existing M2-C guarded race scripts and unknown-commit driver probe under their stated scope. No PostgreSQL, RLS, concurrency or live identity result was obtained here. M2 provisioning/approval/owner positive paths remain disabled until real authority/fencing/atomic adapters are implemented and qualified.

## Synthetic container replacement, shutdown and rollback

The source-only test suite already ran encrypted file verification in fresh Python processes. For a future authorized Docker persistence check, use a new isolated synthetic project name and a locally cached inspected application image with cryptography:

```text
docker compose --env-file <synthetic-image-reference-file> -p <new-synthetic-project> -f deploy/operations/compose.persistence-test.yaml up --no-build --pull never
```

Writer and verifier are separate one-shot containers sharing only their own synthetic volume, with no network. Keep the containers/volume/evidence until disposal is separately authorized; no cleanup command is supplied. Do not mistake this for application-container replacement, real key recovery or a live database restore. Those still need a qualified staging drill with real storage/managed keys and synthetic tenant data.

For authorized orderly shutdown: stop Beat first, allow worker jobs to settle under the accepted uncertainty policy, stop writers/frontend/API, then observability and Redis/database as needed; preserve every volume and secret. Do not delete volumes or keys. On dependency failure, leave protected execution disabled, inspect private liveness/readiness/metrics and bounded logs, and restore only the qualified service/secret/storage dependency. A missing key is an incident, not permission to generate another key. A failed backup retains last-success time and raises failure/staleness alerts. A lost COMMIT acknowledgement requires original-operation reconciliation, never a fresh key or blind retry.

Rollback uses the previous qualified image digests and operational bundle with the SAME durable volumes/keys, after confirming schema compatibility. Never fall back to the insecure development stack, expose API/admin ports or disable release guards. If schema/state compatibility is uncertain, keep maintenance mode and use a newly authorized isolated recovery target; there is no destructive down migration or automatic volume rollback.


## Additional component configuration checks (NOT RUN)

After the isolated staging daemon, inspected cached images, managed test TLS files and external volume ownership are explicitly authorized/ready, run these configuration checks without publishing ports or removing containers:

```text
docker compose --env-file <managed-references> -f docker-compose.production.yml up --no-build --pull never edge-config
docker compose --env-file <managed-references> -f docker-compose.production.yml run --no-deps --pull never --entrypoint nginx nginx -t -c /etc/nexora-edge/nginx.conf
docker compose --env-file <managed-references> -f docker-compose.production.yml run --no-deps --pull never --entrypoint promtool prometheus check config /etc/prometheus/prometheus.yml
docker compose --env-file <managed-references> -f docker-compose.production.yml run --no-deps --pull never --entrypoint promtool prometheus check rules /etc/prometheus/alerts.yml
docker compose --env-file <managed-references> -f docker-compose.production.yml run --no-deps --pull never --entrypoint amtool alertmanager check-config /etc/alertmanager/alertmanager.yml
```

Retain exit codes and redacted outputs. Do not mistake Docker Compose schema validation for these native component checks. Check Redis broker/monitor credential separation and monitor GET denial in the isolated runtime using secret-file environment injection, never a password on command arguments. Exercise alert delivery only to an explicitly approved test receiver; native syntax checks do not prove routing/receipt. No such component container or live notification was executed here.


## Secret rotation and backup status permissions

Application file secrets are loaded once per process. Account-record/key/credential file rotation requires a controlled restart of the affected services and the accepted revocation workflow. Mounted-file changes alone are not immediate live-session/owner fencing.

Provision `nexora-backup` separately and the `nexora-ops` shared group with the actual host/container GID mapping (normally 10001 for this single-host bundle). Give the dedicated backup-status directory setgid/group traversal and read permissions for that group; the host service writes status as group `nexora-ops`, and the helper publishes only this non-secret status file as mode 0640. Backup archives and key files stay privately owned/restricted. The monitor's mount remains read-only. Validate actual Linux/rootless-Docker ACL mapping; Windows source tests do not qualify those permissions. Do not grant the operations container the backup master key or recursively change retained volume ownership to fix a permission error.
