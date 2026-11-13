-- UNEXECUTED. Verify effective privileges, not merely GRANT source text.
BEGIN;
DO $$ DECLARE t record; r text; f record; BEGIN
 FOR t IN SELECT c.oid,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c
  JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname LIKE 'g08_%'
  AND c.relkind='r' LOOP
  IF NOT t.relrowsecurity OR NOT t.relforcerowsecurity THEN RAISE EXCEPTION 'RLS missing'; END IF;
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role','nxr_g08_owner_fn_owner',
   'nxr_g08_owner_reader_owner','nxr_g08_identity_fn_owner'] LOOP
   IF has_table_privilege(r,t.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') THEN
    RAISE EXCEPTION 'unexpected effective writer grant';
   END IF;
  END LOOP;
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
   IF has_table_privilege(r,t.oid,'SELECT') THEN RAISE EXCEPTION 'unexpected runtime read grant'; END IF;
  END LOOP;
 END LOOP;
 FOR f IN SELECT p.oid FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname='public' AND p.proname LIKE 'g08_%' LOOP
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
   IF has_function_privilege(r,f.oid,'EXECUTE') THEN RAISE EXCEPTION 'unexpected runtime RPC grant'; END IF;
  END LOOP;
 END LOOP;
 FOREACH r IN ARRAY ARRAY['nxr_g08_history_check_owner','nxr_g08_owner_history_check_owner',
  'nxr_g08_identity_fn_owner','nxr_g08_owner_fn_owner','nxr_g08_owner_reader_owner'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r AND
   (rolcanlogin OR rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication OR rolinherit))
   OR has_schema_privilege(r,'public','CREATE')
   OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=(SELECT oid FROM pg_roles WHERE rolname=r)
    OR member=(SELECT oid FROM pg_roles WHERE rolname=r))
   OR EXISTS(SELECT 1 FROM pg_class WHERE relkind='r' AND relowner=(SELECT oid FROM pg_roles WHERE rolname=r)) THEN
   RAISE EXCEPTION 'unexpected role ownership/attribute/membership path';
  END IF;
 END LOOP;
END $$;
-- G08 is GLOBAL and has no accepted tenant success projection. Neither tenant
-- may read/write it; this tests denial, not successful per-tenant G08 authority.
SET LOCAL ROLE authenticated;
DO $$ BEGIN
 BEGIN
  PERFORM * FROM public.g08_owner_operation_authorizations;
  RAISE EXCEPTION 'unexpected tenant-visible owner history';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
END $$;
RESET ROLE;
SELECT public.g08_assert_identity_history();
SELECT public.g08_assert_owner_history();
ROLLBACK;
