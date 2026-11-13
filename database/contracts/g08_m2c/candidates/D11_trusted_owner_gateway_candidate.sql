-- UNAPPLIED CANDIDATE. Qualification only; never auto-install or activate r5.
-- Trust signatures are verified by the private SignedG08OwnerTrust adapter before
-- this narrow database writer is called. The writer rechecks persisted D10 state,
-- revocation, fencing, canonical history and the complete effect/receipt linkage
-- inside the same PostgreSQL transaction.
BEGIN;

DO $roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'nxr_g08_gateway_executor') THEN
        CREATE ROLE nxr_g08_gateway_executor NOLOGIN NOSUPERUSER NOBYPASSRLS
            NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
    END IF;
END
$roles$;

GRANT CREATE ON SCHEMA public TO nxr_g08_owner_fn_owner;

DO $privileges$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'g08_identity_administrators',
        'g08_identity_administrator_versions',
        'g08_identity_administrator_events',
        'g08_owner_operation_authorizations',
        'g08_owner_operation_approval_links',
        'g08_owner_operator_assertions',
        'g08_owner_authorization_status_history',
        'g08_owner_execution_evidence',
        'g08_owner_operation_consumptions',
        'g08_owner_operation_receipts',
        'g08_d10_policy_versions',
        'g08_d10_authority_state',
        'g08_d10_approval_evidence',
        'g08_d10_revocations',
        'g08_d10_fencing_state',
        'g08_d10_receipt_scope_bindings'
    ] LOOP
        EXECUTE format(
            'GRANT SELECT, INSERT, UPDATE ON public.%I TO nxr_g08_owner_fn_owner',
            table_name
        );
        EXECUTE format(
            'CREATE POLICY g08_owner_gateway_select ON public.%I '
            'FOR SELECT TO nxr_g08_owner_fn_owner USING (true)',
            table_name
        );
        EXECUTE format(
            'CREATE POLICY g08_owner_gateway_insert ON public.%I '
            'FOR INSERT TO nxr_g08_owner_fn_owner WITH CHECK (true)',
            table_name
        );
        EXECUTE format(
            'CREATE POLICY g08_owner_gateway_update ON public.%I '
            'FOR UPDATE TO nxr_g08_owner_fn_owner USING (true) WITH CHECK (true)',
            table_name
        );
    END LOOP;
END
$privileges$;

GRANT USAGE ON SCHEMA auth TO nxr_g08_owner_fn_owner;
GRANT SELECT (id) ON auth.users TO nxr_g08_owner_fn_owner;
GRANT EXECUTE ON FUNCTION public.g08_owner_decision_time(uuid, uuid)
    TO nxr_g08_owner_fn_owner;
GRANT EXECUTE ON FUNCTION public.g08_stage_owner_admission(
    public.g08_owner_operation_authorizations,
    public.g08_owner_operator_assertions,
    public.g08_owner_operation_approval_links[],
    uuid,
    public.g08_evidence_ref,
    public.g08_rationale
) TO nxr_g08_owner_fn_owner;
GRANT EXECUTE ON FUNCTION public.g08_stage_owner_status(
    uuid, uuid, text, uuid, uuid, public.g08_evidence_ref, public.g08_rationale
) TO nxr_g08_owner_fn_owner;
GRANT EXECUTE ON FUNCTION public.g08_stage_owner_consumption(
    public.g08_owner_execution_evidence
) TO nxr_g08_owner_fn_owner;

