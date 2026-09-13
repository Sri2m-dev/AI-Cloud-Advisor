# Local Deployment and Operations Certification

**Status: LOCAL_RELEASE_CERTIFIED**

## Scope

This gate was local-only. It did not connect to Supabase, AWS, Azure, or any
client environment. RC-001 remains complete and frozen. No migration replay or
architecture assessment was reopened.

| Area | Result | Evidence / classification |
| --- | --- | --- |
| Deployment configuration | PASS with documentation correction | Existing release and credential contract tests pass. `DEFAULT_ORG_ID` documentation was corrected to legacy compatibility only; production tenant fallback remains disabled. |
| Persistence/restart | PASS for covered local authorities | Existing Data Fabric, SourceFact, Universal Evidence, approval, and persistence suites pass. |
| Backup/restore | PASS | `scripts/postgres_backup_restore.py` provides environment-driven `backup`, `restore`, and `verify`; focused tests passed and a synthetic isolated PostgreSQL round trip verified `tenant-a:AVAILABLE`. |
| Secrets/confidentiality | PASS for repository checks | Credential-pattern scan found only redacted/test-pattern references and generated cache matches; no secret values were printed. `git diff --check` passes. |
| Release-mode runtime | PASS for existing automated contracts | Demo/pilot flags and fail-closed configuration contracts are covered by existing tests; no external runtime was started. |
| Monitoring/operations | CONFIGURATION_REQUIRED | Existing health/logging contracts are present; operator alerting and recovery ownership remain deployment configuration. |
| AWS harness | PASS locally / live not executed | Existing connector and tenant-boundary tests pass; no AWS credentials or client environment used. |
| Azure harness | PASS locally / live not executed | Existing connector and tenant-boundary tests pass; no Azure credentials or client environment used. |
| Regression | PASS | Final full repository invocation: 1,639 passed, 2 skipped, 0 failures; focused backup/restore suite: 9 passed. |

## External/deferred gates

- Supabase staging: **DEFERRED_EXTERNAL_COST**
- Supabase Auth/RLS/PostgREST: **DEFERRED_EXTERNAL_COST**
- REL-C1 credential rotation/revocation and access-log review: **EXTERNAL_RELEASE_BLOCKER**
- Live AWS certification: **DEFERRED_EXTERNAL_ENVIRONMENT**
- Live Azure certification: **DEFERRED_EXTERNAL_ENVIRONMENT**
- Integrated browser/client UAT: **STOPPED / UNIVERSAL_GOVERNED_ASK_RELEASE_BLOCKER** (see `INTEGRATED_BROWSER_UAT_STATUS.md`)

## Local backup/restore procedure

Set `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and `PGPASSWORD` locally. Set
`NEXORA_PG_DUMP_PATH`, `NEXORA_PG_RESTORE_PATH`, and `NEXORA_PSQL_PATH` when
PostgreSQL tools are not on `PATH`. Never print those values.

```powershell
python scripts/postgres_backup_restore.py backup --destination .tmp/backups
python scripts/postgres_backup_restore.py restore --source .tmp/backups/<artifact>.dump
python scripts/postgres_backup_restore.py verify --query "select count(*) from ..."
```

Restore requires `TARGET_PGHOST`, `TARGET_PGPORT`, `TARGET_PGDATABASE`,
`TARGET_PGUSER`, and `TARGET_PGPASSWORD`, and rejects a target identical to the
source. Restore only into an isolated disposable database. The backup artifact
is custom-format PostgreSQL output and `.tmp/` is ignored by Git.

## Decision

**LOCAL_RELEASE_CERTIFIED**

The local deployment and operations checks are certified. Supabase-specific
certification is separately deferred for cost, and REL-C1 remains external.

No commit or push was performed.
