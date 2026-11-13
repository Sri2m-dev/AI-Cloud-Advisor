-- UNEXECUTED. Destructive negative statements below are confined to transactions
-- on a separately authorized disposable PostgreSQL fixture ONLY. No connection runner.
-- Prerequisite: isolated blank DB; installer superuser; auth.users + anon,
-- authenticated, service_role roles supplied by the authorized fixture custodian.
-- Install S020, A020A_enforcement, A020A_private_writer before this file.
-- psql ON_ERROR_STOP required. All generated test history is rolled back.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL timezone='UTC';
INSERT INTO auth.users(id) VALUES ('00000000-0000-0000-0000-000000000001');
INSERT INTO auth.users(id) VALUES ('00000000-0000-0000-0000-000000000004');

-- Synthetic owner bootstrap tests structure only, never operator assurance.
DO $$
DECLARE aid uuid:='10000000-0000-0000-0000-000000000001';
 eid uuid:='20000000-0000-0000-0000-000000000001';
 oid uuid:='30000000-0000-0000-0000-000000000001';
 auid uuid:='40000000-0000-0000-0000-000000000001';
 d text:=repeat('a',64); t timestamptz:=clock_timestamp();
 req jsonb;
BEGIN
 INSERT INTO public.g08_owner_operation_authorizations VALUES
 (auid,oid,'grant','global',aid,NULL,'{}',NULL,'fixture-policy','requester','operator',
  'fixture-authentication',d,d,d,d,'fixture-evidence',t-interval '1 day',t+interval '1 day');
 INSERT INTO public.g08_owner_operation_approval_links VALUES
 (auid,'approval-a','person-a',d,'fixture-a'),(auid,'approval-b','person-b',d,'fixture-b');
 INSERT INTO public.g08_identity_administrators VALUES
 (aid,'00000000-0000-0000-0000-000000000001',t-interval '1 day',NULL,1,NULL,'fixture-origin',eid,eid);
 INSERT INTO public.g08_identity_administrator_versions
 SELECT c.*,eid FROM public.g08_identity_administrators c WHERE administrator_id=aid;
 INSERT INTO public.g08_identity_administrator_events VALUES
 (eid,aid,'grant',NULL,1,NULL,NULL,NULL,current_user,'owner_controlled',NULL,NULL,oid,d,d,
  'nxr-g08-owner-administration-v1','fixture rationale','fixture-evidence',t,eid);
 req:=jsonb_build_object('version','nxr-g08-owner-administration-v1','owner_operation_id',oid,
  'operation','grant','scope_key','global','authorization_id',auid,'authorization_sha256',d,
  'approval_manifest_sha256',d,'policy_version','fixture-policy',
  'operator',jsonb_build_object('person_ref','operator','authentication_evidence_sha256',d,
    'verified_auth_uid',NULL,'db_session_user',session_user),
  'procedure_identity','fixture','procedure_version','1','mutation','{}'::jsonb,'idempotency_key','bootstrap');
 INSERT INTO public.g08_owner_operation_receipts VALUES
 (eid,oid,auid,'grant','global','bootstrap','operator','fixture-authentication',d,NULL,
  session_user,current_user,'fixture','1',d,d,'fixture-policy','fixture-evidence',
  '["approval-a","approval-b"]','nxr-g08-owner-administration-v1',d,d,req,'{}',t);
END $$;
SET CONSTRAINTS ALL IMMEDIATE;
SET CONSTRAINTS ALL DEFERRED;
SELECT public.g08_assert_identity_history();

-- Test-only helper: privileged structural fixture, never a production admission path.
CREATE FUNCTION pg_temp.append_fixture(p_action text,p_revision bigint,p_seed integer,p_links text DEFAULT 'valid') RETURNS uuid
LANGUAGE plpgsql AS $$
DECLARE aid uuid:='10000000-0000-0000-0000-000000000002';
 executor uuid:='00000000-0000-0000-0000-000000000001';
 requester uuid:='00000000-0000-0000-0000-000000000002';
 approver uuid:='00000000-0000-0000-0000-000000000003';
 eid uuid:=('20000000-0000-0000-0000-'||lpad(p_seed::text,12,'0'))::uuid;
 rid uuid:=('50000000-0000-0000-0000-'||lpad(p_seed::text,12,'0'))::uuid;
 apid uuid:=('60000000-0000-0000-0000-'||lpad(p_seed::text,12,'0'))::uuid;
 d text:=repeat('b',64); t timestamptz:=clock_timestamp();
 v public.g08_identity_administrator_versions;
 e public.g08_identity_administrator_events;
 h public.g08_administration_receipts;
