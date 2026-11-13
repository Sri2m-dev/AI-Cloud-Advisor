\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL READ COMMITTED;
SELECT public.g08_lock_identity_history();
SELECT pg_sleep(10);
COMMIT;
