-- Install only after S020, under continuous writer quiescence. No runtime activation.
BEGIN;
-- ALTER FUNCTION OWNER requires CREATE for the recipient during transfer only.
GRANT CREATE ON SCHEMA public TO nxr_g08_history_check_owner, nxr_g08_identity_fn_owner;

CREATE FUNCTION public.g08_lock_identity_history() RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF current_setting('transaction_isolation') <> 'read committed' THEN
  RAISE EXCEPTION 'G08 requires READ COMMITTED' USING ERRCODE='25001';
 END IF;
 PERFORM pg_catalog.pg_advisory_xact_lock(16002003001::bigint);
END $$;
REVOKE ALL ON FUNCTION public.g08_lock_identity_history() FROM PUBLIC, anon, authenticated, service_role;

-- Read-only, full-history validation. Full scan intentionally includes unexpected extras.
-- VOLATILE gets fresh command snapshots. Assert explicit unfiltered SELECT policies
-- before reads: row_security=off would reject even the intended NOBYPASSRLS reader.
CREATE FUNCTION public.g08_assert_identity_history() RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog SET row_security=on SET timezone='UTC' AS $$
DECLARE c public.g08_identity_administrators;
 v public.g08_identity_administrator_versions;
 p public.g08_identity_administrator_versions;
 e public.g08_identity_administrator_events;
 q public.g08_identity_administrator_requests;
 h public.g08_administration_receipts;
 o public.g08_owner_operation_receipts;
 a public.g08_owner_operation_authorizations;
 n bigint; previous_time timestamptz; ids jsonb; expected jsonb; r jsonb;
