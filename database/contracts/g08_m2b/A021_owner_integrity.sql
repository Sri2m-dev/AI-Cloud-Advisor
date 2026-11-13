-- STAGED / UNEXECUTED. Requires S021 + M2-A, no writers between steps.
BEGIN;
GRANT CREATE ON SCHEMA public TO nxr_g08_owner_history_check_owner;
GRANT EXECUTE ON FUNCTION public.g08_assert_identity_history() TO nxr_g08_owner_history_check_owner;

CREATE FUNCTION public.g08_assert_owner_history() RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog SET row_security=on AS $$
DECLARE a public.g08_owner_operation_authorizations;
 s public.g08_owner_authorization_status_history;
 previous public.g08_owner_authorization_status_history;
 operator_assertion public.g08_owner_operator_assertions;
 consumption public.g08_owner_operation_consumptions;
 proof public.g08_owner_execution_evidence;
 event public.g08_identity_administrator_events;
 receipt public.g08_owner_operation_receipts;
 n bigint; manifest jsonb;
BEGIN
 -- Read-only catalog visibility assertions, independent of the M2-A 11-table check.
 IF (SELECT count(*) FROM pg_catalog.pg_class cl JOIN pg_catalog.pg_namespace ns ON ns.oid=cl.relnamespace
 WHERE ns.nspname='public' AND cl.relname IN ('g08_owner_operator_assertions','g08_owner_authorization_status_history',
 'g08_owner_execution_evidence','g08_owner_operation_consumptions','g08_owner_operation_authorizations',
 'g08_owner_operation_approval_links','g08_owner_operation_receipts','g08_identity_administrator_events')
 AND cl.relrowsecurity AND cl.relforcerowsecurity
 AND cl.relowner<>(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user)
 AND EXISTS(SELECT 1 FROM pg_catalog.pg_policy pol WHERE pol.polrelid=cl.oid
  AND pol.polname='g08_owner_checker_select' AND pol.polcmd='r' AND pol.polpermissive
  AND pol.polroles=ARRAY[(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user)]
  AND pg_catalog.pg_get_expr(pol.polqual,pol.polrelid)='true')
 AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_policy pol WHERE pol.polrelid=cl.oid
  AND NOT pol.polpermissive AND pol.polcmd IN ('r','*')))<>8 THEN
  RAISE EXCEPTION 'G08 owner checker visibility unavailable' USING ERRCODE='42501';
 END IF;
 PERFORM public.g08_assert_identity_history();
 FOR a IN SELECT * FROM public.g08_owner_operation_authorizations LOOP
  n:=0;
  SELECT coalesce(jsonb_agg(to_jsonb(l)-'authorization_id' ORDER BY l.approval_ref::text),'[]'::jsonb)
   INTO manifest FROM public.g08_owner_operation_approval_links l WHERE l.authorization_id=a.authorization_id;
  IF manifest='[]'::jsonb OR EXISTS(SELECT 1 FROM public.g08_owner_operation_approval_links l
   WHERE l.authorization_id=a.authorization_id AND l.approver_person_ref=a.requester_person_ref) THEN
   RAISE EXCEPTION 'G08 owner independent approval evidence missing' USING ERRCODE='23514';
  END IF;
  FOR s IN SELECT * FROM public.g08_owner_authorization_status_history
   WHERE authorization_id=a.authorization_id ORDER BY revision LOOP
   n:=n+1;
   IF s.revision<>n OR s.owner_operation_id<>a.owner_operation_id OR s.approval_manifest IS DISTINCT FROM manifest THEN
    RAISE EXCEPTION 'G08 owner status revision gap or operation mismatch' USING ERRCODE='23514';
   END IF;
   IF n=1 THEN
    IF s.status<>'ADMITTED' OR s.predecessor_status_id IS NOT NULL OR s.predecessor_revision IS NOT NULL THEN
     RAISE EXCEPTION 'G08 owner initial status must be ADMITTED' USING ERRCODE='23514';
    END IF;
   ELSE
    IF previous.status<>'ADMITTED' OR s.status NOT IN ('REVOKED','INVALIDATED')
     OR s.predecessor_status_id IS DISTINCT FROM previous.status_id
     OR s.predecessor_revision IS DISTINCT FROM previous.revision OR s.occurred_at<previous.occurred_at THEN
     RAISE EXCEPTION 'G08 owner terminal or predecessor violation' USING ERRCODE='23514';
    END IF;
   END IF;
   SELECT * INTO STRICT operator_assertion FROM public.g08_owner_operator_assertions WHERE assertion_id=s.assertion_id;
   IF (operator_assertion.authorization_id,operator_assertion.owner_operation_id,operator_assertion.db_session_user)
    IS DISTINCT FROM (s.authorization_id,s.owner_operation_id,s.db_session_user)
    OR operator_assertion.purpose<>(CASE s.status WHEN 'ADMITTED' THEN 'ADMISSION'
      WHEN 'REVOKED' THEN 'REVOCATION' ELSE 'INVALIDATION' END)
    OR operator_assertion.verified_at>s.occurred_at OR operator_assertion.valid_until<=s.occurred_at THEN
    RAISE EXCEPTION 'G08 owner status assertion mismatch' USING ERRCODE='23514';
   END IF;
   previous:=s;
  END LOOP;
  IF n=0 THEN RAISE EXCEPTION 'G08 authorization has no admission' USING ERRCODE='23514'; END IF;
 END LOOP;
 -- Both directions: every owner event/receipt has one consumption; every consumption
 -- has one evidence record and matching event+receipt. FKs alone do not prove equality.
 IF EXISTS(SELECT 1 FROM public.g08_identity_administrator_events e WHERE e.execution_mode='owner_controlled'
  AND NOT EXISTS(SELECT 1 FROM public.g08_owner_operation_consumptions c WHERE c.event_id=e.event_id AND c.owner_operation_id=e.owner_operation_id))
 OR EXISTS(SELECT 1 FROM public.g08_owner_operation_receipts r WHERE NOT EXISTS(
  SELECT 1 FROM public.g08_owner_operation_consumptions c WHERE
   (c.event_id,c.authorization_id,c.owner_operation_id)=(r.event_id,r.authorization_id,r.owner_operation_id)))
 OR EXISTS(SELECT 1 FROM public.g08_owner_execution_evidence p WHERE NOT EXISTS(
  SELECT 1 FROM public.g08_owner_operation_consumptions c WHERE
   (c.evidence_id,c.authorization_id,c.owner_operation_id,c.event_id)=(p.evidence_id,p.authorization_id,p.owner_operation_id,p.event_id))) THEN
  RAISE EXCEPTION 'G08 incomplete owner consumption/evidence' USING ERRCODE='23514';
 END IF;
 FOR consumption IN SELECT * FROM public.g08_owner_operation_consumptions LOOP
  SELECT * INTO STRICT a FROM public.g08_owner_operation_authorizations WHERE authorization_id=consumption.authorization_id;
  SELECT * INTO STRICT proof FROM public.g08_owner_execution_evidence WHERE evidence_id=consumption.evidence_id;
  SELECT * INTO STRICT event FROM public.g08_identity_administrator_events WHERE event_id=consumption.event_id;
  SELECT * INTO STRICT receipt FROM public.g08_owner_operation_receipts WHERE event_id=consumption.event_id;
  SELECT * INTO STRICT s FROM public.g08_owner_authorization_status_history WHERE status_id=proof.admitted_status_id;
  SELECT * INTO STRICT operator_assertion FROM public.g08_owner_operator_assertions WHERE assertion_id=proof.assertion_id;
  IF (a.owner_operation_id,proof.owner_operation_id,event.owner_operation_id,receipt.owner_operation_id)
    IS DISTINCT FROM (consumption.owner_operation_id,consumption.owner_operation_id,consumption.owner_operation_id,consumption.owner_operation_id)
   OR (proof.authorization_id,receipt.authorization_id,proof.event_id)
    IS DISTINCT FROM (a.authorization_id,a.authorization_id,event.event_id)
   OR event.execution_mode<>'owner_controlled' OR s.status<>'ADMITTED' OR s.revision<>1
   OR s.authorization_id<>a.authorization_id OR s.occurred_at>consumption.consumed_at
   OR (proof.decision_time,event.occurred_at,receipt.occurred_at)
    IS DISTINCT FROM (consumption.consumed_at,consumption.consumed_at,consumption.consumed_at)
   OR a.valid_from>consumption.consumed_at OR a.valid_to<=consumption.consumed_at
   OR EXISTS(SELECT 1 FROM public.g08_owner_authorization_status_history terminal
    WHERE terminal.authorization_id=a.authorization_id AND terminal.status IN ('REVOKED','INVALIDATED')
     AND terminal.occurred_at<=consumption.consumed_at)
   OR operator_assertion.purpose<>'EXECUTION'
   OR (operator_assertion.authorization_id,operator_assertion.owner_operation_id,operator_assertion.person_ref,
       operator_assertion.authentication_evidence_ref,operator_assertion.authentication_evidence_sha256,
       operator_assertion.db_session_user,operator_assertion.verified_auth_uid)
    IS DISTINCT FROM (a.authorization_id,a.owner_operation_id,receipt.operator_person_ref,
       receipt.operator_authentication_evidence_ref,receipt.operator_authentication_evidence_sha256,
       receipt.db_session_user,receipt.verified_operator_auth_uid)
   OR operator_assertion.verified_at>consumption.consumed_at OR operator_assertion.valid_until<=consumption.consumed_at
   OR proof.request_digest<>event.request_digest OR proof.request_digest<>receipt.request_digest
   OR proof.result IS DISTINCT FROM receipt.result THEN
   RAISE EXCEPTION 'G08 invalid owner authority/operator/execution linkage' USING ERRCODE='23514';
  END IF;
 END LOOP;
 -- Evidence references/hashes are linkage, not proof of identity or a technical PASS.
 -- Trust verifiers remain closed in A021 interfaces; current expiry never erases history.
