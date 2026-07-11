# P3 Supabase Staging Validation Runbook

## Purpose

This runbook prepares P3.17 disposable Supabase staging validation. It records the exact integration-test harness requirements and operator steps required before live validation can resume.

This document is pre-flight evidence only. It does not approve a database run, apply migrations, invoke RPCs, or change runtime wiring.

## Required Target

P3.17 requires a dedicated or disposable Supabase project approved only for P3 testing.

Prohibited targets:

- production Supabase projects
- customer environments
- the normal Nexora application Supabase environment
- any shared environment that cannot be reset after migration or test failure

## Workspace And Branch

```powershell
cd C:\Users\SrikanthMudaliar\AI-Cloud-Advisor-p3-clean
git status -sb
git branch --show-current
git log -1 --oneline
```

Expected branch:

```text
feature/p3-supabase-staging-validation
```

Current P3.17 blocker commit:

```text
95468119 docs: record P3 Supabase staging validation blocker
```

## Required Environment Variables

The existing integration-test harness accepts exactly this enable value:

```text
P3_SUPABASE_RUN_INTEGRATION=1
```

Required names:

```text
P3_SUPABASE_RUN_INTEGRATION
P3_SUPABASE_TEST_URL
P3_SUPABASE_TEST_SERVICE_ROLE_KEY
```

Safe local PowerShell configuration syntax:

```powershell
$env:P3_SUPABASE_RUN_INTEGRATION="1"
$env:P3_SUPABASE_TEST_URL="<DISPOSABLE_TEST_PROJECT_URL>"
$env:P3_SUPABASE_TEST_SERVICE_ROLE_KEY="<LOCAL_SECRET_VALUE>"
```

Secret-handling rules:

- Do not paste the service-role key into chat.
- Do not commit the service-role key.
- Do not add real values to `.env`, `.env.example`, `.streamlit/secrets.toml.example`, docs, tests, or migration files.
- Supply the key only through the local process environment or an approved secret mechanism.
- Do not print environment variable values during validation.

## Pre-Flight Verification Commands

Use presence-only checks. Do not print values.

```powershell
@(
  "P3_SUPABASE_RUN_INTEGRATION",
  "P3_SUPABASE_TEST_URL",
  "P3_SUPABASE_TEST_SERVICE_ROLE_KEY"
) | ForEach-Object {
  "$_: " + [bool][Environment]::GetEnvironmentVariable($_, "Process")
}
```

Confirm the enable flag exactly:

```powershell
if ($env:P3_SUPABASE_RUN_INTEGRATION -ne "1") {
  throw "P3 Supabase integration enable flag must be exactly 1"
}
```

Confirm the target is explicitly disposable or dedicated before any command that can touch Supabase.

## Integration-Test Inventory

| File | Coverage | Required env vars | Default skip behavior | Safety helper | Cleanup behavior | Migration prerequisite | Production-target safeguard |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `tests/data_fabric/test_supabase_entity_repository_integration.py` | `SupabaseEntityRepository`; entity create/get/find-by-source | `P3_SUPABASE_RUN_INTEGRATION`, `P3_SUPABASE_TEST_URL`, `P3_SUPABASE_TEST_SERVICE_ROLE_KEY` | Skips unless enable flag is exactly `1`; skips if URL/key missing | Local `_integration_config()` | No explicit cleanup; creates unique `org-it-*` and `tenant-it-*` records | Requires migrations `0001` through at least `0003`; full P3.17 should apply `0001` through `0018` first | No code-level production-looking URL rejection |
| `tests/data_fabric/test_supabase_relationship_history_integration.py` | `SupabaseRelationshipRepository`, `SupabaseVersionRepository`, `SupabaseLineageRepository`, `SupabaseProvenanceRepository` | Same three variables | Skips unless enable flag is exactly `1`; skips if URL/key missing | Local `_integration_client()` | No explicit cleanup; creates unique `org-rh-*` and `tenant-rh-*` records | Requires migrations `0001` through at least `0008`; full P3.17 should apply `0001` through `0018` first | No code-level production-looking URL rejection |
| `tests/data_fabric/test_supabase_governance_semantic_integration.py` | Governance/semantic client construction only | Same three variables | Skips unless enable flag is exactly `1`; skips if URL/key missing | Local `_client()` | No writes; no cleanup required | Requires configured Supabase client; semantic/ontology live scenarios would require `0009` through `0016` | No code-level production-looking URL rejection |
| `tests/data_fabric/test_supabase_atomic_write_integration.py` | Atomic canonical write harness and future entity/relationship bundle scenarios | Same three variables | Skips unless enable flag is exactly `1`; skips if URL/key missing | Local `_client()` plus `_unique_scope()` | Current smoke creates unique scope only; scenario tests skip after client safety check | Requires migrations `0001` through `0018` manually applied | Rejects URLs containing `prod` or `production` |

