# P3.10 Phase 2 CI Certification

## Certification verdict

**CERTIFIED for the current non-secret release-candidate baseline.** The CI workflow now installs every declared candidate dependency manifest, validates dependency resolution, compiles and imports active source, performs reproducible Ruff checks, collects and executes the full suite, reruns the 94-test P3 gate, collects all five gated integrations, and proves that they skip without secrets.

This certification does not authorize a merge or tag.

## Baseline

- Repository: `C:\Users\SrikanthMudaliar\AI-Cloud-Advisor-p3-clean`
- Branch: `feature/p3-supabase-live-validation`
- Starting commit: `507e41c693e312197b5d1495d5a9667ac18ca625`
- Ending commit: the Phase 2 commit containing this report
- Python: 3.11.9 locally; CI pins the Python 3.11 release line
- Starting worktree: clean

## Workflow inventory

### `.github/workflows/ci.yml` — CI

- Triggers: pushes to `main`; all pull requests.
- Branch filters: push is `main` only; pull requests have no branch restriction.
- Runner: `ubuntu-latest`.
- Python: 3.11 via `actions/setup-python@v5`.
- Dependencies: `requirements.txt`, `requirements-dev.txt`, `requirements-prod.txt`, `requirements.frontend.txt`, and `backend/requirements.txt` after pip upgrade.
- Cache: setup-python pip cache keyed from all five manifests.
- Compile/import: in-memory compile of every tracked `.py` outside `archive/`; representative Data Fabric, Supabase adapter, approval-service, and PostgreSQL-driver imports.
- Lint: critical Ruff syntax/control-flow rules across non-archive code; full configured Ruff rules on the certified approval-service health surfaces.
- Tests: full collection, full secret-free execution, the 94-test P3 gate, integration collection, and explicit secret-free integration execution.
- Integration behavior: all `P3_SUPABASE_*` values are explicitly empty for execution steps. The safety helper remains the second fail-closed barrier.
- Secrets: none.
- Artifacts: none produced or uploaded.
- Permissions: read-only repository contents.

### `.github/workflows/cd.yml` — CD

- Triggers: pushes to `main`; manual dispatch.
- Branch filters: automatic runs only on `main`.
- Runner: `ubuntu-latest`.
- Python: none; Docker build workflow.
- Dependencies: resolved inside the five service Dockerfiles, not directly by the workflow.
- Cache: Buildx is enabled; no explicit remote layer cache is configured.
- Compile/lint/tests: none; deployment is expected to follow CI governance.
- Integration behavior: builds and pushes frontend, API, worker, beat, and nginx images.
- Secrets: GitHub-provided `GITHUB_TOKEN`; optional `DEPLOY_WEBHOOK_URL` is guarded by a non-empty check.
- Artifacts: five GHCR images, tagged by commit SHA and `latest`; no Actions artifact upload.

### `.github/workflows/background-jobs-cron.yml` — Background Jobs

- Triggers: hourly, every 15 minutes, daily at 02:00 and 03:00 UTC, plus manual dispatch.
- Branch filters: none; scheduled workflows execute from the default branch.
- Runner/Python: `ubuntu-latest`, Python 3.11.
- Dependencies: `requirements.txt` and `backend/requirements.txt`.
- Cache: none.
- Compile/lint/tests: none; operational workflow.
- Integration behavior: executes KPI refresh, ingestion, anomaly, alert, optimization, and report jobs according to current UTC time.
- Secrets: Supabase, OpenAI, AWS, Azure, and GCP operational secrets. It is not pull-request-triggered.
- Artifacts: none.
- Correction: fixed an indentation error that prevented the hourly alert call from forming valid embedded Python.

### `.github/workflows/ingestion-cron.yml` — Scheduled Ingestion

- Triggers: every 30 minutes plus manual dispatch.
- Branch filters: none; schedules execute from the default branch.
- Runner/Python: `ubuntu-latest`, Python 3.11.
- Dependencies: `requirements.txt`.
- Cache: none.
- Compile/lint/tests: none; operational workflow.
- Integration behavior: runs AWS, Azure, and GCP cost-sync entry points sequentially.
- Secrets: Supabase and the three cloud-provider credential sets. It is not pull-request-triggered.
- Artifacts: none.

## Issues found and disposition