BEGIN
 -- No writes, locks, dynamic SQL, caller-supplied relation names or exception suppression.
 IF (SELECT count(*) FROM pg_catalog.pg_class cl
  JOIN pg_catalog.pg_namespace ns ON ns.oid=cl.relnamespace
  WHERE ns.nspname='public' AND cl.relname IN (
   'g08_identity_administrators','g08_identity_administrator_versions',
   'g08_identity_administrator_events','g08_identity_administrator_requests',
   'g08_identity_administrator_approvals','g08_identity_administrator_approval_withdrawals',
   'g08_identity_administrator_event_approvals','g08_administration_receipts',
   'g08_owner_operation_authorizations','g08_owner_operation_approval_links','g08_owner_operation_receipts')
  AND cl.relrowsecurity AND cl.relforcerowsecurity
  AND cl.relowner<>(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user)
  AND EXISTS(SELECT 1 FROM pg_catalog.pg_policy pol WHERE pol.polrelid=cl.oid
   AND pol.polname='g08_checker_select' AND pol.polcmd='r' AND pol.polpermissive
   AND pol.polroles=ARRAY[(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user)]
   AND pg_catalog.pg_get_expr(pol.polqual,pol.polrelid)='true')
  AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_policy pol WHERE pol.polrelid=cl.oid
   AND NOT pol.polpermissive AND pol.polcmd IN ('r','*')))<>11 THEN
  RAISE EXCEPTION 'G08 checker visibility is not qualified' USING ERRCODE='42501';
 END IF;
 IF EXISTS(SELECT 1 FROM public.g08_identity_administrator_versions x
   WHERE NOT EXISTS(SELECT 1 FROM public.g08_identity_administrators y WHERE y.administrator_id=x.administrator_id))
 OR EXISTS(SELECT 1 FROM public.g08_identity_administrator_events x
   WHERE NOT EXISTS(SELECT 1 FROM public.g08_identity_administrator_versions y
    WHERE (y.administrator_id,y.revision,y.event_id)=(x.administrator_id,x.after_revision,x.event_id)))
 OR EXISTS(SELECT 1 FROM public.g08_administration_receipts x WHERE x.namespace='identity_admin'
   AND NOT EXISTS(SELECT 1 FROM public.g08_identity_administrator_events y WHERE y.event_id=x.event_id AND y.execution_mode='authenticated'))
 OR EXISTS(SELECT 1 FROM public.g08_owner_operation_receipts x
   WHERE NOT EXISTS(SELECT 1 FROM public.g08_identity_administrator_events y WHERE y.event_id=x.event_id AND y.execution_mode='owner_controlled')) THEN
  RAISE EXCEPTION 'G08 orphan history or receipt' USING ERRCODE='23514';
 END IF;
 FOR c IN SELECT * FROM public.g08_identity_administrators LOOP
  n:=0; previous_time:=NULL;
  FOR v IN SELECT * FROM public.g08_identity_administrator_versions
   WHERE administrator_id=c.administrator_id ORDER BY revision LOOP
   n:=n+1;
   IF v.revision<>n OR v.origin_event_id<>c.origin_event_id
    OR v.subject_auth_uid<>c.subject_auth_uid OR v.valid_from<>c.valid_from
    OR v.bootstrap_evidence_ref<>c.bootstrap_evidence_ref OR v.current_event_id<>v.event_id THEN
    RAISE EXCEPTION 'G08 revision gap or changed provenance' USING ERRCODE='23514';
   END IF;
   SELECT * INTO STRICT e FROM public.g08_identity_administrator_events
    WHERE event_id=v.event_id AND administrator_id=v.administrator_id AND after_revision=v.revision;
   IF previous_time IS NOT NULL AND e.occurred_at<previous_time THEN
    RAISE EXCEPTION 'G08 nonmonotonic decision time' USING ERRCODE='23514';
   END IF;
   IF n=1 THEN
    IF e.action<>'grant' OR e.before_revision IS NOT NULL OR v.revoked_at IS NOT NULL
     OR (v.valid_to IS NOT NULL AND v.valid_to<=e.occurred_at)
     OR c.origin_event_id<>e.event_id THEN
     RAISE EXCEPTION 'G08 invalid initial history' USING ERRCODE='23514';
    END IF;
   ELSE
    IF e.before_revision IS DISTINCT FROM n-1 OR e.action='grant' OR p.revoked_at IS NOT NULL
     OR (e.action='revise' AND (p.valid_from>e.occurred_at OR (p.valid_to IS NOT NULL AND p.valid_to<=e.occurred_at))) THEN
     RAISE EXCEPTION 'G08 invalid predecessor or reactivation' USING ERRCODE='23514';
    END IF;
    IF (e.action='revise' AND (v.revoked_at IS NOT NULL OR v.valid_to IS NOT DISTINCT FROM p.valid_to
         OR (v.valid_to IS NOT NULL AND v.valid_to<=e.occurred_at)))
     OR (e.action='revoke' AND (v.revoked_at IS DISTINCT FROM e.occurred_at
         OR v.valid_to IS DISTINCT FROM p.valid_to)) THEN
     RAISE EXCEPTION 'G08 invalid state delta' USING ERRCODE='23514';
    END IF;
   END IF;
   SELECT coalesce(jsonb_agg(approval_id::text ORDER BY approval_id::text),'[]'::jsonb)
    INTO ids FROM public.g08_identity_administrator_event_approvals WHERE event_id=e.event_id;
   IF e.execution_mode='authenticated' THEN
    SELECT * INTO STRICT q FROM public.g08_identity_administrator_requests WHERE request_id=e.request_id;
    SELECT * INTO STRICT h FROM public.g08_administration_receipts WHERE event_id=e.event_id AND namespace='identity_admin';
    IF EXISTS(SELECT 1 FROM public.g08_owner_operation_receipts WHERE event_id=e.event_id)
     OR (q.administrator_id,q.action,q.requester_auth_uid,q.intended_executor_auth_uid,q.intent_sha256,q.rationale,q.evidence_ref)
       IS DISTINCT FROM (e.administrator_id,e.action,e.requester_auth_uid,e.executor_auth_uid,e.intent_sha256,e.rationale,e.evidence_ref)
     OR q.expected_revision IS DISTINCT FROM e.before_revision OR q.submitted_at>e.occurred_at
     OR (e.action='grant' AND (q.subject_auth_uid,q.valid_from,q.valid_to) IS DISTINCT FROM (v.subject_auth_uid,v.valid_from,v.valid_to))
     OR (e.action='revise' AND q.valid_to IS DISTINCT FROM v.valid_to)
     OR ids='[]'::jsonb THEN
     RAISE EXCEPTION 'G08 request or mode mismatch' USING ERRCODE='23514';
    END IF;
    IF EXISTS(SELECT 1 FROM public.g08_identity_administrator_event_approvals l
     JOIN public.g08_identity_administrator_approvals ap USING(approval_id)
     WHERE l.event_id=e.event_id AND
      (ap.request_id<>e.request_id OR ap.intent_sha256<>e.intent_sha256 OR ap.policy_version<>q.policy_version
       OR ap.approver_auth_uid=q.requester_auth_uid OR ap.approver_person_ref=q.requester_person_ref
       OR ap.approved_at>e.occurred_at OR ap.expires_at<=e.occurred_at
       OR EXISTS(SELECT 1 FROM public.g08_identity_administrator_approval_withdrawals w
         WHERE w.approval_id=ap.approval_id AND w.occurred_at<=e.occurred_at))) THEN
     RAISE EXCEPTION 'G08 invalid approval evidence at recorded decision time' USING ERRCODE='23514';
    END IF;
    -- Current-time expiry/withdrawal is not applied retroactively to committed history.
    expected:=jsonb_build_object('version','nxr-g08-identity-admin-execution-v1',
     'namespace','identity_admin','scope_key','global','operation',e.action,
     'request_id',e.request_id,'intent_sha256',e.intent_sha256,'executor_auth_uid',e.executor_auth_uid,
     'approval_ids',ids,'idempotency_key',h.idempotency_key);
    r:=jsonb_build_object('event_id',e.event_id,'request_id',e.request_id,'administrator_id',e.administrator_id,
     'action',e.action,'before_revision',e.before_revision,'resulting_revision',e.after_revision,
     'requester_auth_uid',e.requester_auth_uid,'executor_auth_uid',e.executor_auth_uid,
     'approval_ids',ids,'occurred_at',e.occurred_at,'intent_sha256',e.intent_sha256,
     'fingerprint_version',e.fingerprint_version,'request_digest',e.request_digest,'idempotency_key',h.idempotency_key);
    IF h.canonical_request IS DISTINCT FROM expected OR h.result IS DISTINCT FROM r
     OR (h.scope_key,h.operation,h.actor_auth_uid,h.fingerprint_version,h.request_digest,h.occurred_at)
       IS DISTINCT FROM ('global'::text,e.action,e.executor_auth_uid,e.fingerprint_version,e.request_digest,e.occurred_at)
     OR e.fingerprint_version<>'nxr-g08-identity-admin-execution-v1' THEN
     RAISE EXCEPTION 'G08 human receipt or exact approval-set mismatch' USING ERRCODE='23514';
    END IF;
   ELSE
    SELECT * INTO STRICT o FROM public.g08_owner_operation_receipts WHERE event_id=e.event_id;
    SELECT * INTO STRICT a FROM public.g08_owner_operation_authorizations WHERE authorization_id=o.authorization_id;
    SELECT coalesce(jsonb_agg(approval_ref::text ORDER BY approval_ref::text),'[]'::jsonb)
     INTO ids FROM public.g08_owner_operation_approval_links WHERE authorization_id=a.authorization_id;
    IF EXISTS(SELECT 1 FROM public.g08_identity_administrator_event_approvals WHERE event_id=e.event_id)
     OR o.approval_refs IS DISTINCT FROM ids
     OR EXISTS(SELECT 1 FROM public.g08_administration_receipts WHERE event_id=e.event_id)
     OR (a.owner_operation_id,a.administrator_id,a.operation,a.expected_revision,a.intent_sha256)
      IS DISTINCT FROM (e.owner_operation_id,e.administrator_id,e.action,e.before_revision,e.intent_sha256)
     OR (o.owner_operation_id,o.operation,o.intent_sha256,o.fingerprint_version,o.request_digest,o.occurred_at,o.db_effective_role)
      IS DISTINCT FROM (e.owner_operation_id,e.action,e.intent_sha256,e.fingerprint_version,e.request_digest,e.occurred_at,e.executor_db_role)
     OR (o.authorization_sha256,o.approval_manifest_sha256,o.policy_version,o.operator_person_ref,
         o.operator_authentication_evidence_ref,o.operator_authentication_evidence_sha256)
      IS DISTINCT FROM (a.authorization_sha256,a.approval_manifest_sha256,a.policy_version,a.operator_person_ref,
         a.operator_authentication_evidence_ref,a.operator_authentication_evidence_sha256)
     OR a.valid_from>e.occurred_at OR a.valid_to<=e.occurred_at
     OR NOT EXISTS(SELECT 1 FROM public.g08_owner_operation_approval_links WHERE authorization_id=a.authorization_id)
     OR EXISTS(SELECT 1 FROM public.g08_owner_operation_approval_links WHERE authorization_id=a.authorization_id AND approver_person_ref=a.requester_person_ref)
     OR e.fingerprint_version<>'nxr-g08-owner-administration-v1' THEN
     RAISE EXCEPTION 'G08 owner linkage mismatch' USING ERRCODE='23514';
    END IF;
    expected:=jsonb_build_object('version','nxr-g08-owner-administration-v1',
     'owner_operation_id',o.owner_operation_id,'operation',o.operation,'scope_key',o.scope_key,
     'authorization_id',o.authorization_id,'authorization_sha256',o.authorization_sha256,
     'approval_manifest_sha256',o.approval_manifest_sha256,'policy_version',o.policy_version,
     'operator',jsonb_build_object('person_ref',o.operator_person_ref,
       'authentication_evidence_sha256',o.operator_authentication_evidence_sha256,
       'verified_auth_uid',o.verified_operator_auth_uid,'db_session_user',o.db_session_user),
     'procedure_identity',o.procedure_identity,'procedure_version',o.procedure_version,
     'mutation',a.mutation,'idempotency_key',o.idempotency_key);
    IF o.canonical_request IS DISTINCT FROM expected THEN
     RAISE EXCEPTION 'G08 owner canonical linkage mismatch' USING ERRCODE='23514';
    END IF;
    -- Partial DBR-02 evidence comparison only. No owner writer is installed; the
    -- accepted status, manifest serializer, identity and technical evidence contracts
    -- are prerequisites to admission. Approval is never a technical-control PASS.
   END IF;
   p:=v; previous_time:=e.occurred_at;
  END LOOP;
  IF n=0 OR n<>c.revision OR (to_jsonb(p)-'event_id') IS DISTINCT FROM to_jsonb(c) THEN
   RAISE EXCEPTION 'G08 current snapshot mismatch or missing history' USING ERRCODE='23514';
  END IF;
 END LOOP;
