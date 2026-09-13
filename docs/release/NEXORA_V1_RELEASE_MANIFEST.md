# Nexora v1 — Release Package Manifest

Date: 2026-09-12
REL-C1 closure update: 2026-09-13

This manifest defines the contents of the Nexora v1 release package. It does
not authorize commit, push, or tag; those remain separate, explicitly
authorized operations. See `docs/release/NEXORA_V1_FINAL_RELEASE.md` for the
authoritative certified-state record.

## A. Source

All tracked application source under the current certified worktree
(components, pages, services, repositories, connectors, enterprise_copilot,
shared, universal_evidence, etc.), excluding paths listed under
"Release exclusion boundary" below.

## B. Database / Migrations

- `migrations/data_fabric/*.sql`
- `supabase/bootstrap/public_prerequisites.sql`
- `supabase/migrations/*.sql`
- `scripts/audit_database_bootstrap.py`
- `scripts/postgres_backup_restore.py`

## C. Deployment / Configuration

- `docs/NEXORA_DEPLOYMENT_GUIDE.md`
- `docs/NEXORA_ENVIRONMENT_CONFIGURATION.md`
- `docs/release/PRODUCTION_CONFIGURATION.md`
- `requirements.txt` and related dependency manifests
- `docker-compose*.yml`, `Dockerfile.*`

## D. Test / Certification Evidence

- `tests/` (full certified suite)
- `docs/cmp/CMP-P6-*/` (DEF/SC/RC evidence, preserved as historical evidence)
- Final regression baseline: 1919 passed, 1 known non-blocking failure, 2
  skipped (recorded in `NEXORA_V1_FINAL_RELEASE.md`)

## E. Security / Known Limitations

- `docs/release/KNOWN_LIMITATIONS.md`
- Known non-blocking persona organization-ID issue (see final release record)
- REL-C1: `PASS_WITH_RECORDED_RESIDUAL_OBSERVATION` (see final release record)

## F. Operations / Backup-Restore

- `tests/release/test_postgres_backup_restore.py`
- `docs/release/LOCAL_DEPLOYMENT_OPERATIONS_CERTIFICATION.md`

## G. Release Notes

- `docs/release/NEXORA_V1_FINAL_RELEASE.md`
- `CHANGELOG.md`

## H. External Deferrals

- Supabase live certification: `DEFERRED_EXTERNAL`
- AWS live certification: `DEFERRED_EXTERNAL`
- Azure live certification: `DEFERRED_EXTERNAL`
- See `docs/release/LIVE_CONNECTOR_CERTIFICATION_PREPARATION.md`

## I. REL-C1 Security Sign-off

Status: **PASS_WITH_RECORDED_RESIDUAL_OBSERVATION**.

Project owner **Srikanth** recorded sign-off on **2026-09-13** for the
Supabase AI-Cloud-Advisor-Dev development project. Credential rotation and
replacement verification passed; repository reuse assessment and available
log review are complete. The unattributed REST probing event remains a
reviewed residual observation. Unauthorized disclosure was not established,
and full historical log review was not possible from available evidence.

See `docs/release/NEXORA_V1_FINAL_RELEASE.md` for the supplied evidence,
retention/attribution limitations, and development-project residual-risk
acceptance. Independent corporate Security/InfoSec approval is not claimed.
No credential value is included in this package.

```
COMMERCIAL_RELEASE_STATUS=READY_FOR_FINAL_RELEASE_STAGING
READY_FOR_FINAL_RELEASE_COMMIT=NO
```

This documentation update does not publish the commercial release. Commit,
push, and tag remain unauthorized.

## Release exclusion boundary

Repository sanitization is complete (`HISTORY_REWRITE_PERFORMED=NO`; local
copies preserved on disk). Untracked from the release candidate:

- `data/CUR Jan 2026.xlsx`
- `backup_unused/`
- `backups/technology_tables_20260620_130633/`
- `app.py.bak`
- `supabase/.temp/` (including `pooler-url`)
- `temp_uploads/`
- `test_env/data/uploaded_cur_file.xlsx` (confirmed not tracked)
- `.venv/`, `.tmp/`
- runtime databases, runtime logs, local caches
- local secrets
- known confidential real-client acceptance workbooks and customer/client
  evidence
- any other credential-bearing temporary artifact

No client data is packaged.