CREATE FUNCTION public.g08_gateway_stage_admission(
    p_package jsonb
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
    auth_record public.g08_owner_operation_authorizations;
    assertion public.g08_owner_operator_assertions;
    approvals public.g08_owner_operation_approval_links[];
BEGIN
    IF p_package IS NULL OR jsonb_typeof(p_package) <> 'object' THEN
        RAISE EXCEPTION 'invalid owner admission package' USING ERRCODE = '22023';
    END IF;
    SELECT * INTO auth_record
    FROM jsonb_populate_record(
        NULL::public.g08_owner_operation_authorizations, p_package->'authorization'
    );
    SELECT * INTO assertion
    FROM jsonb_populate_record(
        NULL::public.g08_owner_operator_assertions, p_package->'assertion'
    );
    SELECT coalesce(array_agg(row_value), ARRAY[]::public.g08_owner_operation_approval_links[])
    INTO approvals
    FROM (
        SELECT jsonb_populate_record(
            NULL::public.g08_owner_operation_approval_links, value
        ) AS row_value
        FROM jsonb_array_elements(p_package->'approvals')
    ) AS parsed;
    RETURN public.g08_stage_owner_admission(
        auth_record,
        assertion,
        approvals,
        (p_package->>'status_id')::uuid,
        p_package->>'evidence_ref',
        p_package->>'rationale'
    );
END
$$;
ALTER FUNCTION public.g08_gateway_stage_admission(jsonb) OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_gateway_stage_admission(jsonb)
    FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_gateway_stage_admission(jsonb)
    TO nxr_g08_gateway_executor;

CREATE FUNCTION public.g08_gateway_load_owner_operation(
    p_operation_id uuid
) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
    auth_record public.g08_owner_operation_authorizations;
    history jsonb;
    receipt jsonb;
BEGIN
    SELECT * INTO auth_record
    FROM public.g08_owner_operation_authorizations
    WHERE owner_operation_id = p_operation_id;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;
    SELECT coalesce(jsonb_agg(to_jsonb(s) ORDER BY s.revision), '[]'::jsonb)
    INTO history
    FROM public.g08_owner_authorization_status_history s
    WHERE s.authorization_id = auth_record.authorization_id;
    SELECT to_jsonb(r) || jsonb_build_object(
        'assertion_id', proof.assertion_id,
        'evidence_id', proof.evidence_id,
        'tenant_id', binding.tenant_id,
        'organization_id', binding.organization_id
    ) INTO receipt
    FROM public.g08_owner_operation_receipts r
    JOIN public.g08_owner_execution_evidence proof ON proof.event_id = r.event_id
    JOIN public.g08_d10_receipt_scope_bindings binding ON binding.event_id = r.event_id
    WHERE r.owner_operation_id = p_operation_id;
    RETURN jsonb_build_object(
        'authorization', to_jsonb(auth_record),
        'history', history,
        'receipt', receipt
    );
END
$$;
ALTER FUNCTION public.g08_gateway_load_owner_operation(uuid) OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_gateway_load_owner_operation(uuid)
    FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_gateway_load_owner_operation(uuid)
    TO nxr_g08_gateway_executor;

CREATE FUNCTION public.g08_gateway_execute_owner_operation(
    p_package jsonb
) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
    scope jsonb := p_package->'scope';
    auth_record public.g08_owner_operation_authorizations;
    assertion public.g08_owner_operator_assertions;
    event public.g08_identity_administrator_events;
    admin public.g08_identity_administrators;
    version_row public.g08_identity_administrator_versions;
    owner_receipt public.g08_owner_operation_receipts;
    proof public.g08_owner_execution_evidence;
    binding public.g08_d10_receipt_scope_bindings;
    policy_claims jsonb;
    selected_policy_version text;
    current_generation bigint;
    approval_count bigint;
    expected_approvals bigint;
    decision_time timestamptz;
    canonical_request jsonb;
    idempotency_key text;
    subject_uid uuid;
    previous public.g08_identity_administrators;
BEGIN
    IF p_package IS NULL OR jsonb_typeof(p_package) <> 'object'
       OR scope IS NULL OR jsonb_typeof(scope) <> 'object' THEN
        RAISE EXCEPTION 'invalid owner execution package' USING ERRCODE = '22023';
    END IF;
    IF session_user IN ('anon', 'authenticated', 'service_role') THEN
        RAISE EXCEPTION 'owner gateway is not available to browser roles' USING ERRCODE = '42501';
    END IF;

    PERFORM public.g08_lock_identity_history();
    PERFORM public.g08_assert_identity_history();
    PERFORM public.g08_assert_owner_history();

    SELECT * INTO STRICT auth_record
    FROM public.g08_owner_operation_authorizations
    WHERE authorization_id = (scope->>'authorization_id')::uuid
      AND owner_operation_id = (scope->>'operation_id')::uuid;

    SELECT current_policy_version INTO STRICT selected_policy_version
    FROM public.g08_d10_authority_state
    WHERE authorization_id = auth_record.authorization_id
    FOR UPDATE;
    IF selected_policy_version <> scope->>'policy_version' THEN
        RAISE EXCEPTION 'D10 policy version is stale' USING ERRCODE = '42501';
    END IF;
    SELECT p.claims INTO STRICT policy_claims
    FROM public.g08_d10_policy_versions p
    WHERE p.authorization_id = auth_record.authorization_id
      AND p.policy_version = selected_policy_version
      AND p.valid_from <= clock_timestamp()
      AND p.valid_to > clock_timestamp();
    IF (policy_claims->>'authorization_id', policy_claims->>'operation_id',
        policy_claims->>'tenant_id', policy_claims->>'organization_id',
        policy_claims->>'action', policy_claims->>'target_resource',
        policy_claims->>'version', policy_claims->>'requester_uid')
       IS DISTINCT FROM
       (auth_record.authorization_id::text, auth_record.owner_operation_id::text,
        scope->>'tenant_id', scope->>'organization_id', scope->>'action',
        scope->>'target_resource', scope->>'policy_version', scope->>'requester_uid')
       OR scope->>'tenant_id' <> scope->>'organization_id'
       OR auth_record.operation <> scope->>'action'
       OR policy_claims->'allowed_phases' IS NULL
       OR NOT (policy_claims->'allowed_phases' @> '["EXECUTION"]'::jsonb) THEN
        RAISE EXCEPTION 'D10 tenant, operation, resource, or phase mismatch'
            USING ERRCODE = '42501';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.g08_d10_revocations r
        WHERE r.authorization_id = auth_record.authorization_id
          AND ((r.subject_type = 'AUTHORIZATION'
                AND r.subject_id = auth_record.authorization_id::text)
            OR (r.subject_type = 'OPERATOR_EVIDENCE'
                AND r.subject_id = scope->>'operator_jti')
            OR (r.subject_type = 'FENCING_TOKEN'
                AND r.subject_id = scope->>'fence_jti')
            OR (r.subject_type = 'APPROVAL'
                AND r.subject_id IN (
                    SELECT jsonb_array_elements_text(scope->'approval_ids')
                )))
    ) THEN
        RAISE EXCEPTION 'D10 authorization, approval, operator, or fence is revoked'
            USING ERRCODE = '42501';
    END IF;

    expected_approvals := (policy_claims->>'approval_threshold')::bigint;
    IF expected_approvals < 1 THEN
        RAISE EXCEPTION 'D10 approval threshold is invalid' USING ERRCODE = '42501';
    END IF;
    SELECT count(*) INTO approval_count
    FROM public.g08_d10_approval_evidence approval
    WHERE approval.authorization_id = auth_record.authorization_id
      AND approval.policy_version = policy_version
      AND approval.approval_id::text IN (
          SELECT jsonb_array_elements_text(scope->'approval_ids')
      )
      AND approval.valid_from <= clock_timestamp()
      AND approval.valid_to > clock_timestamp()
      AND approval.claims->>'requester_uid' = scope->>'requester_uid'
      AND approval.claims->>'policy_id' = policy_claims->>'policy_id'
      AND approval.claims->>'tenant_id' = policy_claims->>'tenant_id'
      AND approval.claims->>'organization_id' = policy_claims->>'organization_id'
      AND approval.claims->>'action' = policy_claims->>'action'
      AND approval.claims->>'target_resource' = policy_claims->>'target_resource'
      AND approval.claims->>'approver_uid' NOT IN (
          scope->>'requester_uid', scope->>'operator_uid'
      );
    IF approval_count <> jsonb_array_length(scope->'approval_ids')
       OR approval_count < expected_approvals THEN
        RAISE EXCEPTION 'D10 independent approval threshold is not met'
            USING ERRCODE = '42501';
    END IF;

    SELECT fencing.current_generation INTO STRICT current_generation
    FROM public.g08_d10_fencing_state fencing
    WHERE fencing.tenant_id = (scope->>'tenant_id')::uuid
      AND fencing.organization_id = (scope->>'organization_id')::uuid
      AND fencing.action = scope->>'action'
      AND fencing.target_resource = scope->>'target_resource'
    FOR UPDATE;
    IF current_generation::text <> scope->>'fence_generation' THEN
        RAISE EXCEPTION 'fencing generation is stale' USING ERRCODE = '42501';
    END IF;

    SELECT * INTO STRICT assertion
    FROM jsonb_populate_record(
        NULL::public.g08_owner_operator_assertions, p_package->'assertion'
    );
    IF (assertion.authorization_id, assertion.owner_operation_id,
        assertion.purpose, assertion.db_session_user, assertion.verified_auth_uid)
       IS DISTINCT FROM
       (auth_record.authorization_id, auth_record.owner_operation_id,
        'EXECUTION'::text, session_user::text, (scope->>'operator_uid')::uuid)
        OR assertion.valid_until <= clock_timestamp()
        OR assertion.verified_at > clock_timestamp() THEN
        RAISE EXCEPTION 'independent operator session binding is invalid'
            USING ERRCODE = '42501';
    END IF;
    INSERT INTO public.g08_owner_operator_assertions SELECT assertion.*;
    decision_time := public.g08_owner_decision_time(
        auth_record.authorization_id, assertion.assertion_id
    );

    SELECT * INTO STRICT event
    FROM jsonb_populate_record(
        NULL::public.g08_identity_administrator_events, p_package->'event'
    );
    SELECT * INTO STRICT admin
    FROM jsonb_populate_record(
        NULL::public.g08_identity_administrators, p_package->'administrator'
    );
    SELECT * INTO STRICT version_row
    FROM jsonb_populate_record(
        NULL::public.g08_identity_administrator_versions, p_package->'version'
    );
    SELECT * INTO STRICT proof
    FROM jsonb_populate_record(
        NULL::public.g08_owner_execution_evidence, p_package->'proof'
    );
    SELECT * INTO STRICT owner_receipt
    FROM jsonb_populate_record(
        NULL::public.g08_owner_operation_receipts, p_package->'receipt'
    );
    SELECT * INTO STRICT binding
    FROM jsonb_populate_record(
        NULL::public.g08_d10_receipt_scope_bindings, p_package->'receipt_binding'
    );

    IF auth_record.operation NOT IN ('grant', 'revise', 'revoke')
       OR (event.event_id, event.owner_operation_id, event.administrator_id,
           event.action, event.execution_mode, event.before_revision,
           event.intent_sha256, event.request_digest, event.fingerprint_version,
           event.occurred_at)
          IS DISTINCT FROM
          (proof.event_id, auth_record.owner_operation_id, auth_record.administrator_id,
           auth_record.operation, 'owner_controlled'::text,
           auth_record.expected_revision, auth_record.intent_sha256,
           proof.request_digest, 'nxr-g08-owner-administration-v1'::text,
           proof.decision_time)
       OR (proof.authorization_id, proof.owner_operation_id, proof.assertion_id,
           proof.admitted_status_id, proof.admitted_revision, proof.decision_time,
           proof.request_digest, proof.event_id)
          IS DISTINCT FROM
          (auth_record.authorization_id, auth_record.owner_operation_id,
           assertion.assertion_id, event.event_id, 1::bigint,
           event.occurred_at, scope->>'request_digest', event.event_id)
       OR event.request_digest <> scope->>'request_digest'
       OR event.occurred_at > clock_timestamp()
       OR proof.result->>'event_id' <> event.event_id::text THEN
        RAISE EXCEPTION 'owner effect, event, D08 proof, and request do not match'
            USING ERRCODE = '23514';
    END IF;

    idempotency_key := p_package->>'idempotency_key';
    IF idempotency_key IS NULL OR idempotency_key !~ '^[A-Za-z0-9._:-]{1,128}$'
       OR EXISTS (
           SELECT 1 FROM public.g08_owner_operation_consumptions
           WHERE owner_operation_id = auth_record.owner_operation_id
       ) THEN
        RAISE EXCEPTION 'owner operation already consumed or invalid idempotency key'
            USING ERRCODE = '23505';
    END IF;

    IF auth_record.operation = 'grant' THEN
        subject_uid := (auth_record.mutation->>'subject_auth_uid')::uuid;
        IF (admin.administrator_id, admin.subject_auth_uid, admin.revision,
            admin.valid_from, admin.valid_to, admin.revoked_at,
            admin.origin_event_id, admin.current_event_id, version_row.event_id)
           IS DISTINCT FROM
           (auth_record.administrator_id, subject_uid, 1::bigint,
            (auth_record.mutation->>'valid_from')::timestamptz,
            nullif(auth_record.mutation->>'valid_to', '')::timestamptz,
            NULL::timestamptz, event.event_id, event.event_id, event.event_id)
           OR NOT EXISTS (SELECT 1 FROM auth.users WHERE id = subject_uid)
           OR admin.valid_from > clock_timestamp()
           OR (admin.valid_to IS NOT NULL AND admin.valid_to <= clock_timestamp()) THEN
            RAISE EXCEPTION 'synthetic or authorized G08 grant target is invalid'
                USING ERRCODE = '23514';
        END IF;
        INSERT INTO public.g08_identity_administrators SELECT admin.*;
        INSERT INTO public.g08_identity_administrator_versions SELECT version_row.*;
    ELSE
        RAISE EXCEPTION 'revise and revoke need an independently qualified effect adapter'
            USING ERRCODE = '55000';
    END IF;

    event.executor_db_role := current_user::text;
    INSERT INTO public.g08_identity_administrator_events SELECT event.*;

    canonical_request := jsonb_build_object(
        'version', 'nxr-g08-owner-administration-v1',
        'owner_operation_id', auth_record.owner_operation_id,
        'operation', auth_record.operation,
        'scope_key', auth_record.scope_key,
        'authorization_id', auth_record.authorization_id,
        'authorization_sha256', auth_record.authorization_sha256,
        'approval_manifest_sha256', auth_record.approval_manifest_sha256,
        'policy_version', auth_record.policy_version,
        'operator', jsonb_build_object(
            'person_ref', assertion.person_ref,
            'authentication_evidence_sha256', assertion.authentication_evidence_sha256,
            'verified_auth_uid', assertion.verified_auth_uid,
            'db_session_user', session_user::text
        ),
        'procedure_identity', owner_receipt.procedure_identity,
        'procedure_version', owner_receipt.procedure_version,
        'mutation', auth_record.mutation,
        'idempotency_key', idempotency_key
    );
    owner_receipt.event_id := event.event_id;
    owner_receipt.owner_operation_id := auth_record.owner_operation_id;
    owner_receipt.authorization_id := auth_record.authorization_id;
    owner_receipt.operation := auth_record.operation;
    owner_receipt.scope_key := auth_record.scope_key;
    owner_receipt.idempotency_key := idempotency_key;
    owner_receipt.operator_person_ref := assertion.person_ref;
    owner_receipt.operator_authentication_evidence_ref := assertion.authentication_evidence_ref;
    owner_receipt.operator_authentication_evidence_sha256 := assertion.authentication_evidence_sha256;
    owner_receipt.verified_operator_auth_uid := assertion.verified_auth_uid;
    owner_receipt.db_session_user := session_user::text;
    owner_receipt.db_effective_role := current_user::text;
    owner_receipt.authorization_sha256 := auth_record.authorization_sha256;
    owner_receipt.approval_manifest_sha256 := auth_record.approval_manifest_sha256;
    owner_receipt.policy_version := auth_record.policy_version;
    owner_receipt.approval_refs := (
        SELECT coalesce(jsonb_agg(approval_ref ORDER BY approval_ref), '[]'::jsonb)
        FROM public.g08_owner_operation_approval_links
        WHERE authorization_id = auth_record.authorization_id
    );
    owner_receipt.fingerprint_version := event.fingerprint_version;
    owner_receipt.intent_sha256 := auth_record.intent_sha256;
    owner_receipt.request_digest := proof.request_digest;
    owner_receipt.canonical_request := canonical_request;
    owner_receipt.result := proof.result;
    owner_receipt.occurred_at := event.occurred_at;
    INSERT INTO public.g08_owner_operation_receipts SELECT owner_receipt.*;

    binding.event_id := event.event_id;
    binding.authorization_id := auth_record.authorization_id;
    binding.owner_operation_id := auth_record.owner_operation_id;
    binding.tenant_id := (scope->>'tenant_id')::uuid;
    binding.organization_id := (scope->>'organization_id')::uuid;
    binding.policy_version := selected_policy_version;
    IF binding.binding_jti IS NULL THEN
        RAISE EXCEPTION 'D10 receipt binding identifier is required' USING ERRCODE = '23514';
    END IF;
    binding.recorded_at := clock_timestamp();
    INSERT INTO public.g08_d10_receipt_scope_bindings SELECT binding.*;

    PERFORM public.g08_stage_owner_consumption(proof);
    RETURN jsonb_build_object(
        'authorization_id', auth_record.authorization_id,
        'operation_id', auth_record.owner_operation_id,
        'event_id', event.event_id,
        'result', proof.result,
        'decision_time', event.occurred_at
    );
