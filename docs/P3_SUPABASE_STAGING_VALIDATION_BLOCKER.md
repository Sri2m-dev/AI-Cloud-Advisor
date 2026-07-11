# P3 Supabase Staging Validation Blocker

## Status

P3.17 disposable Supabase staging validation is **BLOCKED** because no explicitly approved disposable Supabase test environment is configured in this shell.

No database operation was attempted.

## Baseline

| Item | Value |
| --- | --- |
| P3.16 certification merge baseline | `6a5fda09` |
| P3.17 branch | `feature/p3-supabase-staging-validation` |
| Safety gate outcome | `BLOCKED` |
| Runtime wiring | Disabled |

## Safety Gate Result

| Required item | Status |
| --- | --- |
| `P3_SUPABASE_RUN_INTEGRATION` | MISSING; exact accepted value is `1` |
| `P3_SUPABASE_TEST_URL` | MISSING |
| `P3_SUPABASE_TEST_SERVICE_ROLE_KEY` | MISSING |
| Explicit disposable/test project confirmation | MISSING |
| Production URL rejection check | NOT RUN; no URL configured |
| Unique test organization/tenant generation | AVAILABLE in tests, but not executed against a database |

## Reason For Stop

P3.17 validates real PostgreSQL and Supabase behavior. The phase requires a disposable or dedicated Supabase test project and server-side service-role credential. Running without explicit safe-test configuration would risk either false evidence or accidental execution against an unintended environment.

## Required Configuration Before Retry

Configure these names only in a local process environment or approved secret mechanism for a disposable or dedicated Supabase test project:

```text
P3_SUPABASE_RUN_INTEGRATION
P3_SUPABASE_TEST_URL
P3_SUPABASE_TEST_SERVICE_ROLE_KEY
```

The existing integration-test harness requires `P3_SUPABASE_RUN_INTEGRATION` to be explicitly set to `1`.

`P3_SUPABASE_TEST_URL` must identify the approved disposable or dedicated Supabase test project.

`P3_SUPABASE_TEST_SERVICE_ROLE_KEY` must be supplied only through the local process environment or an approved secret mechanism.

Secrets must never be committed.

See `docs/P3_SUPABASE_STAGING_VALIDATION_RUNBOOK.md` before resuming P3.17.

Before retry, confirm:

- the project is disposable or dedicated to P3 staging validation
- it is not production
- it is not an existing customer environment
- it is not the current Nexora production Supabase project
- migrations may be manually applied and the project may be reset if validation fails

## Work Not Performed

- No migration rehearsal was run.
- No migrations were applied.
- No Supabase RPC was executed.
- No repository integration test was run against a live database.
- No integration tests were executed against Supabase.
- No RLS or role certification was run.
- No performance baseline was run.
- No cleanup was needed.
- No runtime wiring was added.

## Pre-Flight Safety Assessment

Pre-flight inspection confirmed:

- the integration enable flag is exact and must be `1`
- missing P3 test URL or service-role key causes integration tests to skip before client construction
- integration tests use P3-specific variables and do not read normal application `SUPABASE_URL` or `SUPABASE_KEY`
- migrations are not executed by integration tests and must already exist before tests run
- no environment values were captured in this blocker document

Pre-flight inspection also found P3.17 remains blocked by safety gaps:

- only `tests/data_fabric/test_supabase_atomic_write_integration.py` rejects production-looking URLs in code
- the other Supabase integration helpers do not contain equivalent production-looking URL rejection
- write-based integration tests do not perform explicit row cleanup and rely on unique test-owned organization and tenant IDs

These gaps do not require a database connection to reproduce. Do not run live P3.17 integration tests until they are corrected or explicitly accepted for a disposable-only Supabase test project.

## Migration Assumption

Integration tests assume reviewed Data Fabric migrations `0001` through `0018` have already been applied manually to the disposable or dedicated Supabase test project. The repository does not provide an automatic P3 migration runner, and integration tests must not apply migrations.

## Resume Checklist

Before P3.17 can continue:

- [ ] Dedicated/disposable Supabase test project approved
- [ ] Runbook reviewed: `docs/P3_SUPABASE_STAGING_VALIDATION_RUNBOOK.md`
- [ ] Test URL configured
- [ ] Test service-role key configured server-side
- [ ] Explicit integration enable flag configured as `1`
- [ ] Target confirmed non-production
- [ ] Target confirmed non-customer
- [ ] Migrations `0001` through `0018` applied through an approved manual test-environment process
- [ ] RLS and privileged RPC grants verified
- [ ] Production-looking URL safeguard gap corrected or explicitly accepted for disposable-only validation
- [ ] Cleanup approach confirmed as test-owned-prefix cleanup or disposable project reset
- [ ] Canonical clean workspace in use
- [ ] Branch remains `feature/p3-supabase-staging-validation`

## Next Step

Operator action: provision and approve a disposable or dedicated Supabase test project, apply migrations `0001` through `0018` through the approved manual test-environment process, verify RLS/RPC grants, set only the P3 test environment variables locally, and resume using `docs/P3_SUPABASE_STAGING_VALIDATION_RUNBOOK.md`.
