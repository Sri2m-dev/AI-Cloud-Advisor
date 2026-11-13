-- UNEXECUTED. Safe transaction recovery probe: no destructive down migration.
BEGIN ISOLATION LEVEL READ COMMITTED;
SELECT public.g08_lock_identity_history();
SAVEPOINT incomplete_work;
-- A failed controlled RPC must not leave a partially committed mutation.
DO $$ BEGIN
 BEGIN
  PERFORM public.g08_control_owner_operation('EXECUTION','{}');
  RAISE EXCEPTION 'unexpected owner execution acceptance';
 EXCEPTION WHEN object_not_in_prerequisite_state THEN NULL;
 END;
END $$;
ROLLBACK TO SAVEPOINT incomplete_work;
SELECT public.g08_assert_identity_history();
SELECT public.g08_assert_owner_history();
ROLLBACK;
