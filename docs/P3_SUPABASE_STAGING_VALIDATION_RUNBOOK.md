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
| `tests/data_fabric/test_supabase_entity_repository_integration.py` | `SupabaseEntityRepository`; entity create/get/find-by-source | `P3_SUPABASE_RUN_INTEGRATION`, `P3_SUPABASE_TEST_URL`, `P3_SUPABASE_TEST_SERVICE_ROLE_KEY` | Skips unless enable flag is exactly `1`; skips if URL/key missing | Shared `client_or_skip()` from `supabase_integration_safety.py` | `try/finally` scoped cleanup for `p3test-` organization and tenant | Requires migrations `0001` through at least `0003`; full P3.17 should apply `0001` through `0018` first | Shared layered unsafe-target rejection before client construction |
| `tests/data_fabric/test_supabase_relationship_history_integration.py` | `SupabaseRelationshipRepository`, `SupabaseVersionRepository`, `SupabaseLineageRepository`, `SupabaseProvenanceRepository` | Same three variables | Skips unless enable flag is exactly `1`; skips if URL/key missing | Shared `client_or_skip()` from `supabase_integration_safety.py` | `try/finally` scoped cleanup for `p3test-` organization and tenant | Requires migrations `0001` through at least `0008`; full P3.17 should apply `0001` through `0018` first | Shared layered unsafe-target rejection before client construction |
| `tests/data_fabric/test_supabase_governance_semantic_integration.py` | Governance/semantic client construction only | Same three variables | Skips unless enable flag is exactly `1`; skips if URL/key missing | Shared `client_or_skip()` from `supabase_integration_safety.py` | No writes; no cleanup required | Requires configured Supabase client; semantic/ontology live scenarios would require `0009` through `0016` | Shared layered unsafe-target rejection before client construction |
| `tests/data_fabric/test_supabase_atomic_write_integration.py` | Atomic canonical write harness and future entity/relationship bundle scenarios | Same three variables | Skips unless enable flag is exactly `1`; skips if URL/key missing | Shared `client_or_skip()` and test-owned ID helpers from `supabase_integration_safety.py` | Current smoke creates unique scope only; scenario tests skip after client safety check | Requires migrations `0001` through `0018` manually applied | Shared layered unsafe-target rejection before client construction |

## Harness Safety Assessment

| Question | Assessment |
| --- | --- |
| Is the enable flag exact and unambiguous? | Yes. The shared helper requires `P3_SUPABASE_RUN_INTEGRATION == "1"`. |
| Are missing credentials fail-closed? | Yes. Missing URL or key causes `pytest.skip` before client construction. |
| Is a production-looking URL rejected? | Yes as a layered safeguard. The shared helper rejects malformed URLs, localhost, configured prohibited targets, the normal application Supabase URL when detectable, and production-looking host/path values. |
| Are credentials prevented from appearing in errors? | Partially. Tests do not print env values, and `DataFabricDatabaseConfig.__repr__` redacts the service-role key. Generic client errors may still include provider messages, so operators must not capture logs that expose secrets. |
| Are test tenant IDs unique? | Yes for write tests. Test-owned identifiers use the `p3test-` prefix and UUID suffixes for organization, tenant, canonical, source, idempotency, and correlation IDs where applicable. |
| Is cleanup restricted to test-owned records? | Yes. Cleanup refuses non-`p3test-` organization or tenant IDs and applies both filters to each table delete. |
| Are migrations never automatically executed? | Yes. No integration test applies migrations. |
| Can integration tests accidentally target normal application Supabase variables? | Low risk by naming: tests use only `P3_SUPABASE_TEST_URL` and `P3_SUPABASE_TEST_SERVICE_ROLE_KEY`, not `SUPABASE_URL` or `SUPABASE_KEY`. However, they can still target any URL manually supplied under the P3 test variable names. |
| Does every integration test use equivalent safety gating? | Yes. All four P3 Supabase integration files use `tests/data_fabric/supabase_integration_safety.py`. |

## Safety-Hardening Status

Pre-flight inspection found two reproducible safety gaps:

1. Production-looking URL rejection is not consistently enforced across all P3 Supabase integration helpers.
2. Write-based integration tests do not perform explicit cleanup; they rely on unique test-owned organization and tenant IDs and therefore require a disposable project that may be reset.

P3.17A corrects those gaps on branch `feature/p3-supabase-staging-validation`:

- common safety gate moved into `tests/data_fabric/supabase_integration_safety.py`
- exact enable flag remains `1`
- only P3-specific URL/key variables are read for connection configuration
- application Supabase env vars are not used as fallback
- unsafe-target rejection is applied before client construction
- test-owned identifiers use the `p3test-` prefix plus UUID suffixes
- cleanup is scoped to test-owned organization and tenant IDs
- cleanup refuses non-test tenants and never truncates or drops objects

This safeguard is layered, not perfect generic production detection. An explicitly approved disposable or dedicated Supabase project remains mandatory.

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

Write-based integration tests use explicit scoped cleanup for test-owned tenant data.

Cleanup table order:

1. `idempotency_records`
2. `semantic_mappings`
3. `ontology_relationships`
4. `ontology_concepts`
5. `quality_assessments`
6. `provenance_records`
7. `lineage_events`
8. `entity_versions`
9. `enterprise_relationships`
10. `enterprise_entities`

Cleanup rules:

- organization and tenant IDs must both start with `p3test-`
- every delete must include both `organization_id` and `tenant_id`
- cleanup never truncates
- cleanup never drops objects
- cleanup failures are surfaced
- cleanup reports counts only

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
