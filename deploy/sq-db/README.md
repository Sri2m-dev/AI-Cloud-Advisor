# SQ-DB standalone qualification

Prepared, not executed. No dependency on production Compose, application images,
Supabase Auth, monitoring or external endpoints. No credential generation is
performed by this package. Do not use the incomplete full-stack references.env.

## Fixed identities and preservation

Context: `desktop-linux`; project: `nexora-m3sq-local-20261110`;
database: `nexora_m2c_m3sq_20261110`;
internal network: `nexora-m3sq-local-20261110_sqdb_private`;
external volume: `nexora-m3sq-local-20261110_postgres_data`.
No host database port, external application volume, host network or Docker socket.
The volume already exists: never recreate, reset or repurpose it. Prior metadata
showed disposable scope, zero links and 0 B. Reconfirm custodian ownership,
synthetic-only/empty status and attachments before authorized first startup.
Compose will not create the external volume. Its external name intentionally
references only that proposed disposable resource. No environment started here.

## Image gate

SQL uses PostgreSQL core PL/pgSQL, JSONB, deferred constraints, advisory locks,
roles, SECURITY DEFINER functions and privilege checks. No CREATE EXTENSION was
found in the retained installation/fixture includes. PostgreSQL 17 with psql,
pg_isready, /bin/sh, cp/chown/chmod and the standard postgres OS user is required.
Server wrapper requires `/usr/local/bin/docker-entrypoint.sh`, standard
POSTGRES_PASSWORD_FILE handling and PGDATA `/var/lib/postgresql/data`.
Approve an immutable repository@sha256 digest only after verifying version,
these filesystem/entrypoint requirements, image provenance and a blank init
without vendor Auth schemas or conflicting roles. Static compatibility is not a
runtime qualification result. First SQL bootstrap also rejects preexisting Auth
or G08 objects; later CREATE ROLE fails closed on role conflicts.

Cached public.ecr.aws/supabase/postgres:17.6.1.143 has verified local digest
80d7b27c3e8d77cfa7226eee9508671796da214781ff15a35b3670d7ad5ee453,
but metadata reports entrypoint docker-entrypoint.sh and command postgres -D
/etc/postgresql. Required entrypoint path, PGDATA behavior and blank initialization
are not established. It is NOT qualified or selected. Image reference remains unset.
No image pull, container creation, export or runtime inspection was performed.

## Managed synthetic references (future authorized preparation only)

Copy references.env.example to an approved external directory as sqdb.env; fill
SQDB_SOURCE_ROOT and a qualified SQDB_POSTGRES_IMAGE. Set five distinct external
file paths: SQDB_PASSWORD_FILE, SQDB_SERVER_CERT_FILE, SQDB_SERVER_KEY_FILE,
SQDB_CLIENT_CA_FILE, SQDB_PGPASS_FILE. No values are supplied here. The reference
file contains paths, never secret contents. Do not reuse credentials from another
environment. Do not paste credentials into commands, logs, git or Compose output.

After separate credential-generation authorization, a custodian must generate a
unique high-entropy disposable password and private test CA/server keypair using
an approved CSPRNG/PKI tool, not application/production keys. Server certificate
must include IP SAN 127.0.0.1 and serverAuth; keep CA private key separately.
Use a non-wildcard pgpass entry for 127.0.0.1:5432:nexora_m2c_m3sq_20261110:postgres
with that unique password and proper pgpass escaping. Restrict host file ACLs;
provide only the public CA certificate to clients. The installer is a disposable
cluster superuser because fixtures create roles; never grant it to applications.
Server cert/key and client pgpass are copied to private tmpfs with Linux mode600
at future startup; original managed files remain read-only and unchanged.
TLS expiry/SAN/trust, password match, permissions and filesystem encryption need
real verification later. check_references.py checks existence, not secret contents.

## Offline commands (no SQL or daemon connection)

```powershell
python -B deploy/sq-db/validate.py
python -B deploy/sq-db/test_offline.py
python -B deploy/sq-db/check_references.py C:/Nexora-Staging/m3sq-20261110/sqdb.env
```

