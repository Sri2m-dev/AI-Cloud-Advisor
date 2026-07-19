# P3 Supabase Staging Validation Blocker

Status: **Resolved historical blocker.** The final dedicated-project outcome is recorded in `P3_SUPABASE_LIVE_VALIDATION_CHECKPOINT.md`.

## Status

P3.17 disposable Supabase staging validation is **BLOCKED** because no explicitly approved disposable Supabase test environment is configured in this shell.

No database operation was attempted.

Latest validation-gate attempt: `2026-07-12T05:56:22Z`.

## Baseline

| Item | Value |
| --- | --- |
| P3.17A safety-hardening merge baseline | `17e0d0fb merge: harden P3 Supabase staging validation safety` |
| P3.17 validation branch | `feature/p3-supabase-live-validation` |
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
| Target URL accepted | NO; no URL configured |
| Test target classified as approved disposable/dedicated | NO; no target configured |
| Redacted project reference | `UNAVAILABLE` |
| Unique test organization/tenant generation | AVAILABLE in tests, but not executed against a database |

Local safety-helper result:

```text
SAFETY_GATE_ATTEMPT=local_config_resolution_only
SAFETY_GATE_RESULT=BLOCKED
SAFETY_GATE_REASON=P3 Supabase integration tests are opt-in only
```

## Reason For Stop

P3.17 validates real PostgreSQL and Supabase behavior. The phase requires a disposable or dedicated Supabase test project and server-side service-role credential. Running without explicit safe-test configuration would risk either false evidence or accidental execution against an unintended environment.

## Required Configuration Before Retry

Create and explicitly approve a disposable or dedicated Supabase test project for Nexora P3 validation. Then configure these names only in the local PowerShell process used by Codex or an approved secret mechanism:

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

Safety defects identified during pre-flight:

- inconsistent URL rejection
- missing explicit cleanup

Safety-hardening status:

- merged to `main` at `17e0d0fb`
- shared fail-closed helper added for all P3 Supabase integration tests
- exact enable value remains `1`
- application Supabase env vars are not used as fallback
- layered unsafe-target rejection is applied before client construction
- test-owned identifiers use the `p3test-` prefix plus UUID suffixes
- cleanup is scoped by both `organization_id` and `tenant_id`
- cleanup refuses non-test tenants

These corrections do not change the overall P3.17 status. Live Supabase validation remains blocked until the disposable environment is approved and configured.

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
- [ ] P3.17A safety-hardening validation passed and committed
- [ ] Cleanup approach confirmed as scoped test-owned-prefix cleanup or disposable project reset
- [ ] Canonical clean workspace in use
- [ ] Branch remains `feature/p3-supabase-live-validation`

## Next Step

Operator action: provision and approve a disposable or dedicated Supabase test project, set only the P3 test environment variables locally, and resume using `docs/P3_SUPABASE_STAGING_VALIDATION_RUNBOOK.md`. Do not share the service-role key in chat.
