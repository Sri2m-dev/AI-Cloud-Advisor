-- Gate 1 fixed-destination preflight. Run with psql only.
-- This file reads catalogs and migration identifiers only; it does not read
-- table row contents or secrets. The transaction is explicitly read-only.
-- Do not remove the READ ONLY transaction or change this file to write SQL.
\set ON_ERROR_STOP on

BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '2s';

-- Connection identity and privilege guard evidence.
SELECT
    current_database() AS database_name,
    session_user,
    current_user,
    current_setting('server_version') AS server_version,
    current_setting('server_version_num') AS server_version_num,
    current_setting('transaction_read_only') AS transaction_read_only,
    role.rolsuper,
    role.rolbypassrls,
    role.rolcreatedb,
    role.rolcreaterole,
    role.rolcanlogin,
    role.rolinherit
FROM pg_roles AS role
WHERE role.rolname = current_user;

-- Current database owner and database-level ACL.
SELECT
    database.datname AS database_name,
    pg_get_userbyid(database.datdba) AS owner_name,
    database.datacl::text AS database_acl
FROM pg_database AS database
WHERE database.datname = current_database();

-- Non-system schemas, owners, and schema ACLs.
SELECT
    namespace.nspname AS schema_name,
    pg_get_userbyid(namespace.nspowner) AS owner_name,
    namespace.nspacl::text AS schema_acl
FROM pg_namespace AS namespace
WHERE namespace.nspname <> 'information_schema'
  AND namespace.nspname !~ '^pg_'
ORDER BY namespace.nspname;

-- Relations, owners, row-security flags, ACLs, and catalog row estimates.
-- reltuples is an estimate, not an exact row count.
SELECT
    namespace.nspname AS schema_name,
    relation.relname AS object_name,
    CASE relation.relkind
        WHEN 'r' THEN 'table'
        WHEN 'p' THEN 'partitioned table'
        WHEN 'v' THEN 'view'
        WHEN 'm' THEN 'materialized view'
        WHEN 'S' THEN 'sequence'
        WHEN 'f' THEN 'foreign table'
        ELSE relation.relkind::text
    END AS object_type,
    pg_get_userbyid(relation.relowner) AS owner_name,
    relation.relrowsecurity AS rls_enabled,
    relation.relforcerowsecurity AS force_rls,
    relation.reltuples::bigint AS estimated_rows,
    relation.relacl::text AS object_acl
FROM pg_class AS relation
JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
WHERE namespace.nspname <> 'information_schema'
  AND namespace.nspname !~ '^pg_'
  AND relation.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
ORDER BY namespace.nspname, relation.relname;

-- V1 workflow relation columns, if that schema is present. Defaults are
-- intentionally omitted to avoid exposing any accidentally embedded value.
SELECT
    namespace.nspname AS schema_name,
    relation.relname AS table_name,
    attribute.attnum AS ordinal_position,
    attribute.attname AS column_name,
    format_type(attribute.atttypid, attribute.atttypmod) AS data_type,
    attribute.attnotnull AS not_null
FROM pg_class AS relation
JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
JOIN pg_attribute AS attribute ON attribute.attrelid = relation.oid
WHERE namespace.nspname = 'nexora_customer_workflow'
  AND relation.relkind IN ('r', 'p')
  AND attribute.attnum > 0
  AND NOT attribute.attisdropped
ORDER BY relation.relname, attribute.attnum;

-- Human-readable schema grants.
SELECT
    namespace.nspname AS schema_name,
    CASE privilege.grantee
        WHEN 0 THEN 'PUBLIC'
        ELSE pg_get_userbyid(privilege.grantee)
    END AS grantee,
    pg_get_userbyid(privilege.grantor) AS grantor,
    privilege.privilege_type,
    privilege.is_grantable
FROM pg_namespace AS namespace
CROSS JOIN LATERAL aclexplode(
    COALESCE(namespace.nspacl, acldefault('n', namespace.nspowner))
) AS privilege
WHERE namespace.nspname <> 'information_schema'
  AND namespace.nspname !~ '^pg_'
ORDER BY namespace.nspname, grantee, privilege.privilege_type;

-- Default privileges that may affect future objects.
SELECT
    pg_get_userbyid(default_acl.defaclrole) AS owner_name,
    COALESCE(namespace.nspname, '<global>') AS schema_name,
    default_acl.defaclobjtype AS object_type,
    default_acl.defaclacl::text AS default_acl
