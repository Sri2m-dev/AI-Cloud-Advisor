# Route and Approval Consolidation Test Results

## Approval API and workflow tests

The route/API/customer-workflow/G08/job regression bundle, including the final
JWT-backed API test, recorded **56 passed, 0 failed** in 9.18 seconds.

The approval API test uses an isolated SQLite workflow repository and synthetic
tenant/customer identities. It exercises missing bearer denial, Finance → CIO
→ CEO sequencing, requester/approver separation, actor spoof denial, approval
history, evidence-linked export, tenant selector rejection, and tenant B
visibility denial. This is API-level evidence, not a browser or PostgreSQL
acceptance claim.

## PostgreSQL workflow qualification

Command:

```powershell
$env:NEXORA_CUSTOMER_WORKFLOW_LOCAL_PG = "1"
.\.venv\Scripts\python.exe -m pytest -q tests\customer_workflow\test_customer_workflow_postgres.py
```

Result: **4 passed, 0 failed, 149.82 seconds**. The suite ran against its
disposable local PostgreSQL qualification target. The tests cover the
synthetic customer journey with RLS/least privilege, fresh replay of the
current 43-input migration chain, concurrent approval/database-loss behavior,
and encrypted backup-package restore. Pytest exited successfully. Windows
emitted a non-fatal `PermissionError` from pytest's post-run temporary
directory cleanup callback; it occurred after the four tests passed and the
process returned exit code 0.

## Broader navigation regression

Result: **71 passed, 3 failed** in `tests/test_production_ga_navigation.py`.
The three failures are persona configuration assertions: the client-admin
persona declares 27 entries where the test expects 26, and its `Workspace`
section is not in the test's expected section taxonomy. Persona entry data was
not changed in this task. They remain unresolved and are not represented as a
green full regression.

## Local browser check

The local Streamlit root rendered the login page, and a direct unauthenticated
request to `/cloud_connections` returned HTTP 404. The app process was stopped
after the check. No authenticated browser journey was run; therefore browser
acceptance for the full V1 workflow and authenticated direct-URL denial remain
unverified.

## Coverage boundaries

- **API:** approval order, actor and tenant authorization, history, and export
  are covered with synthetic signed JWTs and an isolated SQLite repository.
- **PostgreSQL service:** four isolated persistence, RLS/recovery qualification
  tests passed; the exact subcases are in the test suite.
- **Streamlit browser:** only login rendering and unauthenticated direct-route
  denial were observed.
- **Hosted Supabase / production:** not accessed or modified.
- **G08:** existing integration checks passed in the targeted regression; owner
  operations remain fail-closed.
- **Static checks:** Ruff passed for the route/API files and import-order checks
  passed for the changed route/page/test files; `compileall` and Pylance syntax
  validation reported no Python syntax errors. Pylance returned
  `reportMissingImports` for `pytest` in the API test file, while the
  repository `.venv`-based pytest command executed the test successfully.
