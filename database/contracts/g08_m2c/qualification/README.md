# Local qualification package — PREPARED, NOT EXECUTED

No explicitly authorized existing disposable local PostgreSQL target was established in this task. Do not run the commands below until its custodian authorizes that specific environment. A database name or session flag is a safety interlock, not authorization.

Use a fresh **isolated disposable cluster**, not merely a new database in a shared cluster: migrations create cluster-global role names. No production, restoration or Supabase target is supported by this package. An installer superuser, PostgreSQL 17 qualification runtime and a blank database named `nexora_m2c_<qualification-id>` are prerequisites. The bootstrap creates a minimal `auth.users(id)` fixture; it is not Supabase identity or managed-platform qualification. No automatic server/container creation, credential discovery, reset or deletion is included.

Prepare and inspect without a database:

```powershell
.venv/Scripts/python.exe -m scripts.prepare_m2c_qualification --output-dir docs/release/nexora-v1-m2c-2026-11-08/qualification
```

After separate target authorization, with the local cluster/database already provisioned, and from the repository root:

```powershell
# Replace placeholders only with the custodian-authorized local fixture values.
# Use a managed credential mechanism such as pgpass, never a password in the command.
$env:PGOPTIONS = '-c nexora.qualification_authorized=local-disposable'
psql -X -h 127.0.0.1 -p <authorized-port> -U <fixture-installer> -d nexora_m2c_<qualification-id> -v ON_ERROR_STOP=1 -f database/contracts/g08_m2c/qualification/install_and_test.sql > <local-evidence-file> 2>&1
```

Record the exact source SHA manifest, PostgreSQL version, exit code, stdout/stderr and database/cluster authorization reference. Do not record credentials. `install_and_test.sql` checks the local endpoint, explicit session marker and database prefix, then installs M2-A, runs its rollback-only fixture, installs M2-B and the additive M2-C result-link correction, runs the M2-B fixture, effective-privilege/RLS/RPC denial checks and a transaction-recovery probe. It stops at the first error. Installation commits persist; fixture data rolls back. The six original migration files are not rewritten.

Additional concurrency qualification uses `race_setup.sql`, `race_a.sql`, `race_b.sql`, in that order with A and B in overlapping sessions under the same separately authorized installer principal. Use the same local connection arguments and PGOPTIONS as above. Start B while A holds its ten-second lock; B asserts a measurable wait and SQLSTATE 42501 after revocation. Setup commits explicit synthetic admission/assertions in the disposable fixture. It does not establish real human authentication. These fixture IDs are not production authorizations.

The existing M2-B structural suite covers consumed-operation uniqueness and missing/mismatched proof rollback. Both real execution attempts through the currently closed RPC must deny. A successful two-executor race, live identity revocation/fencing and full owner-result interoperability require the real trust and owner-mutation adapters; do not fabricate those tests by enabling a success stub.

Unknown-commit qualification requires a controlled driver fault after an actual server commit and before acknowledgement. Use the original status ID or operation/key through a currently authorized reader, and record both commit-loss orders. The offline suite exercises this boundary over synthetic connections/coordinator state; no real fault-injection result is claimed. A live owner read adapter is still unavailable. Do not retry a mutation or choose a fresh key merely because its receipt is absent.

`unknown_commit_probe.py` supplies an executable **driver-only** probe using a session temporary table and simulated acknowledgement loss before/after a real server commit. It never inserts an owner authorization, uses no identity stub, and does not qualify D10 or a real network partition. After separate target authorization, set `PGHOST` to loopback, `PGPORT`, `PGDATABASE` to the authorized `nexora_m2c_...` database, `PGUSER`, managed libpq credentials, and `NEXORA_LOCAL_QUALIFICATION_ACK=authorized-disposable-cluster`; then run:

```powershell
.venv/Scripts/python.exe -m database.contracts.g08_m2c.qualification.unknown_commit_probe --authorization-reference <custodian-local-target-authorization-reference>
```

No such probe was run in this task. The acknowledgement/reference flags are interlocks and traceability, not permission to use an unauthorized target. Missing/wrong target settings reject before importing the database driver or connecting.

Recovery procedure:

1. Stop on the first error and retain source manifest plus partial output. Keep all application traffic and writers disabled.
2. If a data transaction is still open, issue `ROLLBACK` in that same authorized fixture session. Verify both checker functions after recovery. Do not report staged results as durable.
3. Do not rerun CREATE migrations over partially installed objects or invent ADMITTED/evidence backfills. Earlier file commits and cluster-global roles remain after a later-file failure.
4. Resolve a deterministic implementation fault in source and qualify on a fresh custodian-provisioned disposable cluster. Disposal of the failed fixture requires its separately authorized lifecycle; this package supplies no destructive cleanup commands.
5. Never apply a destructive down migration to retained immutable history. A real target needs a separately approved compatibility/recovery plan; this blank-fixture package does not authorize one.

G08 tables are global and provide no accepted tenant-success projection. Effective-privilege tests establish that ordinary/runtime tenant callers have no access; application tests establish authenticated tenant/actor rejection. Neither substitutes for successful tenant-scoped owner authorization, which remains disabled pending an accepted operation-to-organization authority binding.
