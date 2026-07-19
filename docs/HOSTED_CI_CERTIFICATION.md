# P3.10 Hosted CI Certification

## Verdict

**PASS.** GitHub Actions executed the complete non-secret certification workflow successfully on the release-candidate branch.

## Tested candidate

- Branch: `feature/p3-supabase-live-validation`
- Commit: `5ff2e57195861b7cb1fcbac3f7804ce15db8768d`
- Workflow: `CI` (`.github/workflows/ci.yml`)
- Run ID: `29671495028`
- Job: `test`, ID `88151221351`
- Event: push
- Result: success
- Duration: 53 seconds
- Runner: `ubuntu-latest`
- Hosted Python: 3.11.15

## Workflow inventory and triggers

| Workflow | Trigger after correction | Hosted evidence |
|---|---|---|
| CI | Pushes to `main` and `feature/p3-supabase-live-validation`; all pull requests | Run `29671495028` succeeded on the feature branch |
| Background Jobs | Four schedules plus manual dispatch | Definition accepted; correctly did not run on feature push |
| CD | Pushes to `main` plus manual dispatch | Definition accepted; correctly did not run on feature push |
| Scheduled Ingestion | 30-minute schedule plus manual dispatch | Unchanged; not part of the correction |

Previous zero-job failures `29670127599` and `29670127794` were workflow configuration failures. After YAML/secret-expression correction, the same files no longer generated feature-push runs under filename-derived workflow names.

## Exact hosted results

| Step | Result |
|---|---|
| Checkout and Python setup | passed |
| Install all five dependency manifests | passed |
| `pip check` | passed — no broken requirements |
| Active compile/import | 1,095 compiled; representative imports passed |
| Ruff critical active-source gate | passed |
| Ruff focused repository-health gate | passed |
| Full collection | 325 collected |
| Full suite | 320 passed, 5 expected skips, 0 failed, 3 warnings |
| P3 non-secret gate | 94 passed |
| Gated integration collection | 5 collected |
| Secret-free integration execution | 5 expected skips |

Every job step completed successfully. No live Supabase credential was present and no live validation ran.

## Artifact status

GitHub Actions artifact count: 0. The workflow intentionally emits console certification evidence and does not upload a test artifact. Container images are outside this CI workflow and were not built or published by the Phase 5 hosted test.

## Hosted versus local comparison

| Measure | Local certified result | Hosted result |
|---|---:|---:|
| Python | 3.11.9 | 3.11.15 |
| Active compile | 1,095 passed | 1,095 passed |
| Full collection | 325 | 325 |
| Full execution | 320 passed, 5 skipped | 320 passed, 5 skipped |
| P3 gate | 94 passed | 94 passed |
| Gated integrations | 5 skipped | 5 skipped |
| Failures | 0 | 0 |

The Python patch-version difference is within the workflow’s certified 3.11 line and produced identical test totals.

## Warnings

- Three Pydantic v1 validator deprecation warnings remain documented debt.
- GitHub warns that Node.js 20-based action versions are being forced onto Node.js 24; this is non-blocking maintenance debt.
- A setup-python cache-related Git command warning was non-blocking; dependency installation and all gates passed.

## Operational workflow boundary

Background Jobs and CD were not manually dispatched. Background Jobs can invoke secret-backed provider and Supabase operations; CD can publish GHCR images and trigger deployments. Triggering them would exceed the no-runtime/no-database Phase 5 boundary. Valid configuration was demonstrated by GitHub accepting their intended trigger filters without zero-job feature-push failures.

