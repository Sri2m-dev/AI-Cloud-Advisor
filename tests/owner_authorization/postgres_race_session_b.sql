-- UNEXECUTED. Same disposable fixture as A; installer/test authority only.
-- psql variables auth_id and execution_assertion_id reference the authorization
-- and a distinct EXECUTION assertion bound to this actual session principal.
\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL READ COMMITTED;
SET LOCAL lock_timeout='15s';
-- Must wait for A, then reject fresh state with SQLSTATE 42501. Invoke under a
-- harness that expects this error and issues ROLLBACK (ON_ERROR_STOP stops psql).
SELECT public.g08_owner_decision_time(:'auth_id'::uuid,:'execution_assertion_id'::uuid);
ROLLBACK;
