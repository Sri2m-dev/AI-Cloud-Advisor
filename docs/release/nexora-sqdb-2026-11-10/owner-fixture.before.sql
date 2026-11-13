-- UNEXECUTED. Only a separately authorized disposable PostgreSQL fixture.
-- Install all 3 M2-A then all 3 M2-B files first, with no owner history/traffic.
-- Custodian supplies auth.users, anon/authenticated/service_role and installer
-- privileges. Synthetic references are NOT identity/policy/technical qualification.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL timezone='UTC';

CREATE FUNCTION pg_temp.fixture_id(kind text,seed integer) RETURNS uuid
LANGUAGE sql IMMUTABLE AS $$ SELECT md5(kind||':'||seed::text)::uuid $$;

CREATE FUNCTION pg_temp.expect_rejection(statement text,expected_state text) RETURNS void
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
 IF NOT rejected THEN RAISE EXCEPTION 'negative owner fixture unexpectedly accepted'; END IF;
END $$;

CREATE FUNCTION pg_temp.assertion(seed integer,purpose text,person_override text DEFAULT NULL,expired boolean DEFAULT false)
RETURNS public.g08_owner_operator_assertions LANGUAGE plpgsql AS $$
DECLARE a public.g08_owner_operation_authorizations;
 t timestamptz:=clock_timestamp(); identity public.g08_owner_operator_assertions;
BEGIN
 SELECT * INTO STRICT a FROM public.g08_owner_operation_authorizations
  WHERE authorization_id=pg_temp.fixture_id('authorization',seed);
 identity:=ROW(pg_temp.fixture_id('assertion-'||purpose,seed),a.authorization_id,a.owner_operation_id,
  purpose,coalesce(person_override,a.operator_person_ref),a.operator_authentication_evidence_ref,
  a.operator_authentication_evidence_sha256,'fixture-session-binding',session_user,NULL,
  'fixture-identity-verifier',t-interval '1 minute',
  CASE WHEN expired THEN t-interval '1 second' ELSE t+interval '1 hour' END);
 RETURN identity;
END $$;

CREATE FUNCTION pg_temp.admit(seed integer) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE a public.g08_owner_operation_authorizations; identity public.g08_owner_operator_assertions;
 t timestamptz:=clock_timestamp(); d text:=repeat('a',64);
BEGIN
 a:=ROW(pg_temp.fixture_id('authorization',seed),pg_temp.fixture_id('operation',seed),
  'grant','global',pg_temp.fixture_id('administrator',seed),NULL,'{}'::jsonb,NULL,
  'fixture-policy','fixture-requester','fixture-operator','fixture-authentication',d,d,d,d,
  'fixture-authorization',t-interval '1 hour',t+interval '1 hour');
 -- Build the ADMISSION assertion before its FK parent is persisted, then the
 -- private admission primitive stages parent/assertion/links/status atomically.
 identity:=ROW(pg_temp.fixture_id('assertion-ADMISSION',seed),a.authorization_id,a.owner_operation_id,
  'ADMISSION','fixture-admitter',a.operator_authentication_evidence_ref,d,'fixture-session-binding',
  session_user,NULL,'fixture-identity-verifier',t-interval '1 minute',t+interval '1 hour');
 PERFORM public.g08_stage_owner_admission(a,identity,ARRAY[
  ROW(a.authorization_id,'approval-a','person-a',d,'fixture-approval-a')::public.g08_owner_operation_approval_links,
  ROW(a.authorization_id,'approval-b','person-b',d,'fixture-approval-b')::public.g08_owner_operation_approval_links],
  pg_temp.fixture_id('admitted',seed),'fixture-admission','fixture rationale');
 RETURN a.authorization_id;
END $$;

CREATE FUNCTION pg_temp.terminate(seed integer,new_status text) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE identity public.g08_owner_operator_assertions; purpose text;
BEGIN
 purpose:=CASE new_status WHEN 'REVOKED' THEN 'REVOCATION' ELSE 'INVALIDATION' END;
 identity:=pg_temp.assertion(seed,purpose,'fixture-controller');
 INSERT INTO public.g08_owner_operator_assertions SELECT identity.*;
 RETURN public.g08_stage_owner_status(pg_temp.fixture_id('authorization',seed),
  pg_temp.fixture_id('terminal-'||new_status,seed),new_status,pg_temp.fixture_id('admitted',seed),
  identity.assertion_id,'fixture-terminal','fixture rationale');
END $$;

