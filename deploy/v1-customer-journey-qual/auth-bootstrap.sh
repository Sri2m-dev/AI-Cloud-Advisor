#!/bin/sh
set -eu

psql --set=ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=db_password="$POSTGRES_PASSWORD" <<'SQL'
SELECT 'CREATE ROLE postgres SUPERUSER NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres')
\gexec

SELECT format(
    'CREATE ROLE supabase_auth_admin NOINHERIT LOGIN BYPASSRLS PASSWORD %L',
    :'db_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'supabase_auth_admin')
\gexec
ALTER ROLE supabase_auth_admin NOINHERIT LOGIN BYPASSRLS PASSWORD :'db_password';
ALTER ROLE supabase_auth_admin SET search_path = auth, public;

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
SELECT 'CREATE ROLE service_role NOLOGIN BYPASSRLS'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role')
\gexec
GRANT anon, authenticated TO authenticator;
GRANT CONNECT, CREATE ON DATABASE postgres TO supabase_auth_admin;
GRANT USAGE, CREATE ON SCHEMA public TO supabase_auth_admin;
GRANT USAGE, CREATE ON SCHEMA public TO authenticator, anon, authenticated;

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
GRANT service_role TO authenticator;

CREATE TABLE IF NOT EXISTS public.organizations (
    id uuid PRIMARY KEY,
    name text NOT NULL,
    status text NOT NULL CHECK (status IN ('active', 'inactive'))
);
CREATE TABLE IF NOT EXISTS public.users (
    auth_user_id uuid PRIMARY KEY,
    email text NOT NULL UNIQUE,
    org_id uuid NOT NULL REFERENCES public.organizations(id),
    role text NOT NULL,
    permissions jsonb NOT NULL DEFAULT '[]'::jsonb
);
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS users_read_self ON public.users;
CREATE POLICY users_read_self ON public.users
    FOR SELECT TO authenticated
    USING (auth_user_id = auth.uid());
DROP POLICY IF EXISTS organizations_read_membership ON public.organizations;
CREATE POLICY organizations_read_membership ON public.organizations
    FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.users AS member
            WHERE member.org_id = organizations.id
              AND member.auth_user_id = auth.uid()
        )
    );
GRANT SELECT ON public.users, public.organizations TO authenticated;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT ALL ON public.users, public.organizations TO service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA public
    GRANT SELECT ON TABLES TO authenticated;
SQL
