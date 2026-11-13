-- UNEXECUTED: authorized disposable PostgreSQL only, concurrent with session B.
-- Use a session without any pre-existing transaction or locks.
\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL READ COMMITTED;
SELECT public.g08_lock_identity_history();
-- Manually start B while A holds this transaction; B must wait here until COMMIT.
SELECT pg_catalog.pg_sleep(10);
COMMIT;