END
$$;
ALTER FUNCTION public.g08_gateway_execute_owner_operation(jsonb) OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_gateway_execute_owner_operation(jsonb)
    FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_gateway_execute_owner_operation(jsonb)
    TO nxr_g08_gateway_executor;

CREATE FUNCTION public.g08_gateway_read_owner_receipt(
    p_authorization_id uuid,
    p_operation_id uuid,
    p_tenant_id uuid,
    p_organization_id uuid,
    p_policy_version text,
    p_reader_uid uuid
) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
    policy_claims jsonb;
    current_version text;
    receipt jsonb;
BEGIN
    SELECT current_policy_version INTO current_version
    FROM public.g08_d10_authority_state
    WHERE authorization_id = p_authorization_id;
    IF current_version IS DISTINCT FROM p_policy_version THEN
        RAISE EXCEPTION 'receipt reader policy is stale' USING ERRCODE = '42501';
    END IF;
    SELECT claims INTO policy_claims
    FROM public.g08_d10_policy_versions
    WHERE authorization_id = p_authorization_id
      AND policy_version = p_policy_version
      AND valid_from <= clock_timestamp()
      AND valid_to > clock_timestamp();
    IF policy_claims IS NULL
       OR policy_claims->>'operation_id' <> p_operation_id::text
       OR policy_claims->>'tenant_id' <> p_tenant_id::text
       OR policy_claims->>'organization_id' <> p_organization_id::text
       OR policy_claims->>'organization_id' <> policy_claims->>'tenant_id'
       OR NOT (policy_claims->'receipt_reader_uids' @> to_jsonb(ARRAY[p_reader_uid::text])) THEN
        RAISE EXCEPTION 'receipt is outside the authorized tenant projection'
            USING ERRCODE = '42501';
    END IF;
    SELECT to_jsonb(r) || jsonb_build_object(
        'evidence_id', proof.evidence_id,
        'assertion_id', proof.assertion_id,
        'tenant_id', b.tenant_id,
        'organization_id', b.organization_id
    ) INTO receipt
    FROM public.g08_d10_receipt_scope_bindings b
    JOIN public.g08_owner_operation_receipts r
      ON (r.event_id, r.authorization_id, r.owner_operation_id)
       = (b.event_id, b.authorization_id, b.owner_operation_id)
    JOIN public.g08_owner_execution_evidence proof
      ON proof.event_id = r.event_id
    WHERE b.authorization_id = p_authorization_id
      AND r.authorization_id = p_authorization_id
      AND b.owner_operation_id = p_operation_id
      AND b.tenant_id = p_tenant_id
      AND b.organization_id = p_organization_id
      AND b.policy_version = p_policy_version;
    IF receipt IS NULL THEN
        RAISE EXCEPTION 'receipt is outside the authorized tenant projection'
            USING ERRCODE = '42501';
    END IF;
    RETURN receipt;
END
$$;
ALTER FUNCTION public.g08_gateway_read_owner_receipt(
    uuid, uuid, uuid, uuid, text, uuid
) OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_gateway_read_owner_receipt(
    uuid, uuid, uuid, uuid, text, uuid
) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_gateway_read_owner_receipt(
    uuid, uuid, uuid, uuid, text, uuid
) TO nxr_g08_gateway_executor;

REVOKE CREATE ON SCHEMA public FROM nxr_g08_owner_fn_owner;
COMMIT;
