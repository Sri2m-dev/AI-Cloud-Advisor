#!/bin/sh
set -eu

psql --set=ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=db_password="$POSTGRES_PASSWORD" <<'SQL'
\o /dev/null
SELECT 'CREATE ROLE postgres SUPERUSER NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres')
\gexec

SELECT format(
    'CREATE ROLE supabase_admin SUPERUSER LOGIN PASSWORD %L',
    :'db_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'supabase_admin')
\gexec
ALTER ROLE supabase_admin SUPERUSER LOGIN PASSWORD :'db_password';

SELECT format(
    'CREATE ROLE supabase_auth_admin NOINHERIT LOGIN BYPASSRLS PASSWORD %L',
    :'db_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'supabase_auth_admin')
\gexec
ALTER ROLE supabase_auth_admin NOINHERIT LOGIN BYPASSRLS PASSWORD :'db_password';
ALTER ROLE supabase_auth_admin SET search_path = auth, public;
\o

SELECT 'CREATE ROLE authenticator NOINHERIT LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticator')
\gexec
ALTER ROLE authenticator NOINHERIT LOGIN PASSWORD :'db_password';

SELECT 'CREATE ROLE anon NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')
\gexec
SELECT 'CREATE ROLE authenticated NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated')
\gexec
GRANT anon, authenticated TO authenticator;
GRANT CONNECT, CREATE ON DATABASE postgres TO supabase_auth_admin;
GRANT USAGE, CREATE ON SCHEMA public TO supabase_auth_admin;

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;
CREATE SCHEMA IF NOT EXISTS auth AUTHORIZATION supabase_auth_admin;
ALTER SCHEMA auth OWNER TO supabase_auth_admin;
GRANT USAGE ON SCHEMA auth TO anon, authenticated, authenticator;

CREATE OR REPLACE FUNCTION auth.jwt()
RETURNS jsonb
LANGUAGE sql
STABLE
SET search_path = pg_catalog
AS $function$
    SELECT coalesce(
        nullif(current_setting('request.jwt.claims', true), '')::jsonb,
        '{}'::jsonb
    )
$function$;

CREATE OR REPLACE FUNCTION auth.uid()
RETURNS uuid
LANGUAGE sql
STABLE
SET search_path = pg_catalog, auth
AS $function$
    SELECT nullif(auth.jwt() ->> 'sub', '')::uuid
$function$;

CREATE OR REPLACE FUNCTION auth.role()
RETURNS text
LANGUAGE sql
STABLE
SET search_path = pg_catalog, auth
AS $function$
    SELECT coalesce(nullif(auth.jwt() ->> 'role', ''), current_user::text)
$function$;

ALTER FUNCTION auth.jwt() OWNER TO supabase_auth_admin;
ALTER FUNCTION auth.uid() OWNER TO supabase_auth_admin;
ALTER FUNCTION auth.role() OWNER TO supabase_auth_admin;

GRANT EXECUTE ON FUNCTION auth.jwt() TO anon, authenticated, authenticator;
GRANT EXECUTE ON FUNCTION auth.uid() TO anon, authenticated, authenticator;
GRANT EXECUTE ON FUNCTION auth.role() TO anon, authenticated, authenticator;
SQL
