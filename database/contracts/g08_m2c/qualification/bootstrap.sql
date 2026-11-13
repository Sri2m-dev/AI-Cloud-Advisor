-- UNEXECUTED. Minimal local PostgreSQL fixture, NOT a Supabase schema emulator.
-- Requires separate environment authorization and explicit session acknowledgement.
\set ON_ERROR_STOP on
DO $$ BEGIN
 IF current_setting('nexora.qualification_authorized',true) IS DISTINCT FROM 'local-disposable'
  OR current_database() NOT LIKE 'nexora_m2c_%'
  OR (inet_server_addr() IS NOT NULL AND inet_server_addr() NOT IN ('127.0.0.1'::inet,'::1'::inet)) THEN
  RAISE EXCEPTION 'explicit authorized disposable local fixture required';
 END IF;
 IF EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='auth')
  OR EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='public' AND c.relname LIKE 'g08_%') THEN
  RAISE EXCEPTION 'fixture must be blank; no automatic reset';
 END IF;
END $$;
SET default_transaction_isolation='read committed';
CREATE SCHEMA auth;
CREATE TABLE auth.users(id uuid PRIMARY KEY);
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