## Harness Safety Assessment

| Question | Assessment |
| --- | --- |
| Is the enable flag exact and unambiguous? | Yes. Every integration helper requires `P3_SUPABASE_RUN_INTEGRATION == "1"`. |
| Are missing credentials fail-closed? | Yes. Missing URL or key causes `pytest.skip` before client construction. |
| Is a production-looking URL rejected? | Partially. Only `test_supabase_atomic_write_integration.py` rejects URLs containing `prod` or `production`. The other three integration helpers do not. |
| Are credentials prevented from appearing in errors? | Partially. Tests do not print env values, and `DataFabricDatabaseConfig.__repr__` redacts the service-role key. Generic client errors may still include provider messages, so operators must not capture logs that expose secrets. |
| Are test tenant IDs unique? | Partially. Entity and relationship/history tests generate UUID-suffixed organization and tenant IDs. Atomic helper has `_unique_scope()`. Governance/semantic smoke creates no tenant or writes. |
| Is cleanup restricted to test-owned records? | No explicit cleanup exists. Write tests rely on unique test-owned organization and tenant prefixes to prevent collision but leave records in the disposable project. |
| Are migrations never automatically executed? | Yes. No integration test applies migrations. |
| Can integration tests accidentally target normal application Supabase variables? | Low risk by naming: tests use only `P3_SUPABASE_TEST_URL` and `P3_SUPABASE_TEST_SERVICE_ROLE_KEY`, not `SUPABASE_URL` or `SUPABASE_KEY`. However, they can still target any URL manually supplied under the P3 test variable names. |
| Does every integration test use equivalent safety gating? | No. Each file uses a local helper with equivalent opt-in and credential checks, but only the atomic-write helper has production-looking URL rejection. |

## Confirmed Safety Gaps

Pre-flight inspection found two reproducible safety gaps:

1. Production-looking URL rejection is not consistently enforced across all P3 Supabase integration helpers.
2. Write-based integration tests do not perform explicit cleanup; they rely on unique test-owned organization and tenant IDs and therefore require a disposable project that may be reset.

Smallest backward-compatible correction proposed for a later code task:

- move the common safety gate into one shared helper for all P3 Supabase integration tests
- require exact enable flag `1`
- require P3-specific URL/key variables
- reject production-looking URLs consistently
- generate UUID-suffixed organization and tenant scopes consistently
- add cleanup utilities limited to known P3 test-owned prefixes, or document project reset as the only cleanup mechanism

Do not run live P3.17 integration tests until those gaps are corrected or explicitly accepted for a disposable-only project.

## Migration Application Sequence

Apply migrations in this exact order before running integration tests:

1. `migrations/data_fabric/0001_create_data_fabric_schema.sql`
2. `migrations/data_fabric/0002_create_enterprise_entities.sql`
3. `migrations/data_fabric/0003_create_entity_update_rpc.sql`
4. `migrations/data_fabric/0004_create_enterprise_relationships.sql`
5. `migrations/data_fabric/0005_create_entity_versions.sql`
6. `migrations/data_fabric/0006_create_lineage_events.sql`
7. `migrations/data_fabric/0007_create_provenance_records.sql`
8. `migrations/data_fabric/0008_create_relationship_update_rpc.sql`
9. `migrations/data_fabric/0009_create_quality_assessments.sql`
10. `migrations/data_fabric/0010_create_ontology_concepts.sql`
11. `migrations/data_fabric/0011_create_ontology_relationships.sql`
12. `migrations/data_fabric/0012_create_semantic_mappings.sql`
13. `migrations/data_fabric/0013_create_idempotency_records.sql`
14. `migrations/data_fabric/0014_create_ontology_update_rpcs.sql`
15. `migrations/data_fabric/0015_create_semantic_mapping_update_rpc.sql`
16. `migrations/data_fabric/0016_create_idempotency_state_rpcs.sql`
17. `migrations/data_fabric/0017_create_atomic_entity_write_rpc.sql`
18. `migrations/data_fabric/0018_create_atomic_relationship_write_rpc.sql`