BEGIN
 IF p_action='grant' THEN
  v:=ROW(aid,'00000000-0000-0000-0000-000000000004',t-interval '1 hour',t+interval '1 day',1,NULL,'fixture-origin',eid,eid,eid);
 ELSE
  SELECT c.*,eid INTO v FROM public.g08_identity_administrators c WHERE administrator_id=aid;
  v.revision:=p_revision+1; v.current_event_id:=eid; v.event_id:=eid;
  IF p_action='revise' THEN v.valid_to:=t+interval '2 days'; END IF;
 END IF;
 INSERT INTO public.g08_identity_administrator_requests VALUES
 (rid,requester,'requester','identity-requester',executor,p_action,aid,p_revision,
  CASE WHEN p_action='grant' THEN v.subject_auth_uid END,
  CASE WHEN p_action='grant' THEN v.valid_from END,
  CASE WHEN p_action<>'revoke' THEN v.valid_to END,
  'fixture rationale','fixture-evidence','fixture-policy','nxr-g08-identity-admin-intent-v1',
  d,t-interval '2 minutes',p_seed::text,rid);
 INSERT INTO public.g08_identity_administrator_approvals VALUES
 (apid,rid,d,approver,'approver','identity-approver','validator','validation','approval',
  t-interval '1 minute',t+interval '1 hour','fixture-policy');
 e:=ROW(eid,aid,p_action,p_revision,v.revision,rid,requester,executor,current_user,
  'authenticated','10000000-0000-0000-0000-000000000001',1,NULL,d,d,
  'nxr-g08-identity-admin-execution-v1','fixture rationale','fixture-evidence',t,eid);
 h:=ROW(eid,'identity_admin','global',p_action,p_seed::text,executor,e.fingerprint_version,d,
  jsonb_build_object('version',e.fingerprint_version,'namespace','identity_admin','scope_key','global',
   'operation',p_action,'request_id',rid,'intent_sha256',d,'executor_auth_uid',executor,
   'approval_ids',jsonb_build_array(apid),'idempotency_key',p_seed::text),
  jsonb_build_object('event_id',eid,'request_id',rid,'administrator_id',aid,'action',p_action,
   'before_revision',p_revision,'resulting_revision',v.revision,'requester_auth_uid',requester,
   'executor_auth_uid',executor,'approval_ids',jsonb_build_array(apid),'occurred_at',t,
   'intent_sha256',d,'fingerprint_version',e.fingerprint_version,'request_digest',d,'idempotency_key',p_seed::text),t);
 RETURN public.g08_stage_authenticated_history(v,e,h,
  CASE p_links WHEN 'missing' THEN ARRAY[]::uuid[] WHEN 'duplicate' THEN ARRAY[apid,apid] ELSE ARRAY[apid] END);
END $$;
SELECT pg_temp.append_fixture('grant',NULL,2);
SET CONSTRAINTS ALL IMMEDIATE;
SET CONSTRAINTS ALL DEFERRED;
SELECT pg_temp.append_fixture('revise',1,3);
SET CONSTRAINTS ALL IMMEDIATE;
SET CONSTRAINTS ALL DEFERRED;

CREATE FUNCTION pg_temp.expect_rejection(statement text, expected_state text) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE rejected boolean:=false;
BEGIN
 BEGIN
  EXECUTE statement;
  SET CONSTRAINTS ALL IMMEDIATE;
 EXCEPTION WHEN OTHERS THEN
  IF SQLSTATE<>expected_state THEN RAISE; END IF;
  rejected:=true;
 END;
 IF NOT rejected THEN RAISE EXCEPTION 'negative fixture unexpectedly accepted: %',statement; END IF;
END $$;

-- Duplicate link, immutable receipt, orphan human receipt, invalid predecessor.
SELECT pg_temp.expect_rejection($q$INSERT INTO public.g08_identity_administrator_event_approvals
 SELECT * FROM public.g08_identity_administrator_event_approvals LIMIT 1$q$,'23505');
SELECT pg_temp.expect_rejection($q$UPDATE public.g08_administration_receipts SET result='{}'$q$,'55000');
SELECT pg_temp.expect_rejection($q$INSERT INTO public.g08_administration_receipts
 SELECT '20000000-0000-0000-0000-000000000099',namespace,scope_key,operation,'orphan',actor_auth_uid,
 fingerprint_version,request_digest,canonical_request,result,occurred_at
 FROM public.g08_administration_receipts LIMIT 1$q$,'23514');
