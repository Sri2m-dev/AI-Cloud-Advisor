# NEXORA V1 Canonical Bootstrap — Test Results

## Focused regression run

Environment: repository `.venv`; disposable local PostgreSQL enabled only for
the customer-workflow PostgreSQL tests using
`NEXORA_CUSTOMER_WORKFLOW_LOCAL_PG=1`.

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp <session-local-basetemp> `
  tests/security/test_database_bootstrap_audit.py `
  tests/security/test_postgres_replay_harness.py `
  tests/security/test_production_tenant_provisioning.py `
  tests/auth/test_tenant_authorization_foundation.py `
  tests/customer_workflow/test_customer_workflow_environment_secrets.py `
  tests/customer_workflow/test_customer_workflow_service.py `
  tests/customer_workflow/test_customer_workflow_postgres.py `
  tests/financial_data_fabric/test_pvt003c1_financial_data_fabric.py `
  tests/financial_data_fabric/test_pvt003c1_dashboard_and_migration.py `
  tests/operations/test_recovery.py
```

**Final result: 172 passed, 0 failed, 0 skipped; 180.90 seconds.** This is the
focused suite listed above, not the full repository suite.

The bootstrap-audit file was also run independently after correcting the two
new October migration checksums and readiness-manifest pin: **15 passed**.
Those tests are included in the final 172-test run.

## Fresh-cluster bootstrap and workflow

`test_v1_customer_workflow_bootstraps_against_current_migration_chain` in
`tests/customer_workflow/test_customer_workflow_postgres.py` provisions a
fresh disposable PostgreSQL cluster and:

1. Applies the exact 43 current PostgreSQL migration inputs.
2. Verifies the test-only ledger contains all 43 paths and hashes.
3. Runs the chain a second time and verifies 43 safe ledger skips.
4. Executes an intentional failing transactional probe and confirms the probe
   object was rolled back.
5. Applies the existing synthetic customer-workflow PostgreSQL contract.
6. Starts `CustomerWorkflowService` from environment configuration.
7. Creates a workspace; uploads encrypted synthetic CSV evidence; runs bounded
   Ask; records a decision; records Finance, CIO, and executive approvals;
   creates an evidence-linked export; and resumes the workspace.
8. Verifies Customer B cannot list or resume Customer A's workspace.
9. Checks the stored evidence ciphertext does not contain the plaintext CSV or
   the workflow/evidence encryption keys.

The final integration assertion reports `migration_count=43`,
`idempotent_skips=43`, and `rollback_verified=true`.

## Other checks

- The guarded network-disabled test-only migration replay passed its catalog
  and synthetic tenant assertions, as recorded in
  [`CMP-P6-DEF-001/REPORT.md`](../../cmp/CMP-P6-DEF-001/REPORT.md).
- Ruff on the six changed Python source/test files: **passed**.
- Python `compileall` on those files: **passed**.
- `git diff --check`: **passed**.
- No complete full-repository test run was performed for this bootstrap task.

## Not validated

- Full Streamlit/FastAPI application startup against this database.
- Browser login and journey against this database.
- Hosted Supabase Auth, PostgREST, grants, or platform-managed roles.
- Every application route/repository against a complete application schema.
- A production migration runner or production rollback workflow.
- Cloud resources, external database targets, or production data.