| Finding | Disposition |
|---|---|
| CI installed only runtime and development manifests | CI now installs all five candidate manifests. |
| No dependency consistency gate | Added `python -m pip check`. |
| No dependency caching | Added setup-python pip caching using all manifests. |
| No active-source compile/import gate | Added tracked, non-archive in-memory compilation and representative imports. |
| `ruff check .` was not reproducible | Replaced with a critical active non-archive gate and full focused gate; broad lint debt is documented rather than mass-refactored. |
| Bare `mypy` fails because the hyphenated checkout directory is treated as a package | Removed this obsolete blocking command; type-check configuration remediation is deferred. |
| Full collection was implicit only | Added an explicit 325-test collection gate. |
| Integration opt-in skips were collected but not executed | Added explicit secret-free execution requiring the five safe skips. |
| CI installed no prod/frontend/backend manifests | Added all three without upgrading pinned dependencies. |
| Background-job embedded Python had invalid indentation | Corrected one line only. |
| Background Jobs and Scheduled Ingestion overlap in cloud-ingestion responsibility | Recorded as operational duplication; no redesign in Phase 2. |
| Cron workflows use operational secrets without preflight messages | Recorded; they are schedule/manual only and never run on pull requests. No secrets are echoed. |
| No test artifacts or reports are retained | Accepted for this gate; exact console results remain authoritative. |

No command uses `continue-on-error`, `|| true`, or another failure-masking mechanism. GitHub's default bash error handling stops each certification step on failure.

## Certified commands

```text
python -m pip install -r requirements.txt -r requirements-dev.txt \
  -r requirements-prod.txt -r requirements.frontend.txt \
  -r backend/requirements.txt
python -m pip check

# In-memory compile of tracked *.py excluding archive/, then imports:
# data_fabric, psycopg2, services.approval_service,
# data_fabric.adapters.supabase.atomic_write

ruff check . --exclude archive --select E9,F63,F7
ruff check services/approval_service.py tests/services/test_sla_logic.py
pytest --collect-only -q
pytest -q

pytest -q \
  tests/data_fabric/test_supabase_integration_safety.py \
  tests/data_fabric/test_supabase_atomic_write_unit.py \
  tests/data_fabric/test_persistence_foundation.py \
  tests/data_fabric/test_persistence_certification.py \
  tests/data_fabric/test_supabase_adapter_structure.py
python -m compileall -q data_fabric tests/data_fabric

pytest --collect-only -q <four gated integration modules>
pytest -q -rs <four gated integration modules>
```

The full and integration execution commands explicitly set all three `P3_SUPABASE_*` values to empty strings.

## Exact reproduced results

| Check | Result |
|---|---:|
| Dependency resolution | `pip check` passed |
| Active tracked Python compile | 1,095 passed, 0 syntax failures |
| Representative imports | passed |
| Ruff critical active-source gate | passed |
| Ruff focused configured gate | passed |
| Full pytest collection | 325 collected, 0 errors |
| Full pytest | 320 passed, 5 skipped, 0 failed |
| P3 non-secret gate | 94 passed, 0 failed |
| Gated integration collection | 5 collected |
| Secret-free gated integrations | 5 expected skips, 0 failures |

The exact integration skip reason is `P3 Supabase integration tests are opt-in only`. No production, development, or validation Supabase endpoint was contacted.

## Archival exclusions and remaining debt

- `archive/` is excluded from active compile and Ruff gates because it contains the 30 documented placeholder `.py` files plus other historical material. No archival content was repaired or deleted.
- Repository-wide full-rule Ruff currently has 775 pre-existing findings across legacy and Data Fabric code. Enforcing it would require broad source refactoring and is outside Phase 2.
- Critical F82 analysis also identifies pre-existing undefined-name debt in `backup_unused/`, `test_env/`, and two findings in `services/recommendation_service.py`; these are not execution or collection blockers and were not changed.
- Bare repository-wide mypy remains non-reproducible under the current package/config layout and requires a separately scoped type-check baseline.
- Full tests retain three Pydantic v1 validator deprecation warnings. Local Windows execution also reports pytest-cache permission warnings; CI's clean Ubuntu workspace should not.
- Operational cron workflows have no pip cache or `pip check`; they install only their runtime-specific manifests. Adding operational preflight and deduplicating ingestion are later operational-hardening tasks.
- No Actions test artifact is retained.

## Authorization status

- CI certification: approved for the non-secret release-candidate baseline.
- Merge authorization: **not granted by this phase**.
- Tag authorization: **not granted by this phase**.
- Live Supabase authorization: not requested and not used.

Phase 3 documentation certification has not started.