SELECT pg_temp.expect_rejection($q$SELECT pg_temp.append_fixture('revise',9,9)$q$,'23514');
SELECT pg_temp.expect_rejection($q$SELECT pg_temp.append_fixture('revise',2,8,'missing')$q$,'23514');
SELECT pg_temp.expect_rejection($q$SELECT pg_temp.append_fixture('revise',2,8,'duplicate')$q$,'23514');
SELECT pg_temp.expect_rejection($q$SELECT public.g08_stage_authenticated_history(v,e,h,
 ARRAY['60000000-0000-0000-0000-000000000003'::uuid])
 FROM public.g08_identity_administrator_versions v
 JOIN public.g08_identity_administrator_events e ON e.event_id=v.event_id
 JOIN public.g08_administration_receipts h ON h.event_id=e.event_id
 WHERE e.event_id='20000000-0000-0000-0000-000000000003'$q$,'23505');

-- Late extra approval: same request, independent second approver; immutable
-- receipt still records exactly the original set, so insertion must fail.
SELECT pg_temp.expect_rejection($q$WITH extra AS (
 INSERT INTO public.g08_identity_administrator_approvals
 SELECT '60000000-0000-0000-0000-000000000099',request_id,intent_sha256,
 '00000000-0000-0000-0000-000000000099','extra-person',approver_identity_evidence_ref,
 validator_ref,validation_evidence_ref,approval_evidence_ref,approved_at,expires_at,policy_version
 FROM public.g08_identity_administrator_approvals WHERE approval_id='60000000-0000-0000-0000-000000000003'
 RETURNING approval_id)
 INSERT INTO public.g08_identity_administrator_event_approvals SELECT
 '20000000-0000-0000-0000-000000000003',approval_id FROM extra$q$,'23514');

-- A later withdrawal preserves historical validity; backdated withdrawal fails.
INSERT INTO public.g08_identity_administrator_approval_withdrawals VALUES
 ('70000000-0000-0000-0000-000000000003','60000000-0000-0000-0000-000000000003',
 '00000000-0000-0000-0000-000000000003','validator','withdrawal','fixture rationale',clock_timestamp());
SET CONSTRAINTS ALL IMMEDIATE;
SET CONSTRAINTS ALL DEFERRED;
SELECT pg_temp.expect_rejection($q$INSERT INTO public.g08_identity_administrator_approval_withdrawals VALUES
 ('70000000-0000-0000-0000-000000000002','60000000-0000-0000-0000-000000000002',
 '00000000-0000-0000-0000-000000000003','validator','withdrawal','fixture rationale',clock_timestamp()-interval '1 hour')$q$,'23514');
SELECT pg_temp.append_fixture('revoke',2,4);
SET CONSTRAINTS ALL IMMEDIATE;
SET CONSTRAINTS ALL DEFERRED;
SELECT pg_temp.expect_rejection($q$SELECT pg_temp.append_fixture('revise',3,5)$q$,'23514');
SELECT public.g08_assert_identity_history();

-- Checker cannot silently accept RLS-hidden rows. Policy DDL is fixture-only.
SELECT pg_temp.expect_rejection($q$DO $policy$ BEGIN
 CREATE POLICY fixture_hide_history ON public.g08_identity_administrator_versions
 AS RESTRICTIVE FOR SELECT TO nxr_g08_history_check_owner USING(false);
 PERFORM public.g08_assert_identity_history();
 END $policy$$q$,'42501');
SET LOCAL ROLE nxr_g08_history_check_owner;
SELECT public.g08_assert_identity_history();
DO $$ BEGIN
 BEGIN
  UPDATE public.g08_identity_administrators SET revision=revision+1;
  RAISE EXCEPTION 'checker unexpectedly writable';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
END $$;
RESET ROLE;

-- Runtime denial: do not grant test role membership on any real target.
SET LOCAL ROLE authenticated;
DO $$
BEGIN
 BEGIN
  PERFORM * FROM public.g08_identity_administrators;
  RAISE EXCEPTION 'unexpected runtime SELECT';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  PERFORM public.g08_administer_identity_administrator('{}');
  RAISE EXCEPTION 'unexpected runtime execute';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  INSERT INTO public.g08_identity_administrator_event_approvals VALUES
  ('20000000-0000-0000-0000-000000000003','60000000-0000-0000-0000-000000000003');
  RAISE EXCEPTION 'unexpected runtime write';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
END $$;
RESET ROLE;
ROLLBACK;
