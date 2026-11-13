# M0 - exact verification command inventory

Commands below are identified from existing workflows and test files. NONE was run during M0. They are not permission to connect, execute SQL, start containers, dispatch workflows, publish images or deploy. M0 itself used only repository metadata/static reads and documentation generation/integrity checks.

## Existing CI commands

Python 3.11. Working directory: repository root. Shell: workflow bash or PowerShell equivalents. Install only in a later authorized isolated environment:

```text
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt -r requirements-prod.txt -r requirements.frontend.txt -r backend/requirements.txt
python -m pip check
ruff check . --exclude archive --select E9,F63,F7
ruff check services/approval_service.py tests/services/test_sla_logic.py
python -m pytest --collect-only -q
python -m pytest -q
```

CI additionally compiles Git-tracked `.py` outside `archive/` with Python `compile()` then imports `data_fabric`, `psycopg2`, `services.approval_service` and the atomic-write adapter. Exact source is `.github/workflows/ci.yml`. Its tracked-file enumeration does not certify today's untracked candidate files; freeze/include them before exact-candidate certification.

For full execution and gated integration skip checks, CI sets these three variables to empty strings: `P3_SUPABASE_RUN_INTEGRATION`, `P3_SUPABASE_TEST_URL`, `P3_SUPABASE_TEST_SERVICE_ROLE_KEY`. Never populate these as part of M0/M1 offline checks.

```text
python -m pytest -q tests/data_fabric/test_supabase_integration_safety.py tests/data_fabric/test_supabase_atomic_write_unit.py tests/data_fabric/test_persistence_foundation.py tests/data_fabric/test_persistence_certification.py tests/data_fabric/test_supabase_adapter_structure.py
python -m compileall -q data_fabric tests/data_fabric
python -m pytest --collect-only -q tests/data_fabric/test_supabase_entity_repository_integration.py tests/data_fabric/test_supabase_relationship_history_integration.py tests/data_fabric/test_supabase_governance_semantic_integration.py tests/data_fabric/test_supabase_atomic_write_integration.py
python -m pytest -q -rs tests/data_fabric/test_supabase_entity_repository_integration.py tests/data_fabric/test_supabase_relationship_history_integration.py tests/data_fabric/test_supabase_governance_semantic_integration.py tests/data_fabric/test_supabase_atomic_write_integration.py
```

Expected integration behavior without opt-in: skip with recorded reason. No fixed full-suite count is promised. Every skip must be classified for the exact candidate. Collection/import is code execution; review its side effects before a future run. Full tests may execute local SQL and are not authorized by this M0 instruction.

## Existing targeted test modules

These proposed combinations use existing files, not new tests or historical pass claims:

```text
python -m pytest -q -p no:cacheprovider tests/security/test_streamlit_auth_isolation.py tests/security/test_connector_context_tenant_guard.py tests/security/test_tenant_scoped_data_access.py
python -m pytest -q -p no:cacheprovider tests/security/test_api_user_store.py tests/security/test_api_auth_tenant_authorization.py tests/security/test_token_store_revocation_contract.py tests/security/test_jwt_secret_policy.py
python -m pytest -q -p no:cacheprovider tests/security/test_production_tenant_provisioning.py tests/security/test_database_bootstrap_audit.py
python -m pytest -q -p no:cacheprovider tests/release
python -m pytest -q -p no:cacheprovider backend/tests/test_security_api.py backend/tests/test_governance_rbac.py
python -m pytest -q -p no:cacheprovider tests/executive_experience/test_customer_journey_ux.py
```

Backend tests are outside default `testpaths=["tests"]`; invoke explicitly when the API is in scope. Existing tests do not yet prove future L06/L09/L13 fixes. Add only focused behavioral tests for those changes during M1.

Do not run `tests/financial_data_fabric/test_nxr_dash_10_postgres.py` with `NXR_DASH10_LOCAL_PG=1`, opt-in disposable database suites, `scripts/test_only_postgres_replay.py`, staging validators/replay tests or live integration opt-ins under M0. They can create runtimes/execute SQL. Inspect and authorize their later scope separately; preserve existing guards.

## Existing workflows

| Workflow | Existing trigger/behavior | Release implication |
|---|---|---|
| `.github/workflows/ci.yml` | Push to main and named feature branches; pull requests; Python dependencies, compile/import, lint, full tests and gated skips | Need exact-candidate run plus retained results; no live certification implied |
| `.github/workflows/cd.yml` | Main push/manual; matrix builds/pushes five images to GHCR; SHA and latest; optional deployment webhook per image | NOT a verification command; do not trigger; L09 must gate promotion and coherent service release |
| `.github/workflows/background-jobs-cron.yml` | Scheduled/manual jobs with operational secrets | No dispatch; reconcile duplicate scheduling and tenant coverage before activation |
| `.github/workflows/ingestion-cron.yml` | Every 30 minutes/manual; provider sync entry points | No dispatch; live providers outside initial release activation |

CD has no explicit CI dependency or deployment-readiness proof in its current source. Remote workflows, branch protection and secrets availability were not queried.

## Target prerequisites and later verification

- Approved target/container host; region, operating budget and operators.
- DNS/domain control; TLS termination and renewal; secure proxy/WebSocket behavior.
- `ENVIRONMENT=production`; accepted Auth configuration; managed JWT/API configuration only if API enabled; public-key UI login and bounded backend secrets.
- Durable Universal Evidence database AND encrypted prospect file path; stable managed encryption key and separate key recovery; single-node topology unless shared storage is separately certified.
- Exact accepted database chain, G08 implementation, Auth/RLS/role/API qualification and target identity. No migration invocation is included here.
- Dependency readiness beyond `/health`; restricted metrics, genuine Prometheus scraping and delivered alerts; monitoring defaults must not be public.
- Backup coverage: database, encrypted source files, configuration references, application artifacts and key recovery. Restore verification must use a separately authorized safe target; no restoration access occurs in M0.
- Supported upload/workload/latency limits, availability, RPO/RTO and retention must be recorded before M5.
- Exactly one scheduler per enabled job; workers/beat and GitHub cron are not automatically accepted by their presence.
- Browser evidence must include real rendered functionality, role/tenant denial, restart/resume and commit acknowledgement; HTTP 200/liveness alone is not sufficient.

No usable target, TLS certificate, external provider credential, backup or live role is inferred from an environment variable name or repository document.
