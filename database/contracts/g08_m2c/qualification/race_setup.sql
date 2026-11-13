-- UNEXECUTED. Dedicated synthetic admission for the overlapping-session test.
\set ON_ERROR_STOP on
DO $$ BEGIN
 IF current_setting('nexora.qualification_authorized',true) IS DISTINCT FROM 'local-disposable'
  OR current_database() NOT LIKE 'nexora_m2c_%'
  OR (inet_server_addr() IS NOT NULL AND inet_server_addr() NOT IN ('127.0.0.1'::inet,'::1'::inet)) THEN
  RAISE EXCEPTION 'authorized local fixture required';
 END IF;
END $$;
BEGIN;
DO $$
DECLARE a public.g08_owner_operation_authorizations; identity public.g08_owner_operator_assertions;
 t timestamptz:=clock_timestamp(); d text:=repeat('a',64);
 aid uuid:='a0000000-0000-0000-0000-000000000001';
 oid uuid:='b0000000-0000-0000-0000-000000000001';
BEGIN
 a:=ROW(aid,oid,'grant','global','c0000000-0000-0000-0000-000000000001',NULL,
  '{}'::jsonb,NULL,'fixture-policy','requester','operator','fixture-auth',d,d,d,d,
  'fixture-evidence',t-interval '1 hour',t+interval '1 hour');
 identity:=ROW('d0000000-0000-0000-0000-000000000001',aid,oid,'ADMISSION','fixture-admitter',
  'fixture-auth',d,'fixture-session',session_user,NULL,'fixture-verifier',t-interval '1 minute',t+interval '1 hour');
 PERFORM public.g08_stage_owner_admission(a,identity,ARRAY[
  ROW(aid,'approval-a','person-a',d,'evidence-a')::public.g08_owner_operation_approval_links,
  ROW(aid,'approval-b','person-b',d,'evidence-b')::public.g08_owner_operation_approval_links],
  'e0000000-0000-0000-0000-000000000001','fixture-admission','fixture rationale');
 identity.assertion_id:='d0000000-0000-0000-0000-000000000002';
 identity.purpose:='REVOCATION';
 INSERT INTO public.g08_owner_operator_assertions SELECT identity.*;
 identity.assertion_id:='d0000000-0000-0000-0000-000000000003';
 identity.purpose:='EXECUTION'; identity.person_ref:='operator';
 INSERT INTO public.g08_owner_operator_assertions SELECT identity.*;
END $$;
COMMIT;
