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
| `P3_SUPABASE_RUN_INTEGRATION` | MISSING |
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

## Resume Checklist

Before P3.17 can continue:

- [ ] Dedicated/disposable Supabase test project approved
- [ ] Test URL configured
- [ ] Test service-role key configured server-side
- [ ] Explicit integration enable flag configured
- [ ] Target confirmed non-production
- [ ] Target confirmed non-customer
- [ ] Canonical clean workspace in use
- [ ] Branch remains `feature/p3-supabase-staging-validation`

## Next Step

Retry P3.17 only after the disposable Supabase test environment is explicitly configured and approved.