END $$;
ALTER FUNCTION public.g08_assert_identity_history() OWNER TO nxr_g08_history_check_owner;
REVOKE ALL ON FUNCTION public.g08_assert_identity_history() FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION public.g08_assert_identity_history() TO nxr_g08_identity_fn_owner;

CREATE FUNCTION public.g08_check_identity_admin_history() RETURNS trigger
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog SET row_security=on AS $$
BEGIN
 PERFORM public.g08_assert_identity_history();
 RETURN NULL;
END $$;
ALTER FUNCTION public.g08_check_identity_admin_history() OWNER TO nxr_g08_history_check_owner;
REVOKE ALL ON FUNCTION public.g08_check_identity_admin_history() FROM PUBLIC,anon,authenticated,service_role;

CREATE FUNCTION public.g08_deny_history_mutation() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 RAISE EXCEPTION 'G08 append-only history' USING ERRCODE='55000';
END $$;
REVOKE ALL ON FUNCTION public.g08_deny_history_mutation() FROM PUBLIC,anon,authenticated,service_role;

-- BEFORE STATEMENT: lock precedes any tuple locks, including missing-row operations.
CREATE FUNCTION public.g08_guard_history_write() RETURNS trigger
LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 PERFORM public.g08_lock_identity_history();
 RETURN NULL;