END $$;
ALTER FUNCTION public.g08_assert_owner_history() OWNER TO nxr_g08_owner_history_check_owner;
REVOKE ALL ON FUNCTION public.g08_assert_owner_history() FROM PUBLIC,anon,authenticated,service_role,nxr_g08_identity_fn_owner;
GRANT EXECUTE ON FUNCTION public.g08_assert_owner_history() TO nxr_g08_owner_fn_owner,nxr_g08_owner_reader_owner;

CREATE FUNCTION public.g08_check_owner_history() RETURNS trigger
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog SET row_security=on AS $$
BEGIN PERFORM public.g08_assert_owner_history(); RETURN NULL; END $$;
ALTER FUNCTION public.g08_check_owner_history() OWNER TO nxr_g08_owner_history_check_owner;
REVOKE ALL ON FUNCTION public.g08_check_owner_history() FROM PUBLIC,anon,authenticated,service_role;

DO $triggers$
DECLARE t text;
BEGIN
 FOREACH t IN ARRAY ARRAY['g08_owner_operator_assertions','g08_owner_authorization_status_history',
 'g08_owner_execution_evidence','g08_owner_operation_consumptions'] LOOP
  EXECUTE format('CREATE TRIGGER g08_owner_global_lock BEFORE INSERT OR UPDATE OR DELETE ON public.%I FOR EACH STATEMENT EXECUTE FUNCTION public.g08_guard_history_write()',t);
  EXECUTE format('CREATE TRIGGER g08_owner_append_only BEFORE UPDATE OR DELETE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.g08_deny_history_mutation()',t);
  EXECUTE format('CREATE TRIGGER g08_owner_no_truncate BEFORE TRUNCATE ON public.%I FOR EACH STATEMENT EXECUTE FUNCTION public.g08_deny_history_mutation()',t);
 END LOOP;
 FOREACH t IN ARRAY ARRAY['g08_owner_operator_assertions','g08_owner_authorization_status_history',
 'g08_owner_execution_evidence','g08_owner_operation_consumptions','g08_owner_operation_authorizations',
 'g08_owner_operation_approval_links','g08_owner_operation_receipts','g08_identity_administrator_events'] LOOP
  EXECUTE format('CREATE CONSTRAINT TRIGGER g08_owner_complete_history AFTER INSERT ON public.%I DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.g08_check_owner_history()',t);
 END LOOP;
END $triggers$;
REVOKE CREATE ON SCHEMA public FROM nxr_g08_owner_history_check_owner;
-- Deliberately fail installation if old owner history lacks real admission/evidence.
-- No automatic grandfathering or invented verified identity/status is permitted.
SELECT public.g08_assert_owner_history();
COMMIT;