Last command requires real managed paths; not run during this pass. Validator
uses nonexistent synthetic secret references and fake image digests for schema
validation only. offline-results.json records that limitation.

## Future authorized execution commands -- NOT EXECUTED

Run from candidate repository root. Recheck volume metadata, attachments and
resource names before any startup. Do not create a replacement volume on failure.

```powershell
$refs = 'C:/Nexora-Staging/m3sq-20261110/sqdb.env'
$cfg = @('--context','desktop-linux','compose','--env-file',$refs,
  '--project-name','nexora-m3sq-local-20261110',
  '-f','deploy/sq-db/compose.yaml','--profile','qualification')
python -B deploy/sq-db/check_references.py $refs
# STOP if nonzero; independently approve image/TLS/volume evidence.
docker @cfg config --quiet
# STOP if nonzero. Requires explicit startup authorization.
docker @cfg up -d --no-build --pull never --wait postgres
# STOP if unhealthy; never reset PGDATA to fix initialization.
docker @cfg run --name nexora-m3sq-db-install --no-deps qualification
# Retain exit status and sanitized stdout/stderr; stop on any failure.
```

Installer reuses the retained 12 include files and seven migrations in manifest
order. Covers clean installation, composite/deferred constraints, append-only
history, checker visibility/read-only protections, receipts, revocation,
invalidation, replay, privileges, unauthorized function access and rollback.
Ordinary/tenant callers must be denied; there is no positive tenant or real Auth
qualification. Inspect retained fixtures for exact assertions; do not infer
coverage of external Auth, PostgREST transport or cross-system fencing.

After successful installation, run concurrency setup once:

```powershell
docker @cfg run --name nexora-m3sq-db-race-setup --no-deps qualification -X -v ON_ERROR_STOP=1 -f /qualification/database/contracts/g08_m2c/qualification/race_setup.sql
# Terminal A, with the same $cfg:
docker @cfg run --name nexora-m3sq-db-race-a --no-deps qualification -X -v ON_ERROR_STOP=1 -f /qualification/database/contracts/g08_m2c/qualification/race_a.sql
# Terminal B: start while A holds its lock (10-second window).
docker @cfg run --name nexora-m3sq-db-race-b --no-deps qualification -X -v ON_ERROR_STOP=1 -f /qualification/database/contracts/g08_m2c/qualification/race_b.sql
```

B asserts actual waiting and fresh revocation denial. A timing miss is a failure,
not a pass; retain both outcomes. Setup is not idempotent. Repeated CREATE or
setup failure never authorizes clearing immutable history.

Optional compose.driver.yaml prepares the retained unknown_commit_probe.py.
It additionally requires SQDB_DRIVER_IMAGE (qualified isolated Python image with
psycopg2 plus exact candidate modules/dependencies under /app, including repository,
auth and data_fabric imports) and SQDB_AUTHORIZATION_REFERENCE. Base SQL tests
never require this image. Check its imports and candidate hashes before use.

```powershell
$driver = @('--context','desktop-linux','compose','--env-file',$refs,
 '--project-name','nexora-m3sq-local-20261110',
 '-f','deploy/sq-db/compose.yaml','-f','deploy/sq-db/compose.driver.yaml',
 '--profile','driver')
docker @driver config --quiet
docker @driver run --name nexora-m3sq-db-commit-probe --no-deps commit-probe
```

This is real-driver temporary-table testing with simulated acknowledgement loss,
not a network-partition test, owner execution success or D10 reconciliation
acceptance. Real identity, operation-to-organization binding and external fencing
remain disabled and unqualified. No mock authentication is introduced.

No cleanup, down -v, volume deletion or automatic migration retry is supplied.
On failure retain containers, volume and sanitized logs; preserve partial install
state and obtain separate recovery/disposal authorization. Source rollback is not
a destructive database down-migration. Full live qualification remains NO-GO
until image, managed files, volume ownership, capacity and execution permission
are established. Docker VM free disk and memory headroom still need confirmation.
