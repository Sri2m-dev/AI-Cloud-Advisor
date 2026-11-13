# NEXORA V1 Final Dependency Closure — Regression Results

Run date: 2026-11-13  
All test data was synthetic. PostgreSQL cases created fresh temporary local
clusters; no existing PostgreSQL, Docker, cloud, or Supabase resource was used.

## Test results

| Scope | Command / files | Result |
|---|---|---:|
| Navigation, route policy, direct API denial, operations job guards | `tests/test_production_ga_navigation.py`, `tests/security/test_v1_route_enforcement.py`, `tests/operations/test_health_and_jobs.py`, `tests/operations/test_runtime_and_config.py` | **69 passed, 0 failed** |
| Customer workflow service, approval API, environment secrets, original schema-contract guard | `tests/customer_workflow/test_customer_workflow_service.py`, `tests/customer_workflow/test_customer_workflow_approvals_api.py`, `tests/customer_workflow/test_customer_workflow_environment_secrets.py`, `tests/security/test_current_application_schema_contract.py` | **15 passed, 0 failed** |
| Canonical application portfolio and P1 financial source/read models | `tests/application_portfolio/test_canonical_reads.py`, `tests/services/test_financial_read_models.py`, `tests/financial_data_fabric/test_pvt003c1_financial_data_fabric.py` | **29 passed, 0 failed** |
| Enterprise Registry canonical-source behavior and V1 legacy-read denial | `tests/enterprise_registry/test_canonical_data_fabric_reader.py` | **6 passed, 0 failed** |
| Fresh PostgreSQL workflow, canonical migration replay, RLS, recovery, least privilege | `tests/customer_workflow/test_customer_workflow_postgres.py` with `NEXORA_CUSTOMER_WORKFLOW_LOCAL_PG=1` | **4 passed, 0 failed, 0 skipped** |

Across these distinct test selections: **123 passed, 0 failed, 0 skipped**.
The latest PostgreSQL run took 167.96 seconds and exercised a new temporary
PostgreSQL 18 cluster. It covered the applicable migration replay, customer workflow,
Finance → CIO → executive approvals, export, A/B tenant isolation, JWT and
runtime authorization negatives, persistence/recovery, and restoration.

The FastAPI approval tests provide API-level evidence. The PostgreSQL
customer-workflow suite provides service/database evidence. They are separate
test environments and are not represented as one end-to-end browser run.

## Browser and acceptance boundary

The existing browser page at `http://127.0.0.1:8567/` reported that the
Streamlit server was not responding and that `/_stcore/health` could not be
reached. No authenticated browser login or full interactive journey was run.
There were no synthetic browser credentials available in that browser session.
Direct deferred-page denial is verified at application page registration; it
is not claimed as browser-level HTTP evidence.

## Static validation

- `py_compile` passed for the modified Python source and test files.
- `git diff --check` passed for the changed implementation files.
- Unfiltered Ruff on the changed-file set remains non-clean because of
  pre-existing import-order and compact-style findings in existing operational
  and test files. The first run exposed one overlong line in a newly added test;
  that line was split. No broad formatting cleanup was made to unrelated
  existing code.
- The V1 Enterprise Registry tests prove that the configured V1 composition
  uses the canonical Data Fabric source and does not merge legacy rows. This is
  service-level evidence only: the operations frontend receives the anon key,
  while the service-role secret is mounted only in the API container. The
  direct frontend reader therefore remains unqualified for production and must
  not be given the service-role secret.

## Negative and failure-path evidence

- Both FastAPI applications return 404 for direct `/api/v1/cost` requests.
- Direct page-spec tests deny Cost Intelligence, Dependency Analysis, and
  Technology Digital Twin even when a role map is supplied.
- V1 worker/beat startup is rejected; V1 schedule construction is empty; a
  manually allowlisted queued legacy task is refused before its body runs.
- Existing PostgreSQL tests cover failed authorization, invalid/tampered JWT,
  tenant spoofing, cross-tenant workspace/evidence/approval/export denial,
  concurrent approval, database loss/recovery, and encrypted restore.
- This run did not perform a full Streamlit browser test or an independent
  off-host recovery drill.
