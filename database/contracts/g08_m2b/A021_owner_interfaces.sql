-- STAGED / UNEXECUTED. Private primitives are persistence, never authority sources.
-- No runtime grants, writer table grants, identity provider or success stub.
BEGIN;
CREATE FUNCTION public.g08_owner_decision_time(p_authorization_id uuid,p_assertion_id uuid) RETURNS timestamptz
LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE a public.g08_owner_operation_authorizations;
 s public.g08_owner_authorization_status_history;
 identity public.g08_owner_operator_assertions;
 already_consumed boolean; decision_time timestamptz;
BEGIN
 PERFORM public.g08_lock_identity_history();
 -- All reads are separate commands after acquiring the transaction lock.
 SELECT * INTO STRICT a FROM public.g08_owner_operation_authorizations WHERE authorization_id=p_authorization_id;
 SELECT * INTO STRICT s FROM public.g08_owner_authorization_status_history
  WHERE authorization_id=p_authorization_id ORDER BY revision DESC LIMIT 1;
 SELECT * INTO STRICT identity FROM public.g08_owner_operator_assertions WHERE assertion_id=p_assertion_id;
 SELECT EXISTS(SELECT 1 FROM public.g08_owner_operation_consumptions WHERE owner_operation_id=a.owner_operation_id)
  INTO already_consumed;
 decision_time:=pg_catalog.clock_timestamp();
 IF s.status<>'ADMITTED' OR s.revision<>1 OR s.occurred_at>decision_time OR already_consumed
  OR a.valid_from>decision_time OR a.valid_to<=decision_time
  OR (identity.authorization_id,identity.owner_operation_id,identity.person_ref,identity.purpose,
      identity.authentication_evidence_ref,identity.authentication_evidence_sha256,identity.db_session_user)
   IS DISTINCT FROM (a.authorization_id,a.owner_operation_id,a.operator_person_ref,'EXECUTION'::text,
      a.operator_authentication_evidence_ref,a.operator_authentication_evidence_sha256,session_user::text)
  OR identity.verified_at>decision_time OR identity.valid_until<=decision_time THEN
  RAISE EXCEPTION 'G08 owner authorization not effective, consumed or operator mismatch' USING ERRCODE='42501';
 END IF;
 RETURN decision_time;
END $$;
REVOKE ALL ON FUNCTION public.g08_owner_decision_time(uuid,uuid)
 FROM PUBLIC,anon,authenticated,service_role,nxr_g08_identity_fn_owner,nxr_g08_owner_fn_owner,nxr_g08_owner_reader_owner;

CREATE FUNCTION public.g08_stage_owner_status(
 p_authorization_id uuid,p_status_id uuid,p_status text,p_expected_predecessor uuid,
 p_assertion_id uuid,p_evidence_ref public.g08_evidence_ref,p_rationale public.g08_rationale
) RETURNS uuid LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE a public.g08_owner_operation_authorizations; previous public.g08_owner_authorization_status_history;
 has_previous boolean; decision_time timestamptz; manifest jsonb;
BEGIN
 PERFORM public.g08_lock_identity_history();
 SELECT * INTO STRICT a FROM public.g08_owner_operation_authorizations WHERE authorization_id=p_authorization_id;
 SELECT * INTO previous FROM public.g08_owner_authorization_status_history
  WHERE authorization_id=p_authorization_id ORDER BY revision DESC LIMIT 1;
 has_previous:=FOUND;
 SELECT coalesce(jsonb_agg(to_jsonb(l)-'authorization_id' ORDER BY l.approval_ref::text),'[]'::jsonb)
  INTO manifest FROM public.g08_owner_operation_approval_links l WHERE l.authorization_id=a.authorization_id;
 IF p_status IS NULL OR p_status NOT IN ('ADMITTED','REVOKED','INVALIDATED')
  OR (NOT has_previous AND (p_status<>'ADMITTED' OR p_expected_predecessor IS NOT NULL))
  OR (has_previous AND (previous.status<>'ADMITTED' OR p_status='ADMITTED'
   OR p_expected_predecessor IS DISTINCT FROM previous.status_id)) THEN
  RAISE EXCEPTION 'G08 invalid owner status transition or stale predecessor' USING ERRCODE='23514';
 END IF;
 decision_time:=pg_catalog.clock_timestamp();
 INSERT INTO public.g08_owner_authorization_status_history VALUES
 (p_status_id,a.authorization_id,a.owner_operation_id,
  CASE WHEN has_previous THEN previous.revision+1 ELSE 1 END,
  CASE WHEN has_previous THEN previous.status_id END,
  CASE WHEN has_previous THEN previous.revision END,p_status,p_assertion_id,decision_time,
  session_user,current_user,p_evidence_ref,p_rationale,manifest);
 PERFORM public.g08_assert_owner_history();
 RETURN p_status_id; -- staged only; COMMIT acknowledgement is still required