FROM pg_default_acl AS default_acl
LEFT JOIN pg_namespace AS namespace
       ON namespace.oid = default_acl.defaclnamespace
ORDER BY owner_name, schema_name, object_type;

-- Human-readable table, sequence, and view grants in all non-system schemas.
SELECT
    namespace.nspname AS schema_name,
    relation.relname AS object_name,
    CASE privilege.grantee
        WHEN 0 THEN 'PUBLIC'
        ELSE pg_get_userbyid(privilege.grantee)
    END AS grantee,
    pg_get_userbyid(privilege.grantor) AS grantor,
    privilege.privilege_type,
    privilege.is_grantable
FROM pg_class AS relation
JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
CROSS JOIN LATERAL aclexplode(
    COALESCE(
        relation.relacl,
        acldefault(CASE WHEN relation.relkind = 'S' THEN 'S' ELSE 'r' END,
                   relation.relowner)
    )
) AS privilege
WHERE namespace.nspname <> 'information_schema'
  AND namespace.nspname !~ '^pg_'
  AND relation.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
ORDER BY namespace.nspname, relation.relname, grantee, privilege.privilege_type;

-- Constraint and index definitions for all non-system relations.
SELECT
    namespace.nspname AS schema_name,
    relation.relname AS table_name,
    constraint_item.conname AS object_name,
    constraint_item.contype AS constraint_type,
    constraint_item.convalidated AS validated,
    pg_get_constraintdef(constraint_item.oid, true) AS definition
FROM pg_constraint AS constraint_item
JOIN pg_class AS relation ON relation.oid = constraint_item.conrelid
JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
WHERE namespace.nspname <> 'information_schema'
  AND namespace.nspname !~ '^pg_'
ORDER BY namespace.nspname, relation.relname, constraint_item.conname;

SELECT
    namespace.nspname AS schema_name,
    relation.relname AS table_name,
    index_relation.relname AS index_name,
    index_state.indisprimary AS is_primary,
    index_state.indisunique AS is_unique,
    index_state.indisvalid AS is_valid,
    index_state.indisready AS is_ready,
    pg_get_indexdef(index_relation.oid) AS definition
FROM pg_index AS index_state
JOIN pg_class AS relation ON relation.oid = index_state.indrelid
JOIN pg_class AS index_relation ON index_relation.oid = index_state.indexrelid
JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
WHERE namespace.nspname <> 'information_schema'
  AND namespace.nspname !~ '^pg_'
ORDER BY namespace.nspname, relation.relname, index_relation.relname;

-- Role attributes only; intentionally excludes password verifiers and secrets.
SELECT
    role.rolname,
    role.rolsuper,
    role.rolcreatedb,
    role.rolcreaterole,
    role.rolinherit,
    role.rolcanlogin,
    role.rolreplication,
    role.rolbypassrls,
    role.rolconnlimit,
    role.rolvaliduntil
FROM pg_roles AS role
WHERE role.rolname !~ '^pg_'
ORDER BY role.rolname;

-- Role memberships and delegable/settable membership options.
SELECT
    member.rolname AS member_role,
    granted.rolname AS granted_role,
    membership.admin_option,
    membership.inherit_option,
    membership.set_option
FROM pg_auth_members AS membership
JOIN pg_roles AS member ON member.oid = membership.member
JOIN pg_roles AS granted ON granted.oid = membership.roleid
WHERE member.rolname !~ '^pg_'
   OR granted.rolname !~ '^pg_'
ORDER BY member.rolname, granted.rolname;

-- RLS enablement and policy definitions; no row data is selected.
SELECT
    policy.schemaname,
    policy.tablename,
    policy.policyname,
    policy.permissive,
    policy.roles,
    policy.cmd,
    policy.qual,
    policy.with_check
FROM pg_policies AS policy
WHERE policy.schemaname IN (
    'public',
    'nexora_customer_workflow',
    'auth',
    'data_fabric',
    'supabase_migrations'
)
ORDER BY policy.schemaname, policy.tablename, policy.policyname;

-- Installed extensions and namespace ownership.
SELECT
    extension.extname,
    extension.extversion,
    namespace.nspname AS extension_schema,
    pg_get_userbyid(extension.extowner) AS owner_name
