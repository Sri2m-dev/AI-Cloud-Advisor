-- Private persistence primitive, not an authorization/admission interface.
-- Deliberately SECURITY INVOKER with no grants, no runtime table privileges.
-- M2-B must invoke only from a reviewed, verified execution wrapper after every
-- identity/policy/root/digest guard. Do not expose or grant this primitive directly.
BEGIN;
CREATE FUNCTION public.g08_stage_authenticated_history(
 p_version public.g08_identity_administrator_versions,
 p_event public.g08_identity_administrator_events,
 p_receipt public.g08_administration_receipts,
 p_approval_ids uuid[]
) RETURNS uuid LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog SET timezone='UTC' AS $$
DECLARE c public.g08_identity_administrators;
 v public.g08_identity_administrator_versions := p_version;
 e public.g08_identity_administrator_events := p_event;
 h public.g08_administration_receipts := p_receipt;
 decision_time timestamptz; found_current boolean;
BEGIN
 PERFORM public.g08_lock_identity_history();
 PERFORM public.g08_assert_identity_history();
 -- Fresh command snapshot after global lock; no pre-lock current/key decision.
 SELECT * INTO c FROM public.g08_identity_administrators WHERE administrator_id=e.administrator_id;
 found_current:=FOUND;
 IF e.execution_mode IS DISTINCT FROM 'authenticated' THEN
  RAISE EXCEPTION 'owner execution interface unresolved' USING ERRCODE='55000';
 END IF;
 IF EXISTS(SELECT 1 FROM public.g08_identity_administrator_events WHERE request_id=e.request_id) THEN
  RAISE EXCEPTION 'REQUEST_CONSUMED: reconcile original receipt' USING ERRCODE='23505';
 END IF;
 IF EXISTS(SELECT 1 FROM public.g08_administration_receipts WHERE
  (namespace,scope_key,operation,idempotency_key)=(h.namespace,h.scope_key,h.operation,h.idempotency_key)) THEN
  RAISE EXCEPTION 'IDEMPOTENCY_CONFLICT: authorized replay must use receipt interface' USING ERRCODE='23505';
 END IF;
 IF p_approval_ids IS NULL OR cardinality(p_approval_ids)=0
  OR cardinality(p_approval_ids)<> (SELECT count(DISTINCT x) FROM unnest(p_approval_ids) x)
  OR array_position(p_approval_ids,NULL) IS NOT NULL THEN
  RAISE EXCEPTION 'invalid approval set' USING ERRCODE='23514';
 END IF;
 IF (e.action='grant' AND found_current) OR (e.action<>'grant' AND
  (NOT found_current OR c.revision IS DISTINCT FROM e.before_revision OR c.revoked_at IS NOT NULL)) THEN
  RAISE EXCEPTION 'REVISION_CONFLICT' USING ERRCODE='23514';
 END IF;
 -- A wall clock captured after protected reads, never transaction_timestamp/now().
 decision_time:=pg_catalog.clock_timestamp();
 IF e.action IN ('grant','revise') AND EXISTS(
  SELECT 1 FROM public.g08_identity_administrators other
  WHERE other.administrator_id<>v.administrator_id AND other.subject_auth_uid=v.subject_auth_uid
   AND other.revoked_at IS NULL AND v.revoked_at IS NULL
   AND (other.valid_to IS NULL OR v.valid_from<other.valid_to)
   AND (v.valid_to IS NULL OR other.valid_from<v.valid_to)) THEN
  RAISE EXCEPTION 'overlapping unrevoked subject interval' USING ERRCODE='23514';
 END IF;
 e.occurred_at:=decision_time;
 IF e.action='revoke' THEN v.revoked_at:=decision_time; END IF;
 h.occurred_at:=decision_time;
 h.result:=jsonb_set(h.result,'{occurred_at}',to_jsonb(decision_time),false);
 IF e.action='grant' THEN
  INSERT INTO public.g08_identity_administrators VALUES
   (v.administrator_id,v.subject_auth_uid,v.valid_from,v.valid_to,v.revision,v.revoked_at,
    v.bootstrap_evidence_ref,v.origin_event_id,v.current_event_id);
 END IF;
 INSERT INTO public.g08_identity_administrator_versions SELECT v.*;
 INSERT INTO public.g08_identity_administrator_events SELECT e.*;
 INSERT INTO public.g08_identity_administrator_event_approvals(event_id,approval_id)
  SELECT e.event_id,x FROM unnest(p_approval_ids) x;
 INSERT INTO public.g08_administration_receipts SELECT h.*;
 IF e.action<>'grant' THEN
  UPDATE public.g08_identity_administrators SET valid_to=v.valid_to,revision=v.revision,
   revoked_at=v.revoked_at,current_event_id=v.current_event_id WHERE administrator_id=v.administrator_id;
 END IF;
 PERFORM public.g08_assert_identity_history();
 -- UUID is staged only: caller must not publish durable completion before COMMIT ack.
 RETURN e.event_id;
END $$;
REVOKE ALL ON FUNCTION public.g08_stage_authenticated_history(
 public.g08_identity_administrator_versions,public.g08_identity_administrator_events,
 public.g08_administration_receipts,uuid[])
 FROM PUBLIC,anon,authenticated,service_role,nxr_g08_identity_fn_owner;
COMMIT;
