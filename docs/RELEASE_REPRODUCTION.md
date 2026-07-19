# P3.10 Phase 0 Release Reproduction

## Verdict

**REPRODUCIBLE.** The published release candidate was cloned from `origin`, checked out at the exact expected commit, installed from every declared dependency manifest in a new Python 3.11.9 virtual environment, and passed the approved non-secret P3 release gate. No live Supabase validation ran.

## Repository evidence

| Item | Result |
|---|---|
| Canonical path | `C:\Users\SrikanthMudaliar\AI-Cloud-Advisor-p3-clean` |
| Branch | `feature/p3-supabase-live-validation` |
| Candidate commit | `273db69cb34e559bd339174925bdfd4bc4847d75` |
| Origin | `https://github.com/Sri2m-dev/AI-Cloud-Advisor.git` |
| Push | Successful; `Everything up-to-date` |
| Remote branch | `refs/heads/feature/p3-supabase-live-validation` |
| Remote commit | `273db69cb34e559bd339174925bdfd4bc4847d75` |
| Fresh-clone path | `C:\Users\SrikanthMudaliar\AI-Cloud-Advisor-p3-release-validation-273db69c` |
| Fresh-clone HEAD | `273db69cb34e559bd339174925bdfd4bc4847d75` |
| Fresh-clone worktree | Clean |

This evidence was committed as `67ceb65add12470efe396dce7a79a4a8511757a0`. Later certification commits do not alter the historical fresh-clone result recorded here.

The branch was pushed normally. No rebase, amend, force push, merge, or tag was performed.

## Runtime and dependencies

- Python: 3.11.9
- Virtual environment: new `.venv` in the fresh clone
- Secrets and custom configuration: not used
- `P3_SUPABASE_RUN_INTEGRATION`, `P3_SUPABASE_TEST_URL`, and `P3_SUPABASE_TEST_SERVICE_ROLE_KEY`: explicitly absent during validation
- Installed distributions: 130

Every dependency manifest declared by the candidate was installed:

- `requirements.txt`
- `requirements-dev.txt`
- `requirements-prod.txt`
- `requirements.frontend.txt`
- `backend/requirements.txt`

`pip check` passed with `No broken requirements found`. Representative imports passed for `data_fabric`, persistence models, the Supabase atomic-write adapter, `pytest`, `mypy`, `ruff`, `psycopg2`, `supabase`, `streamlit`, `fastapi`, and `celery`.

No `.env` containing local values was used. The documented `.env.example` remains the configuration reference; placeholder configuration was not needed for the non-secret checks.

## Commands and validation scope

The reproduction used a single-branch remote clone, created a new virtual environment, installed all five manifests, ran `pip check`, compiled Git-tracked active Data Fabric Python sources, imported representative runtime and development modules, and ran:

```text
python -m pytest -q \
  tests/data_fabric/test_supabase_integration_safety.py \
  tests/data_fabric/test_supabase_atomic_write_unit.py \
  tests/data_fabric/test_persistence_foundation.py \
  tests/data_fabric/test_persistence_certification.py \
  tests/data_fabric/test_supabase_adapter_structure.py

python -m pytest --collect-only -q \
  tests/data_fabric/test_supabase_entity_repository_integration.py \
  tests/data_fabric/test_supabase_relationship_history_integration.py \
  tests/data_fabric/test_supabase_governance_semantic_integration.py \
  tests/data_fabric/test_supabase_atomic_write_integration.py

python -m pytest -q -rs <the same four integration modules>
```

## Compile and import results

- Git-tracked active Data Fabric and Data Fabric test files compiled: 119
- Syntax failures: 0
- Representative import failures: 0
- Dependency-resolution failures: 0

The scan intentionally covered active `data_fabric/` and `tests/data_fabric/` code. Repository-health work, including `calculate_sla_status`, is outside Phase 0 and was neither modified nor investigated as a fix.

## Exact test results

| Gate | Passed | Failed | Skipped | Collected |
|---|---:|---:|---:|---:|
| Approved non-secret P3 gate | 94 | 0 | 0 | 94 |
| Gated integrations, collection only | - | - | - | 5 |
| Gated integrations, secret-free execution | 0 | 0 | 5 | 5 |

The 94-test gate comprises the hardened safety suite, atomic adapter unit tests, persistence foundation and certification tests, and Supabase adapter structure tests. All five integration tests skipped for the exact expected reason: `P3 Supabase integration tests are opt-in only`.

No live Supabase request, database read, RPC, write, migration, grant, RLS change, API-setting change, or cleanup operation occurred.

## Comparison with release evidence

Compared with `docs/P3_SUPABASE_LIVE_VALIDATION_CHECKPOINT.md` and `docs/P3_DATA_FABRIC_RELEASE_GATE.md`:

- Python 3.11.9 matches.
- Hardened safety coverage and the approved aggregate non-secret gate match the recorded release-candidate scope.
- The candidate produces 94 passed, 0 failed, and no unexpected skips.
- All five gated integrations collect successfully and produce the five expected opt-in skips when executed without secrets.
- Live Supabase results were not reproduced by design; their durable evidence and database-operation counts remain documented in the live-validation checkpoint.
- The reproduced hardened candidate is `273db69c...`; later commits add certification evidence and the repository-health/CI corrections documented by subsequent phase reports.
- Relationship-version history remains the documented migration 0018 deferred behavior.

No unexplained difference was observed in the approved Phase 0 scope.

## Worktree and governance status

- Fresh clone: clean after validation (`.venv` is ignored).
- Canonical repository: source tree unchanged; only this report is untracked.
- Report: updated, not staged, and not committed.
- Source code, CI, migrations, grants, RLS, Supabase configuration, and runtime behavior: unchanged.
- Merge: not performed.
- Tag: not created.
- Phase 1 repository-health work: not started.