SELECT pg_temp.admit(1),pg_temp.admit(2),pg_temp.admit(3),pg_temp.admit(4),pg_temp.admit(5);
SET CONSTRAINTS ALL IMMEDIATE;
SET CONSTRAINTS ALL DEFERRED;
SELECT pg_temp.terminate(1,'REVOKED'),pg_temp.terminate(2,'INVALIDATED');
SET CONSTRAINTS ALL IMMEDIATE;
SET CONSTRAINTS ALL DEFERRED;
SELECT pg_temp.expect_rejection($q$SELECT pg_temp.terminate(1,'INVALIDATED')$q$,'23514');
SELECT pg_temp.expect_rejection($q$SELECT pg_temp.admit(3)$q$,'23505');
SELECT pg_temp.expect_rejection($q$UPDATE public.g08_owner_authorization_status_history SET status='ADMITTED'$q$,'55000');
SELECT pg_temp.expect_rejection($q$TRUNCATE public.g08_owner_operation_consumptions$q$,'55000');
SELECT pg_temp.expect_rejection($q$INSERT INTO public.g08_owner_operation_approval_links VALUES
 (pg_temp.fixture_id('authorization',3),'extra','extra-person',repeat('b',64),'extra-evidence')$q$,'23514');
SELECT pg_temp.expect_rejection($q$INSERT INTO public.g08_owner_authorization_status_history
 SELECT pg_temp.fixture_id('bad-status',3),authorization_id,owner_operation_id,3,status_id,2,'REVOKED',
 assertion_id,occurred_at,db_session_user,db_effective_role,evidence_ref,rationale,approval_manifest
 FROM public.g08_owner_authorization_status_history WHERE authorization_id=pg_temp.fixture_id('authorization',3)$q$,'23503');

-- Current authority denies terminal status, stale identity and wrong operator.
DO $$ DECLARE identity public.g08_owner_operator_assertions; seed integer; BEGIN
 FOR seed IN 1..5 LOOP
  identity:=pg_temp.assertion(seed,'EXECUTION',
   CASE WHEN seed=3 THEN 'wrong-person' END,seed=4);
  INSERT INTO public.g08_owner_operator_assertions SELECT identity.*;
 END LOOP;
END $$;
SELECT pg_temp.expect_rejection($q$SELECT public.g08_owner_decision_time(
 pg_temp.fixture_id('authorization',1),pg_temp.fixture_id('assertion-EXECUTION',1))$q$,'42501');
SELECT pg_temp.expect_rejection($q$SELECT public.g08_owner_decision_time(
 pg_temp.fixture_id('authorization',2),pg_temp.fixture_id('assertion-EXECUTION',2))$q$,'42501');
SELECT pg_temp.expect_rejection($q$SELECT public.g08_owner_decision_time(
 pg_temp.fixture_id('authorization',3),pg_temp.fixture_id('assertion-EXECUTION',3))$q$,'42501');
SELECT pg_temp.expect_rejection($q$SELECT public.g08_owner_decision_time(
 pg_temp.fixture_id('authorization',4),pg_temp.fixture_id('assertion-EXECUTION',4))$q$,'42501');
SELECT public.g08_owner_decision_time(pg_temp.fixture_id('authorization',5),pg_temp.fixture_id('assertion-EXECUTION',5));

CREATE FUNCTION pg_temp.execute_fixture(seed integer,mode text DEFAULT 'valid') RETURNS uuid
LANGUAGE plpgsql AS $$
DECLARE a public.g08_owner_operation_authorizations;
 identity public.g08_owner_operator_assertions; proof public.g08_owner_execution_evidence;
 eid uuid:=pg_temp.fixture_id('event',seed); uid uuid:=pg_temp.fixture_id('subject',seed);
 t timestamptz; canonical jsonb; result jsonb:=jsonb_build_object('event_id',eid);