END $$;
REVOKE ALL ON FUNCTION public.g08_guard_history_write() FROM PUBLIC,anon,authenticated,service_role;

CREATE FUNCTION public.g08_guard_current_update() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF (NEW.administrator_id,NEW.subject_auth_uid,NEW.valid_from,NEW.bootstrap_evidence_ref,NEW.origin_event_id)
  IS DISTINCT FROM (OLD.administrator_id,OLD.subject_auth_uid,OLD.valid_from,OLD.bootstrap_evidence_ref,OLD.origin_event_id)
  OR OLD.revoked_at IS NOT NULL OR OLD.revision=9223372036854775807
  OR NEW.revision<>OLD.revision+1 THEN
  RAISE EXCEPTION 'G08 protected current provenance or revision' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.g08_guard_current_update() FROM PUBLIC,anon,authenticated,service_role;

DO $triggers$
DECLARE t text;
BEGIN
 FOREACH t IN ARRAY ARRAY[
 'g08_identity_administrators','g08_identity_administrator_versions',
 'g08_identity_administrator_events','g08_identity_administrator_requests',
 'g08_identity_administrator_approvals','g08_identity_administrator_approval_withdrawals',
 'g08_identity_administrator_event_approvals','g08_administration_receipts',
 'g08_owner_operation_authorizations','g08_owner_operation_approval_links','g08_owner_operation_receipts'] LOOP
  EXECUTE format('CREATE TRIGGER g08_global_lock BEFORE INSERT OR UPDATE OR DELETE ON public.%I FOR EACH STATEMENT EXECUTE FUNCTION public.g08_guard_history_write()',t);
  EXECUTE format('CREATE TRIGGER g08_no_truncate BEFORE TRUNCATE ON public.%I FOR EACH STATEMENT EXECUTE FUNCTION public.g08_deny_history_mutation()',t);
  IF t='g08_identity_administrators' THEN
   EXECUTE format('CREATE TRIGGER g08_no_delete BEFORE DELETE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.g08_deny_history_mutation()',t);
  ELSE
   EXECUTE format('CREATE TRIGGER g08_append_only BEFORE UPDATE OR DELETE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.g08_deny_history_mutation()',t);
  END IF;
  EXECUTE format('CREATE CONSTRAINT TRIGGER g08_complete_history AFTER INSERT OR UPDATE ON public.%I DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.g08_check_identity_admin_history()',t);
 END LOOP;