END $$;
REVOKE ALL ON FUNCTION public.g08_stage_owner_status(uuid,uuid,text,uuid,uuid,public.g08_evidence_ref,public.g08_rationale)
 FROM PUBLIC,anon,authenticated,service_role,nxr_g08_identity_fn_owner,nxr_g08_owner_fn_owner;

CREATE FUNCTION public.g08_stage_owner_admission(
 p_authorization public.g08_owner_operation_authorizations,
 p_assertion public.g08_owner_operator_assertions,
 p_approvals public.g08_owner_operation_approval_links[],p_status_id uuid,
 p_evidence_ref public.g08_evidence_ref,p_rationale public.g08_rationale
) RETURNS uuid LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 PERFORM public.g08_lock_identity_history();
 PERFORM public.g08_assert_owner_history();
 IF p_approvals IS NULL OR cardinality(p_approvals)=0 OR p_assertion.purpose IS DISTINCT FROM 'ADMISSION' THEN
  RAISE EXCEPTION 'G08 admission evidence incomplete' USING ERRCODE='23514';
 END IF;
 INSERT INTO public.g08_owner_operation_authorizations SELECT p_authorization.*;
 INSERT INTO public.g08_owner_operator_assertions SELECT p_assertion.*;
 INSERT INTO public.g08_owner_operation_approval_links SELECT x.* FROM unnest(p_approvals) x;
 RETURN public.g08_stage_owner_status(p_authorization.authorization_id,p_status_id,'ADMITTED',NULL,
  p_assertion.assertion_id,p_evidence_ref,p_rationale);
END $$;
REVOKE ALL ON FUNCTION public.g08_stage_owner_admission(public.g08_owner_operation_authorizations,
 public.g08_owner_operator_assertions,public.g08_owner_operation_approval_links[],uuid,public.g08_evidence_ref,public.g08_rationale)
 FROM PUBLIC,anon,authenticated,service_role,nxr_g08_identity_fn_owner,nxr_g08_owner_fn_owner;

CREATE FUNCTION public.g08_stage_owner_consumption(p_proof public.g08_owner_execution_evidence)
RETURNS uuid LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE event public.g08_identity_administrator_events;
 receipt public.g08_owner_operation_receipts;
BEGIN
 PERFORM public.g08_lock_identity_history();
 -- Event/version/receipt have been staged by the future trusted owner wrapper in
 -- this SAME transaction; no intermediate commit, and no caller-chosen replay key.
 SELECT * INTO STRICT event FROM public.g08_identity_administrator_events WHERE event_id=p_proof.event_id;
 SELECT * INTO STRICT receipt FROM public.g08_owner_operation_receipts WHERE event_id=p_proof.event_id;
 PERFORM public.g08_owner_decision_time(p_proof.authorization_id,p_proof.assertion_id);
 IF event.occurred_at>pg_catalog.clock_timestamp() OR receipt.db_session_user<>session_user::text
  OR receipt.db_effective_role<>current_user::text THEN
  RAISE EXCEPTION 'G08 execution session or decision mismatch' USING ERRCODE='42501';
 END IF;
 INSERT INTO public.g08_owner_execution_evidence SELECT p_proof.*;
 INSERT INTO public.g08_owner_operation_consumptions VALUES
 (p_proof.owner_operation_id,p_proof.authorization_id,p_proof.event_id,p_proof.evidence_id,event.occurred_at);
 PERFORM public.g08_assert_owner_history();
 RETURN p_proof.event_id;
