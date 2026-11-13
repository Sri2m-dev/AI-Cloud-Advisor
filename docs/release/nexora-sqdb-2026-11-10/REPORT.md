# SQ-DB real execution results

SQL-core PostgreSQL qualification PASSED. Complete SQ-DB sign-off remains open
for the optional real-driver commit probe/uncertainty qualification. This is not
SQ-APP, real identity, tenant-success or external fencing acceptance.

## Target and image

Current Product Owner activation directive authorized the named disposable target
once gates passed. desktop-linux / nexora-m3sq-local-20261110 /
nexora_m2c_m3sq_20261110. Official Docker Library postgres:17-bookworm public
manifest resolved linux/amd64 digest
sha256:73bedc9eaa0121b92b9b26bb52e5141b3f6f37479c7ef913c0160455763ca80a.
Pulled that exact digest with empty isolated registry configuration. Runtime
binaries report PostgreSQL/psql 17.11. Standard entrypoint/PGDATA were verified;
real blank initialization and verified-TLS SQL execution succeeded.

Expected volume label, zero attachments, Docker 0B, direct empty-directory
inspection and root ownership passed before initialization. No other named volume
was used. The private network is internal, with no published ports. VM data disk
reported 964913100 KiB free, VM available memory 14667 MiB; host free RAM about
5.2 GiB. Capacity observations are point-in-time, not a sustained load test.

## Managed configuration

C:/Nexora-Staging/m3sq-20261110/sqdb.env references unique synthetic managed
password/TLS/pgpass files in its sqdb-managed directory. Directory ACL inheritance
is disabled with current-user/SYSTEM access. Seven-day private local CA and
server certificate: signature/key/SAN/expiry and password/pgpass pairing checked.
Client uses verify-full to 127.0.0.1. No secret value is in this report or git.
The earlier incomplete full-stack references.env was preserved unchanged.

## Execution and corrected failures

1. Initial startup exited before PGDATA access: Windows CRLF in shell wrappers.
   Converted wrappers to LF, added offline guard, reconfirmed empty volume;
   retry succeeded. Original failure logs retained.
2. Original installer passed all M2-A migrations and rollback-only M2-A fixtures,
   then S021. A021 parse error rolled back that migration's transaction.
   Parenthesized its CASE expression without changing its authority predicates.
   Preserved the exact original; guarded continuation applied only the remaining
   migrations, never reset/replayed committed schema.
3. Owner fixture expected append-only SQLSTATE55000, but FK precheck intercepted
   its isolated TRUNCATE test. Added CASCADE inside rollback-only negative test;
   append-only trigger now supplies the expected denial. Original preserved.
4. All owner fixtures, privilege/RLS and rollback/recovery fixtures passed.
5. Race setup committed synthetic history; two actual sessions overlapped.
   Granted advisory lock was observed before launching B. Both exited0;
   B's fixture asserted actual wait and fresh revocation denial.
6. Final READ ONLY transaction executed both checkers successfully. TLS=true,
   READ COMMITTED, 15 G08 tables all FORCE RLS, 26 deferrable constraints.
7. A separate new network_mode:none, tmpfs-only clean-install fixture under the
   same authorized project reran the corrected canonical installer end-to-end.
   It passed all seven migrations and retained fixtures. No persistent volume was
   mounted in that fixture. It remains running to preserve its in-memory state.

Canonical command: docker --context desktop-linux compose --env-file
C:/Nexora-Staging/m3sq-20261110/sqdb.env -p nexora-m3sq-local-20261110
-f deploy/sq-db/compose.yaml --profile qualification run
--name nexora-m3sq-db-install --no-deps qualification.
Do not rerun CREATE migrations or reuse retained container names on this installed
cluster. For clean proof see compose.clean.yaml and clean-install.log.
Concurrency command executed: python -B deploy/sq-db/run_concurrency.py.

## Limits and next gates

Optional compose.driver.yaml was schema-validated only. No qualified Python image
with psycopg2 plus exact candidate modules/dependencies was available; commit probe
NOT RUN. No real lost-COMMIT network fault or D10 reconciliation acceptance.
Qualify that driver image and use the existing retained unknown_commit_probe.py;
it tests simulated acknowledgement loss with real commits, not external identity.

98 existing M2 offline tests passed (two nonfatal pytest-cache permission warnings),
8 isolation tests passed, all three Compose variants passed offline schema checks.
The initial system Python lacked pytest; existing .venv supplied it. Preserve
old manifests: qualification-corrections.json explicitly links original hashes,
preserved originals and corrected executed hashes; executed-source-manifest.json
records the SQL actually used. offline-results.json still labels only offline
checks; results.json is the separate real-execution record.

SQ-APP still needs qualified exact-candidate application images, resolved loopback
ingress port collision, approved real synthetic Auth identities, tenant binding,
owner authority/atomic adapters and external fencing, product journey, persistent
encrypted resume and coordinated recovery/monitoring qualification. Do not enable
owner execution based on these fixture approvals. Existing application containers
remain unchanged. No cleanup, commit, push, tag or guard change occurred. Both
SQ-DB servers and all runner/image-check containers are retained; no lifecycle
cleanup authorization is inferred from qualification completion.
