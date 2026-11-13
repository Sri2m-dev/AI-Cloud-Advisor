#!/bin/sh
set -eu

authenticator_password=$(cat /run/secrets/financial_authenticator_password)
psql --set=ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=authenticator_password="$authenticator_password" <<'SQL'
SELECT format(
    'CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD %L',
    :'authenticator_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'authenticator')
\gexec

CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
GRANT anon, authenticated TO authenticator;

CREATE SCHEMA auth;
CREATE TABLE auth.users (id uuid PRIMARY KEY);

CREATE FUNCTION auth.jwt()
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

CREATE FUNCTION auth.uid()
RETURNS uuid
LANGUAGE sql
STABLE
SET search_path = pg_catalog, auth
AS $function$
    SELECT nullif(auth.jwt() ->> 'sub', '')::uuid
$function$;

CREATE FUNCTION auth.role()
RETURNS text
LANGUAGE sql
STABLE
SET search_path = pg_catalog, auth
AS $function$
    SELECT coalesce(nullif(auth.jwt() ->> 'role', ''), current_user::text)
$function$;

REVOKE ALL ON SCHEMA auth FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA auth TO authenticated, authenticator;
GRANT EXECUTE ON FUNCTION auth.jwt(), auth.uid(), auth.role()
    TO authenticated, authenticator;

CREATE FUNCTION public.validate_r5_auth_request()
RETURNS void
LANGUAGE plpgsql
SET search_path = pg_catalog, public, auth
AS $function$
DECLARE
    claims jsonb := auth.jwt();
BEGIN
    IF claims ->> 'iss' IS DISTINCT FROM 'https://auth-gateway:8443'
       OR claims ->> 'aud' IS DISTINCT FROM 'authenticated'
       OR claims ->> 'role' IS DISTINCT FROM 'authenticated'
       OR auth.uid() IS NULL THEN
        RAISE insufficient_privilege USING MESSAGE = 'verified r5 Auth identity required';
    END IF;
END
$function$;

REVOKE ALL ON FUNCTION public.validate_r5_auth_request() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.validate_r5_auth_request() TO authenticated;
SQL
unset authenticator_password
