-- UNEXECUTED. Start while A sleeps; assert wait + fresh terminal-state denial.
\set ON_ERROR_STOP on
\ir local_guard.sql
BEGIN ISOLATION LEVEL READ COMMITTED;
SET LOCAL lock_timeout='15s';
DO $$ DECLARE started timestamptz:=clock_timestamp(); denied boolean:=false; BEGIN
 BEGIN
  PERFORM public.g08_owner_decision_time('a0000000-0000-0000-0000-000000000001',
   'd0000000-0000-0000-0000-000000000003');
 EXCEPTION WHEN insufficient_privilege THEN denied:=true;
 END;
 IF NOT denied OR clock_timestamp()-started<interval '0.1 second' THEN
  RAISE EXCEPTION 'expected overlapping lock wait and current revocation denial';
 END IF;
END $$;
ROLLBACK;