END $triggers$;
CREATE TRIGGER g08_current_provenance BEFORE UPDATE ON public.g08_identity_administrators
 FOR EACH ROW EXECUTE FUNCTION public.g08_guard_current_update();

-- Explicit unresolved dependency, not a caller-provided boolean or JSON assurance.
CREATE FUNCTION public.g08_require_verified_execution_interface() RETURNS void
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 RAISE EXCEPTION 'POLICY_UNRESOLVED: trusted identity, authority, approval policy, D08 and D10 interfaces required'
 USING ERRCODE='55000';
END $$;
REVOKE ALL ON FUNCTION public.g08_require_verified_execution_interface() FROM PUBLIC,anon,authenticated,service_role;

CREATE FUNCTION public.g08_administer_identity_administrator(p_request jsonb) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 PERFORM public.g08_lock_identity_history();
 -- Separate command after the lock wait, never a pre-lock protected snapshot.
 PERFORM public.g08_assert_identity_history();
 PERFORM public.g08_require_verified_execution_interface();
 RAISE EXCEPTION 'unreachable execution boundary' USING ERRCODE='55000';
END $$;
ALTER FUNCTION public.g08_administer_identity_administrator(jsonb) OWNER TO nxr_g08_identity_fn_owner;
REVOKE ALL ON FUNCTION public.g08_administer_identity_administrator(jsonb) FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION public.g08_lock_identity_history(),
 public.g08_require_verified_execution_interface() TO nxr_g08_identity_fn_owner;
-- No runtime EXECUTE, table writes or approval admission. DBR-02 activation is separate.
REVOKE CREATE ON SCHEMA public FROM nxr_g08_history_check_owner, nxr_g08_identity_fn_owner;
COMMIT;
