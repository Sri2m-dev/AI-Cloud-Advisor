# P3.10 Phase 1 Repository Health Report

## Scope and verdict

Phase 1 restored repository-wide collection and test health without changing the certified Data Fabric baseline.

**Verdict: GREEN within the active repository scope.** Full collection succeeds, the complete executable suite passes with only the five expected opt-in Supabase skips, and the 94-test P3 gate remains green. The tracked archival placeholder files remain a documented repository-hygiene issue and were not modified.

## Baseline

- Branch: `feature/p3-supabase-live-validation`
- Starting commit: `67ceb65add12470efe396dce7a79a4a8511757a0`
- Ending commit: recorded by the Phase 1 commit containing this report
- Python: 3.11.9
- Database, Supabase, and live integration activity: none

## Root cause and disposition

`tests/services/test_sla_logic.py` imported `services.approval_service.calculate_sla_status`, but an approval-service rebuild removed that module-level symbol. Git history showed that the earlier implementation was only a compatibility placeholder returning `OK`; it did not calculate thresholds. The repository already contains the canonical 24/48/72-hour behavior in `core.workflows.sla_engine.SLAEngine`.

The correct disposition was to restore `calculate_sla_status` as a narrow service wrapper around `SLAEngine`. The wrapper retains the historical result shape, normalizes successful status names to uppercase, and returns structured failures for missing or invalid inputs. It does not duplicate SLA rules.

Full execution then revealed four related compatibility failures: the same rebuild had removed the tested module-level `approve_request` and `reject_request` entry points. Their minimal RBAC/result-shape compatibility wrappers were restored using the existing permission matrix. They do not access a database.

## Files changed

- `services/approval_service.py`
- `tests/services/test_sla_logic.py`
- `docs/REPOSITORY_HEALTH_PHASE1.md`

No Data Fabric contract, migration, RPC, adapter behavior, database object, CI workflow, or Supabase configuration changed.

## Dependency and import health

- Installed candidate `requirements-dev.txt` into the Python 3.11.9 environment.
- `pip check`: passed with no broken requirements.
- `psycopg2-binary`: 2.9.9.
- `import psycopg2`: passed.
- `import services.approval_service`: passed.
- Focused Python compile checks: passed.

Before the candidate development manifest was installed, collection also failed while importing `services.recommendation_service` because `psycopg2` was absent from the local environment. This was an environment drift issue, not a candidate-manifest defect: `requirements-dev.txt` declares `psycopg2-binary==2.9.9` and resolves it successfully.

## Tests

| Validation | Result |
|---|---:|
| Focused SLA service and canonical engine | 16 passed |
| Final focused approval-health suite | 20 passed |
| Full pytest collection | 325 collected, 0 errors |
| Full pytest execution | 320 passed, 5 skipped, 0 failed |
| Approved non-secret P3 gate | 94 passed, 0 failed |

The five full-suite skips are the expected secret-free, opt-in Supabase integrations. No live validation ran. Warnings comprise three Pydantic v1-validator deprecations and two local pytest-cache permission warnings; neither blocks collection or execution.

Focused coverage now includes exact 24-, 48-, and 72-hour boundaries, one-second-over overdue transitions, UTC `Z` and offset-aware timestamps, the historical missing-status behavior, missing timestamps, malformed timestamps, and non-mapping input.

## Archival placeholder classification

A read-only compile scan covered 1,239 tracked Python paths and found 30 syntax failures. All are line-one placeholder text (`...existing code from ...`) rather than Python, duplicated across two archival trees. No active runtime or test path is affected.

Each row below represents both listed prefixes, so every relative path identifies two affected files (30 total):

- `archive/AI-CLOUD-ADVISOR_BACKUP/backup 11-03-26/`
- `archive/backup 11-03-26/`

| Relative path (present under both prefixes) | Classification | Recommendation |
|---|---|---|
| `auth/login.py` | Placeholder, not source | Archival conversion |
| `config.py` | Placeholder, not source | Archival conversion |
| `database/db.py` | Placeholder, not source | Archival conversion |
| `pages/ai_advisor.py` | Placeholder, not source | Archival conversion |
| `pages/cost_explorer.py` | Placeholder, not source | Archival conversion |
| `pages/dashboard.py` | Placeholder, not source | Archival conversion |
| `pages/optimization.py` | Placeholder, not source | Archival conversion |
| `pages/reports.py` | Placeholder, not source | Archival conversion |
| `services/ai_recommender.py` | Placeholder, not source | Archival conversion |
| `services/aws_cost.py` | Placeholder, not source | Archival conversion |
| `services/finops_metrics.py` | Placeholder, not source | Archival conversion |
| `services/optimization_engine.py` | Placeholder, not source | Archival conversion |
| `utils/ai_recommender.py` | Placeholder, not source | Archival conversion |
| `utils/cost_loader.py` | Placeholder, not source | Archival conversion |
| `utils/finops_metrics.py` | Placeholder, not source | Archival conversion |

Recommended disposition is to convert these `.py` placeholders to a non-source archival format such as `.txt` or a manifest in a later, explicitly approved cleanup. Until then, compile/lint tooling should exclude the two named archival subtrees. Deletion should require a separate retention decision because the files are tracked as historical artifacts. Remediation into executable Python is not recommended because no implementation content exists.

## Remaining blockers and debt

- No active test or collection blocker remains.
- Thirty tracked archival placeholders are intentionally not valid Python.
- Three Pydantic v1 validator deprecation warnings should be handled in later repository maintenance.
- This workspace reports pytest-cache write warnings; tests themselves are unaffected.
- The previously recorded migration 0018 relationship-history deferral remains unchanged.

No merge, tag, architecture work, feature work, database operation, or frozen Data Fabric change occurred in Phase 1.
