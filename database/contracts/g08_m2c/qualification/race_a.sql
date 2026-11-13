-- UNEXECUTED. Run after race_setup, concurrently with B in the same local fixture.
\set ON_ERROR_STOP on
\ir local_guard.sql
BEGIN ISOLATION LEVEL READ COMMITTED;
SELECT public.g08_lock_identity_history();
SELECT public.g08_stage_owner_status('a0000000-0000-0000-0000-000000000001',
 'e0000000-0000-0000-0000-000000000002','REVOKED','e0000000-0000-0000-0000-000000000001',
 'd0000000-0000-0000-0000-000000000002','fixture-revocation','fixture rationale');
SELECT pg_sleep(10);
COMMIT;
