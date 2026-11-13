-- UNEXECUTED. Run only in separately authorized fresh local disposable cluster.
\set ON_ERROR_STOP on
\ir bootstrap.sql
\ir ../../g08_m2a/S020_integrity.sql
\ir ../../g08_m2a/A020A_enforcement.sql
\ir ../../g08_m2a/A020A_private_writer.sql
-- M2-A data fixture rolls back BEFORE the stronger owner-history requirements.
\ir ../../../../tests/database_integrity/postgres_qualification.sql
\ir ../../g08_m2b/S021_owner_authorization.sql
\ir ../../g08_m2b/A021_owner_integrity.sql
\ir ../../g08_m2b/A021_owner_interfaces.sql
\ir ../A022_result_link_integrity.sql
\ir ../../../../tests/owner_authorization/postgres_qualification.sql
\ir privileges_and_boundaries.sql
\ir rollback_recovery.sql
