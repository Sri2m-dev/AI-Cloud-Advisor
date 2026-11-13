-- Specific recovery for recorded A021 parse failure only; not a generic retry.
\set ON_ERROR_STOP on
\ir local_guard.sql
DO $$ BEGIN
 IF to_regclass('public.g08_owner_authorization_status_history') IS NULL
 OR to_regprocedure('public.g08_assert_owner_history()') IS NOT NULL THEN
  RAISE EXCEPTION 'unexpected partial-install state; continuation refused';
 END IF;
END $$;
\ir ../../g08_m2b/A021_owner_integrity.sql
\ir ../../g08_m2b/A021_owner_interfaces.sql
\ir ../A022_result_link_integrity.sql
\ir ../../../../tests/owner_authorization/postgres_qualification.sql
\ir privileges_and_boundaries.sql
\ir rollback_recovery.sql