## Supported Manual Migration Mechanism

The repository does not provide or document a Supabase CLI, `psql`, or Python migration runner for P3 Data Fabric migrations.

The currently supported mechanism is the one documented in `migrations/data_fabric/README.md`: apply reviewed SQL artifacts through an approved deployment or test-environment migration process. For P3.17, that process must target only the approved disposable or dedicated Supabase test project.

Do not introduce a new migration runner during P3.17 pre-flight.

## Migration Evidence To Capture

Capture evidence outside repository files unless the next task explicitly requests a committed report:

- target project confirmation as disposable or dedicated
- list of migration filenames applied in order
- start and completion timestamp
- executor identity or approved migration mechanism
- success or failure status for each migration
- screenshots or copied SQL output with no secret values
- reset/backup evidence for the disposable project

## Schema Verification Steps

After migrations are applied, verify through the approved database console or SQL mechanism:

- schema `data_fabric` exists
- all P3 tables from migrations `0002` through `0013` exist
- append-only triggers exist for entity versions, lineage, provenance, and quality assessments
- tenant-scoped unique constraints exist for current-state tables and idempotency records
- indexes on organization and tenant columns exist

## RLS Verification Steps

Verify:

- RLS is enabled on all Data Fabric tables
- no anonymous policies grant broad access
- service-role validation is server-side only
- repository tests still use explicit organization and tenant filters

## RPC And Grant Verification Steps

Verify RPC availability and grants for:

- `data_fabric_update_enterprise_entity`
- `data_fabric_update_enterprise_relationship`
- ontology update RPCs
- semantic mapping update RPC
- idempotency state RPCs
- `data_fabric_atomic_entity_write`
- `data_fabric_atomic_relationship_write`

Verify privileged RPCs:

- use `SECURITY DEFINER`
- set `search_path = data_fabric, pg_temp`
- revoke execute from `PUBLIC`
- grant execute to `service_role`

## Integration-Test Execution Order

Run only after the disposable target, migrations, RLS, and RPC grants are verified.

Recommended order:

```powershell
python -m pytest tests/data_fabric/test_supabase_entity_repository_integration.py -q
python -m pytest tests/data_fabric/test_supabase_relationship_history_integration.py -q
python -m pytest tests/data_fabric/test_supabase_governance_semantic_integration.py -q
python -m pytest tests/data_fabric/test_supabase_atomic_write_integration.py -q
```

Full integration suite command:

```powershell
python -m pytest tests/data_fabric/test_supabase_*_integration.py -q
```

Atomic RPC validation command:

```powershell
python -m pytest tests/data_fabric/test_supabase_atomic_write_integration.py -q
```

Current limitation: atomic entity and relationship bundle scenario tests intentionally skip after confirming the safe Supabase client gate. Full scenario implementation remains deferred until a disposable database has migrations applied and the test cases are expanded.

## Cleanup Expectations

Current integration tests do not perform explicit row cleanup.

Cleanup must be handled by one of:

- resetting the disposable Supabase test project
- deleting only records whose organization and tenant IDs carry the test-owned prefixes generated by the harness
- restoring the disposable test project from a pre-validation backup

Never run broad cleanup against production, customer, or normal application environments.

## Post-Test Secret Cleanup

Remove P3 test values from the PowerShell session after validation:

```powershell
Remove-Item Env:P3_SUPABASE_RUN_INTEGRATION
Remove-Item Env:P3_SUPABASE_TEST_URL
Remove-Item Env:P3_SUPABASE_TEST_SERVICE_ROLE_KEY
```

## Stop Conditions

Stop without running integration tests if any of these are true:

- target project is not explicitly approved as disposable or dedicated
- target might be production, customer, or the normal Nexora application environment
- any required env var is missing
- enable flag is not exactly `1`
- migration `0001` through `0018` has not been applied successfully
- RLS status cannot be verified
- RPC grants cannot be verified
- logs or errors expose credential material
- operator cannot prove cleanup is restricted to test-owned records or project reset
- the inconsistent production-looking URL safeguard has not been corrected or explicitly accepted for a disposable-only target