BEGIN
 SELECT * INTO STRICT a FROM public.g08_owner_operation_authorizations WHERE authorization_id=pg_temp.fixture_id('authorization',seed);
 SELECT * INTO STRICT identity FROM public.g08_owner_operator_assertions WHERE assertion_id=pg_temp.fixture_id('assertion-EXECUTION',seed);
 t:=public.g08_owner_decision_time(a.authorization_id,identity.assertion_id);
 INSERT INTO auth.users(id) VALUES(uid);
 INSERT INTO public.g08_identity_administrators VALUES
 (a.administrator_id,uid,a.valid_from,a.valid_to,1,NULL,'fixture-origin',eid,eid);
 INSERT INTO public.g08_identity_administrator_versions SELECT c.*,eid
  FROM public.g08_identity_administrators c WHERE c.administrator_id=a.administrator_id;
 INSERT INTO public.g08_identity_administrator_events VALUES
 (eid,a.administrator_id,'grant',NULL,1,NULL,NULL,NULL,current_user,'owner_controlled',NULL,NULL,
 a.owner_operation_id,a.intent_sha256,repeat('a',64),'nxr-g08-owner-administration-v1',
 'fixture rationale','fixture-outcome',t,eid);
 canonical:=jsonb_build_object('version','nxr-g08-owner-administration-v1','owner_operation_id',a.owner_operation_id,
 'operation',a.operation,'scope_key',a.scope_key,'authorization_id',a.authorization_id,
 'authorization_sha256',a.authorization_sha256,'approval_manifest_sha256',a.approval_manifest_sha256,
 'policy_version',a.policy_version,'operator',jsonb_build_object('person_ref',a.operator_person_ref,
 'authentication_evidence_sha256',a.operator_authentication_evidence_sha256,'verified_auth_uid',NULL,
 'db_session_user',session_user),'procedure_identity','fixture','procedure_version','1',
 'mutation',a.mutation,'idempotency_key','fixture-'||seed::text);
 INSERT INTO public.g08_owner_operation_receipts VALUES
 (eid,a.owner_operation_id,a.authorization_id,a.operation,a.scope_key,'fixture-'||seed::text,
 a.operator_person_ref,a.operator_authentication_evidence_ref,a.operator_authentication_evidence_sha256,NULL,
 session_user,current_user,'fixture','1',a.authorization_sha256,a.approval_manifest_sha256,
 a.policy_version,'fixture-outcome','["approval-a","approval-b"]',
 'nxr-g08-owner-administration-v1',a.intent_sha256,repeat('a',64),canonical,result,t);
 proof:=ROW(pg_temp.fixture_id('proof',seed),a.authorization_id,a.owner_operation_id,eid,1,
 pg_temp.fixture_id('admitted',seed),identity.assertion_id,t,
 CASE WHEN mode='mismatch' THEN repeat('b',64) ELSE repeat('a',64) END,result,
 'fixture-technical',repeat('c',64),'fixture-technical-verifier','fixture-authority','fixture-fence');
 IF mode<>'missing' THEN PERFORM public.g08_stage_owner_consumption(proof); END IF;
 RETURN eid;
END $$;
SELECT pg_temp.expect_rejection($q$SELECT pg_temp.execute_fixture(5,'missing')$q$,'23514');
SELECT pg_temp.expect_rejection($q$SELECT pg_temp.execute_fixture(5,'mismatch')$q$,'23514');
SELECT pg_temp.execute_fixture(5);
SET CONSTRAINTS ALL IMMEDIATE;
SET CONSTRAINTS ALL DEFERRED;
SELECT pg_temp.expect_rejection($q$INSERT INTO public.g08_owner_operation_consumptions
 SELECT * FROM public.g08_owner_operation_consumptions LIMIT 1$q$,'23505');
SELECT pg_temp.expect_rejection($q$SELECT public.g08_stage_owner_consumption(p)
 FROM public.g08_owner_execution_evidence p LIMIT 1$q$,'42501');
-- Later revocation changes current permission, never deletes committed evidence.
SELECT pg_temp.terminate(5,'REVOKED');
SET CONSTRAINTS ALL IMMEDIATE;
SET CONSTRAINTS ALL DEFERRED;
SELECT public.g08_assert_owner_history();

SELECT pg_temp.expect_rejection($q$DO $policy$ BEGIN
 CREATE POLICY fixture_hide_owner ON public.g08_owner_execution_evidence
 AS RESTRICTIVE FOR SELECT TO nxr_g08_owner_history_check_owner USING(false);
 PERFORM public.g08_assert_owner_history();
 END $policy$$q$,'42501');
SET LOCAL ROLE nxr_g08_owner_history_check_owner;
SELECT public.g08_assert_owner_history();
DO $$ BEGIN
 BEGIN
  DELETE FROM public.g08_owner_execution_evidence;
  RAISE EXCEPTION 'checker unexpectedly writable';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
END $$;
RESET ROLE;
SET LOCAL ROLE authenticated;
DO $$ BEGIN
 BEGIN
  PERFORM public.g08_control_owner_operation('EXECUTION','{"verified":true}');
  RAISE EXCEPTION 'runtime execute unexpectedly permitted';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  PERFORM * FROM public.g08_owner_operation_consumptions;
  RAISE EXCEPTION 'runtime read unexpectedly permitted';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
END $$;
RESET ROLE;
-- Even an explicitly selected bounded function owner reaches the closed verifier.
SET LOCAL ROLE nxr_g08_owner_fn_owner;
DO $$ BEGIN
 BEGIN
  PERFORM public.g08_control_owner_operation('EXECUTION','{"verified":true}');
  RAISE EXCEPTION 'unconfigured identity verifier unexpectedly accepted';
 EXCEPTION WHEN object_not_in_prerequisite_state THEN NULL;
 END;
END $$;
RESET ROLE;
ROLLBACK;
