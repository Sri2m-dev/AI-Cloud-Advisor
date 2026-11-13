\set ON_ERROR_STOP on
SELECT current_database(), version();
SELECT extname, extversion FROM pg_extension ORDER BY extname;
SELECT rolname, rolcanlogin, rolsuper, rolbypassrls
FROM pg_roles
WHERE rolname LIKE 'nxr_g08_%'
   OR rolname IN ('authenticated', 'service_role', 'anon', 'postgres')
ORDER BY rolname;
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name LIKE 'g08_%'
ORDER BY table_name;
SELECT table_name, string_agg(column_name || ':' || data_type, ', ' ORDER BY ordinal_position)
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN (
      'g08_owner_operation_authorizations',
      'g08_owner_operator_assertions',
      'g08_owner_authorization_status_history',
      'g08_identity_administrators',
      'g08_identity_administrator_versions',
      'g08_identity_administrator_events',
      'g08_administration_receipts',
      'g08_owner_operation_receipts',
      'g08_owner_execution_evidence',
      'g08_owner_operation_consumptions'
  )
GROUP BY table_name
ORDER BY table_name;
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'auth' AND table_name = 'users'
ORDER BY ordinal_position;
