-- Specific recovery for recorded A021 parse failure only; not a generic retry.
\set ON_ERROR_STOP on
\ir ../../database/contracts/g08_m2c/qualification/local_guard.sql
DO $$ BEGIN
 IF to_regclass('public.g08_owner_authorization_status_history') IS NULL
 OR to_regprocedure('public.g08_assert_owner_history()') IS NOT NULL THEN
  RAISE EXCEPTION 'unexpected partial-install state; continuation refused';
 END IF;
END $$;
\ir ../../database/contracts/g08_m2b/A021_owner_integrity.sql
\ir ../../database/contracts/g08_m2b/A021_owner_interfaces.sql
\ir ../../database/contracts/g08_m2c/A022_result_link_integrity.sql
\ir ../../tests/owner_authorization/postgres_qualification.sql
\ir ../../database/contracts/g08_m2c/qualification/privileges_and_boundaries.sql
\ir ../../database/contracts/g08_m2c/qualification/rollback_recovery.sql