FROM pg_extension AS extension
JOIN pg_namespace AS namespace ON namespace.oid = extension.extnamespace
ORDER BY extension.extname;

-- Triggers, including internal/constraint triggers, with definitions.
SELECT
    namespace.nspname AS schema_name,
    relation.relname AS table_name,
    trigger.tgname AS trigger_name,
    trigger.tgenabled AS enabled_state,
    trigger.tgisinternal AS is_internal,
    trigger.tgconstraint <> 0 AS is_constraint_trigger,
    pg_get_triggerdef(trigger.oid, true) AS trigger_definition
FROM pg_trigger AS trigger
JOIN pg_class AS relation ON relation.oid = trigger.tgrelid
JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
WHERE namespace.nspname IN (
    'public',
    'nexora_customer_workflow',
    'auth',
    'data_fabric',
    'supabase_migrations'
)
ORDER BY namespace.nspname, relation.relname, trigger.tgname;

-- Function metadata only; function bodies and settings are omitted.
SELECT
    namespace.nspname AS schema_name,
    procedure.proname AS function_name,
    pg_get_function_identity_arguments(procedure.oid) AS arguments,
    pg_get_function_result(procedure.oid) AS result_type,
    language.lanname AS language,
    pg_get_userbyid(procedure.proowner) AS owner_name,
    procedure.prosecdef AS security_definer,
    procedure.provolatile AS volatility,
    procedure.proacl::text AS function_acl
FROM pg_proc AS procedure
JOIN pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
JOIN pg_language AS language ON language.oid = procedure.prolang
WHERE namespace.nspname IN (
    'public',
    'nexora_customer_workflow',
    'auth',
    'data_fabric',
    'supabase_migrations'
)
ORDER BY namespace.nspname, procedure.proname,
         pg_get_function_identity_arguments(procedure.oid);

-- Dependencies touching protected application, Auth, G07, or migration relations.
WITH protected_relations AS (
    SELECT relation.oid
    FROM pg_class AS relation
    JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
    WHERE namespace.nspname IN (
        'public',
        'nexora_customer_workflow',
        'auth',
        'data_fabric',
        'supabase_migrations'
    )
)
SELECT
    pg_describe_object(
        dependency.classid,
        dependency.objid,
        dependency.objsubid
    ) AS dependent_object,
    pg_describe_object(
        dependency.refclassid,
        dependency.refobjid,
        dependency.refobjsubid
    ) AS referenced_object,
    dependency.deptype AS dependency_type
FROM pg_depend AS dependency
WHERE (
        dependency.classid = 'pg_class'::regclass
        AND dependency.objid IN (SELECT oid FROM protected_relations)
      )
   OR (
        dependency.refclassid = 'pg_class'::regclass
        AND dependency.refobjid IN (SELECT oid FROM protected_relations)
      )
ORDER BY dependent_object, referenced_object, dependency_type;

-- Migration identifiers only; do not select stored SQL statements.
SELECT CASE
           WHEN to_regclass('supabase_migrations.schema_migrations') IS NOT NULL
           THEN 'true'
           ELSE 'false'
       END AS migration_history_present
\gset
\if :migration_history_present
SELECT
    to_jsonb(migration)->>'version' AS version,
    to_jsonb(migration)->>'name' AS name
FROM supabase_migrations.schema_migrations AS migration
ORDER BY version, name;
\else
\echo 'supabase_migrations.schema_migrations is absent'
\endif

-- Preservation boundary summary uses catalog estimates, not row contents.
SELECT
    protected.schema_name,
    count(relation.oid) AS relation_count,
    COALESCE(sum(relation.reltuples::bigint), 0) AS estimated_rows
FROM (
    VALUES
        ('auth'),
        ('data_fabric'),
        ('nexora_customer_workflow'),
        ('public'),
        ('supabase_migrations')
) AS protected(schema_name)
LEFT JOIN pg_namespace AS namespace
       ON namespace.nspname = protected.schema_name
LEFT JOIN pg_class AS relation
       ON relation.relnamespace = namespace.oid
      AND relation.relkind IN ('r', 'p')
GROUP BY protected.schema_name
ORDER BY protected.schema_name;

-- Nothing is committed; end the read-only transaction explicitly.
ROLLBACK;
