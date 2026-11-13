-- UNEXECUTED: run during session A's lock hold in authorized disposable DB only.
\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL READ COMMITTED;
SET LOCAL lock_timeout='15s';
SELECT public.g08_lock_identity_history();
-- Must return after A commits. Inspect pg_locks from a separate authorized session.
SELECT public.g08_assert_identity_history(), pg_catalog.clock_timestamp();
COMMIT;
-- Separately run BEGIN ISOLATION LEVEL REPEATABLE READ; SELECT
-- public.g08_lock_identity_history(); expect SQLSTATE 25001, then ROLLBACK.
-- This lock smoke test alone does NOT prove post-wait authority freshness.