END $$;
REVOKE ALL ON FUNCTION public.g08_stage_owner_consumption(public.g08_owner_execution_evidence)
 FROM PUBLIC,anon,authenticated,service_role,nxr_g08_identity_fn_owner,nxr_g08_owner_fn_owner;

-- The real provider must establish independently authenticated natural person,
-- operation/session binding, current permission, approved manifest/digests and,
-- for execution, technical evidence + cross-system fencing. No JSON flag qualifies.
CREATE FUNCTION public.g08_verify_owner_trust(p_action text,p_context jsonb) RETURNS uuid
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 RAISE EXCEPTION 'IDENTITY_ASSURANCE_UNAVAILABLE: accepted owner verifier, policy, D08/D10 and fencing adapters required'
 USING ERRCODE='55000';
END $$;
REVOKE ALL ON FUNCTION public.g08_verify_owner_trust(text,jsonb) FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION public.g08_verify_owner_trust(text,jsonb),public.g08_lock_identity_history()
 TO nxr_g08_owner_fn_owner,nxr_g08_owner_reader_owner;
GRANT CREATE ON SCHEMA public TO nxr_g08_owner_fn_owner,nxr_g08_owner_reader_owner;

CREATE FUNCTION public.g08_control_owner_operation(p_action text,p_context jsonb) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF p_action IS NULL OR p_action NOT IN ('ADMISSION','REVOCATION','INVALIDATION','EXECUTION') THEN
  RAISE EXCEPTION 'invalid owner action' USING ERRCODE='22023';
 END IF;
 PERFORM public.g08_lock_identity_history();
 PERFORM public.g08_assert_owner_history();
 PERFORM public.g08_verify_owner_trust(p_action,p_context);
 RAISE EXCEPTION 'owner execution adapter unavailable' USING ERRCODE='55000';
END $$;
ALTER FUNCTION public.g08_control_owner_operation(text,jsonb) OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_control_owner_operation(text,jsonb) FROM PUBLIC,anon,authenticated,service_role,nxr_g08_identity_fn_owner;

CREATE FUNCTION public.g08_read_owner_operation_receipt(p_context jsonb) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 PERFORM public.g08_lock_identity_history();
 PERFORM public.g08_assert_owner_history();
 -- Replay/reconciliation requires CURRENT D10 read permission, independently of
 -- historical mutation permission. Revocation does not delete an existing receipt.
 PERFORM public.g08_verify_owner_trust('RECONCILIATION',p_context);
 RAISE EXCEPTION 'authorized owner receipt projection unavailable' USING ERRCODE='55000';
END $$;
ALTER FUNCTION public.g08_read_owner_operation_receipt(jsonb) OWNER TO nxr_g08_owner_reader_owner;
REVOKE ALL ON FUNCTION public.g08_read_owner_operation_receipt(jsonb) FROM PUBLIC,anon,authenticated,service_role,nxr_g08_identity_fn_owner;

CREATE FUNCTION public.g08_read_owner_authorization_status(p_context jsonb) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 PERFORM public.g08_lock_identity_history();
 PERFORM public.g08_assert_owner_history();
 PERFORM public.g08_verify_owner_trust('RECONCILIATION',p_context);
 RAISE EXCEPTION 'authorized owner status projection unavailable' USING ERRCODE='55000';
END $$;
ALTER FUNCTION public.g08_read_owner_authorization_status(jsonb) OWNER TO nxr_g08_owner_reader_owner;
REVOKE ALL ON FUNCTION public.g08_read_owner_authorization_status(jsonb) FROM PUBLIC,anon,authenticated,service_role,nxr_g08_identity_fn_owner;
REVOKE CREATE ON SCHEMA public FROM nxr_g08_owner_fn_owner,nxr_g08_owner_reader_owner;
-- Functions own no tables, have no DML or runtime memberships, and remain closed.
COMMIT;
