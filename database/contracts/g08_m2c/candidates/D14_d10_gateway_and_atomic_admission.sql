-- UNAPPLIED ADDITIVE CANDIDATE. Synthetic qualification only; never activate r5.
-- Private application code verifies signatures before calling these functions.
-- Functions expose only scoped D10 data to the NOLOGIN gateway executor.
BEGIN;

GRANT CREATE ON SCHEMA public TO nxr_g08_owner_fn_owner;
GRANT USAGE ON SCHEMA auth TO nxr_g08_owner_fn_owner;
GRANT SELECT (id) ON TABLE auth.users TO nxr_g08_owner_fn_owner;

DO $empty_policy_history$
BEGIN
    IF EXISTS (SELECT 1 FROM public.g08_d10_policy_versions) THEN
        RAISE EXCEPTION 'D14 requires an empty qualification D10 policy history';
    END IF;
END
$empty_policy_history$;

ALTER TABLE public.g08_d10_policy_versions
    ADD COLUMN authority_class text NOT NULL
        CHECK (authority_class = 'SYNTHETIC_QUALIFICATION');

CREATE FUNCTION public.g08_d10_gateway_read_bundle(
    p_authorization_id uuid,
    p_operation_id uuid,
    p_tenant_id uuid,
    p_organization_id uuid
) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
    auth_record public.g08_owner_operation_authorizations;
    state public.g08_d10_authority_state;
    policy public.g08_d10_policy_versions;
    approvals jsonb;
BEGIN
    IF current_database() <> 'nexora_m2c_g08gateway_20261111'
       OR p_tenant_id IS NULL OR p_organization_id IS NULL
       OR p_tenant_id <> p_organization_id THEN
        RAISE EXCEPTION 'synthetic D10 authority is restricted to the isolated qualification target'
            USING ERRCODE = '42501';
    END IF;
    SELECT * INTO auth_record
    FROM public.g08_owner_operation_authorizations
    WHERE authorization_id = p_authorization_id
      AND owner_operation_id = p_operation_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'D10 owner authorization is unavailable' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO state
    FROM public.g08_d10_authority_state
    WHERE authorization_id = p_authorization_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'current D10 authority state is unavailable' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO policy
    FROM public.g08_d10_policy_versions
    WHERE authorization_id = p_authorization_id
      AND policy_version = state.current_policy_version;
    IF NOT FOUND
       OR policy.authority_class <> 'SYNTHETIC_QUALIFICATION'
       OR policy.valid_from > clock_timestamp()
       OR policy.valid_to <= clock_timestamp()
       OR policy.claims->>'authorization_id' <> p_authorization_id::text
       OR policy.claims->>'operation_id' <> p_operation_id::text
       OR policy.claims->>'tenant_id' <> p_tenant_id::text
       OR policy.claims->>'organization_id' <> p_organization_id::text
       OR policy.claims->>'action' <> auth_record.operation THEN
        RAISE EXCEPTION 'current D10 policy is invalid or outside the requested tenant scope'
            USING ERRCODE = '42501';
    END IF;
    SELECT coalesce(
        jsonb_agg(
            jsonb_build_object(
                'issuer_key_id', a.issuer_key_id,
                'claims', a.claims,
                'signature_hex', encode(a.signature, 'hex')
            ) ORDER BY a.approval_id::text
        ),
        '[]'::jsonb
    ) INTO approvals
    FROM public.g08_d10_approval_evidence a
    WHERE a.authorization_id = p_authorization_id
      AND a.policy_version = state.current_policy_version
      AND a.valid_from <= clock_timestamp()
      AND a.valid_to > clock_timestamp();
    RETURN jsonb_build_object(
        'current_policy_version', state.current_policy_version,
        'authority_class', policy.authority_class,
        'policy', jsonb_build_object(
            'issuer_key_id', policy.issuer_key_id,
            'claims', policy.claims,
            'signature_hex', encode(policy.signature, 'hex')
        ),
        'approvals', approvals
    );
END
$$;
ALTER FUNCTION public.g08_d10_gateway_read_bundle(uuid, uuid, uuid, uuid)
    OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_d10_gateway_read_bundle(uuid, uuid, uuid, uuid)
    FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_d10_gateway_read_bundle(uuid, uuid, uuid, uuid)
    TO nxr_g08_gateway_executor;

CREATE FUNCTION public.g08_d10_gateway_is_revoked(
    p_authorization_id uuid,
    p_subject_type text,
    p_subject_id text
) RETURNS boolean
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    IF p_subject_type NOT IN (
        'AUTHORIZATION', 'APPROVAL', 'OPERATOR_EVIDENCE', 'FENCING_TOKEN'
    ) OR p_subject_id IS NULL OR length(btrim(p_subject_id)) = 0
       OR NOT EXISTS (
           SELECT 1 FROM public.g08_owner_operation_authorizations
           WHERE authorization_id = p_authorization_id
       ) THEN
        RAISE EXCEPTION 'invalid scoped D10 revocation query' USING ERRCODE = '42501';
    END IF;
    RETURN EXISTS (
        SELECT 1
        FROM public.g08_d10_revocations r
        WHERE r.authorization_id = p_authorization_id
          AND r.subject_type = p_subject_type
          AND r.subject_id = p_subject_id
    );
END
$$;
ALTER FUNCTION public.g08_d10_gateway_is_revoked(uuid, text, text)
    OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_d10_gateway_is_revoked(uuid, text, text)
    FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_d10_gateway_is_revoked(uuid, text, text)
    TO nxr_g08_gateway_executor;

CREATE FUNCTION public.g08_d10_gateway_append_policy(
    p_authorization_id uuid,
    p_operation_id uuid,
    p_tenant_id uuid,
    p_organization_id uuid,
    p_policy_version text,
    p_policy_id text,
    p_issuer_key_id text,
    p_policy_jti text,
    p_claims jsonb,
    p_signature bytea,
    p_valid_from timestamptz,
    p_valid_to timestamptz
) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
    auth_record public.g08_owner_operation_authorizations;
    current_version text;
BEGIN
    IF current_database() <> 'nexora_m2c_g08gateway_20261111'
       OR p_tenant_id IS NULL OR p_organization_id IS NULL
       OR p_tenant_id <> p_organization_id
       OR p_claims->>'authority_class' <> 'SYNTHETIC_QUALIFICATION'
       OR p_claims->>'sub' <> 'synthetic-d10-authority'
       OR p_claims->>'aud' <> 'nexora-g08-d10-policy'
       OR p_claims->>'jti' <> p_policy_jti
       OR p_claims->>'policy_id' <> p_policy_id
       OR p_claims->>'version' <> p_policy_version
       OR p_claims->>'requester_uid' IS NULL
       OR p_claims->>'not_before' IS NULL
       OR p_claims->>'expires_at' IS NULL
       OR p_valid_to <= p_valid_from
       OR p_signature IS NULL OR octet_length(p_signature) <> 64 THEN
        RAISE EXCEPTION 'invalid synthetic D10 policy envelope' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO STRICT auth_record
    FROM public.g08_owner_operation_authorizations
    WHERE authorization_id = p_authorization_id
      AND owner_operation_id = p_operation_id
    FOR UPDATE;
    IF (p_claims->>'authorization_id', p_claims->>'operation_id',
        p_claims->>'tenant_id', p_claims->>'organization_id',
        p_claims->>'action', p_claims->>'requester_person_ref')
       IS DISTINCT FROM
       (p_authorization_id::text, p_operation_id::text,
        p_tenant_id::text, p_organization_id::text,
        auth_record.operation, auth_record.requester_person_ref::text) THEN
        RAISE EXCEPTION 'synthetic D10 policy does not bind canonical owner authorization'
            USING ERRCODE = '42501';
    END IF;
    SELECT current_policy_version INTO current_version
    FROM public.g08_d10_authority_state
    WHERE authorization_id = p_authorization_id
    FOR UPDATE;
    INSERT INTO public.g08_d10_policy_versions (
        authorization_id, policy_version, policy_id, issuer_key_id,
        policy_jti, claims, signature, valid_from, valid_to, authority_class
    ) VALUES (
        p_authorization_id, p_policy_version, p_policy_id, p_issuer_key_id,
        p_policy_jti, p_claims, p_signature, p_valid_from, p_valid_to,
        'SYNTHETIC_QUALIFICATION'
    );
    IF current_version IS NULL THEN
        INSERT INTO public.g08_d10_authority_state (
            authorization_id, current_policy_version, revision
        ) VALUES (p_authorization_id, p_policy_version, 1);
    ELSE
        UPDATE public.g08_d10_authority_state
        SET current_policy_version = p_policy_version,
            revision = revision + 1,
            updated_at = clock_timestamp()
        WHERE authorization_id = p_authorization_id;
    END IF;
END
$$;
ALTER FUNCTION public.g08_d10_gateway_append_policy(
    uuid, uuid, uuid, uuid, text, text, text, text, jsonb, bytea, timestamptz, timestamptz
) OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_d10_gateway_append_policy(
    uuid, uuid, uuid, uuid, text, text, text, text, jsonb, bytea, timestamptz, timestamptz
) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_d10_gateway_append_policy(
    uuid, uuid, uuid, uuid, text, text, text, text, jsonb, bytea, timestamptz, timestamptz
) TO nxr_g08_gateway_executor;

CREATE FUNCTION public.g08_d10_gateway_append_approval(
    p_authorization_id uuid,
    p_operation_id uuid,
    p_policy_version text,
    p_approval_id uuid,
    p_issuer_key_id text,
    p_approval_jti text,
    p_claims jsonb,
    p_signature bytea,
    p_valid_from timestamptz,
    p_valid_to timestamptz
) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
    policy_claims jsonb;
BEGIN
    IF p_signature IS NULL OR octet_length(p_signature) <> 64
       OR p_valid_to <= p_valid_from
       OR p_claims->>'approval_id' <> p_approval_id::text
       OR p_claims->>'jti' <> p_approval_jti
       OR p_claims->>'aud' <> 'nexora-g08-owner-approval' THEN
        RAISE EXCEPTION 'invalid signed D10 approval envelope' USING ERRCODE = '42501';
    END IF;
    PERFORM 1
    FROM public.g08_d10_authority_state
    WHERE authorization_id = p_authorization_id
      AND current_policy_version = p_policy_version
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'approval is not for the current D10 policy' USING ERRCODE = '42501';
    END IF;
    SELECT claims INTO STRICT policy_claims
    FROM public.g08_d10_policy_versions
    WHERE authorization_id = p_authorization_id
      AND policy_version = p_policy_version
      AND authority_class = 'SYNTHETIC_QUALIFICATION';
    IF (p_claims->>'policy_id', p_claims->>'policy_version',
        p_claims->>'authorization_id', p_claims->>'operation_id',
        p_claims->>'tenant_id', p_claims->>'organization_id',
        p_claims->>'action', p_claims->>'target_resource',
        p_claims->>'requester_uid')
       IS DISTINCT FROM
       (policy_claims->>'policy_id', p_policy_version,
        p_authorization_id::text, p_operation_id::text,
        policy_claims->>'tenant_id', policy_claims->>'organization_id',
        policy_claims->>'action', policy_claims->>'target_resource',
        policy_claims->>'requester_uid')
       OR p_claims->>'approver_uid' = policy_claims->>'requester_uid' THEN
        RAISE EXCEPTION 'approval does not bind independent approver to current policy'
            USING ERRCODE = '42501';
    END IF;
    INSERT INTO public.g08_d10_approval_evidence (
        approval_id, authorization_id, policy_version, policy_id,
        approver_auth_uid, issuer_key_id, approval_jti, claims, signature,
        valid_from, valid_to
    ) VALUES (
        p_approval_id, p_authorization_id, p_policy_version,
        policy_claims->>'policy_id', (p_claims->>'approver_uid')::uuid,
        p_issuer_key_id, p_approval_jti, p_claims, p_signature,
        p_valid_from, p_valid_to
    );
END
$$;
ALTER FUNCTION public.g08_d10_gateway_append_approval(
    uuid, uuid, text, uuid, text, text, jsonb, bytea, timestamptz, timestamptz
) OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_d10_gateway_append_approval(
    uuid, uuid, text, uuid, text, text, jsonb, bytea, timestamptz, timestamptz
) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_d10_gateway_append_approval(
    uuid, uuid, text, uuid, text, text, jsonb, bytea, timestamptz, timestamptz
) TO nxr_g08_gateway_executor;

CREATE FUNCTION public.g08_d10_gateway_append_revocation(
    p_authorization_id uuid,
    p_revocation_id uuid,
    p_subject_type text,
    p_subject_id text,
    p_issuer_key_id text,
    p_revocation_jti text,
    p_claims jsonb,
    p_signature bytea,
    p_revoked_at timestamptz
) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    IF p_subject_type NOT IN (
        'AUTHORIZATION', 'APPROVAL', 'OPERATOR_EVIDENCE', 'FENCING_TOKEN'
    ) OR p_claims->>'authorization_id' <> p_authorization_id::text
       OR p_claims->>'subject_type' <> p_subject_type
       OR p_claims->>'subject_id' <> p_subject_id
       OR p_claims->>'jti' <> p_revocation_jti
       OR p_signature IS NULL OR octet_length(p_signature) <> 64 THEN
        RAISE EXCEPTION 'invalid signed D10 revocation envelope' USING ERRCODE = '42501';
    END IF;
    PERFORM 1
    FROM public.g08_d10_authority_state
    WHERE authorization_id = p_authorization_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'D10 revocation authorization is unavailable' USING ERRCODE = '42501';
    END IF;
    IF p_subject_type = 'APPROVAL' AND NOT EXISTS (
        SELECT 1 FROM public.g08_d10_approval_evidence
        WHERE authorization_id = p_authorization_id
          AND approval_id::text = p_subject_id
    ) THEN
        RAISE EXCEPTION 'D10 approval revocation target is outside authorization'
            USING ERRCODE = '42501';
    END IF;
    INSERT INTO public.g08_d10_revocations (
        revocation_id, authorization_id, subject_type, subject_id,
        issuer_key_id, revocation_jti, claims, signature, revoked_at
    ) VALUES (
        p_revocation_id, p_authorization_id, p_subject_type, p_subject_id,
        p_issuer_key_id, p_revocation_jti, p_claims, p_signature, p_revoked_at
    );
END
$$;
ALTER FUNCTION public.g08_d10_gateway_append_revocation(
    uuid, uuid, text, text, text, text, jsonb, bytea, timestamptz
) OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_d10_gateway_append_revocation(
    uuid, uuid, text, text, text, text, jsonb, bytea, timestamptz
) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_d10_gateway_append_revocation(
    uuid, uuid, text, text, text, text, jsonb, bytea, timestamptz
) TO nxr_g08_gateway_executor;

CREATE FUNCTION public.g08_d10_gateway_advance_fence(
    p_authorization_id uuid,
    p_operation_id uuid,
    p_tenant_id uuid,
    p_organization_id uuid,
    p_action text,
    p_target_resource text,
    p_fencing_jti text,
    p_generation bigint
) RETURNS bigint
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
    policy_claims jsonb;
    existing_generation bigint;
BEGIN
    IF current_database() <> 'nexora_m2c_g08gateway_20261111'
       OR p_tenant_id <> p_organization_id OR p_generation < 1 THEN
        RAISE EXCEPTION 'invalid synthetic fencing scope' USING ERRCODE = '42501';
    END IF;
    PERFORM 1 FROM public.g08_d10_authority_state
    WHERE authorization_id = p_authorization_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'fencing D10 authority is unavailable' USING ERRCODE = '42501';
    END IF;
    SELECT claims INTO STRICT policy_claims
    FROM public.g08_d10_policy_versions p
    JOIN public.g08_d10_authority_state s USING (authorization_id)
    WHERE p.authorization_id = p_authorization_id
      AND p.policy_version = s.current_policy_version
      AND p.authority_class = 'SYNTHETIC_QUALIFICATION';
    IF (policy_claims->>'operation_id', policy_claims->>'tenant_id',
        policy_claims->>'organization_id', policy_claims->>'action',
        policy_claims->>'target_resource')
       IS DISTINCT FROM
       (p_operation_id::text, p_tenant_id::text, p_organization_id::text,
        p_action, p_target_resource)
       OR public.g08_d10_gateway_is_revoked(
           p_authorization_id, 'FENCING_TOKEN', p_fencing_jti
       ) THEN
        RAISE EXCEPTION 'fencing token is revoked or outside D10 scope'
            USING ERRCODE = '42501';
    END IF;
    SELECT fencing.current_generation INTO existing_generation
    FROM public.g08_d10_fencing_state
        AS fencing
    WHERE tenant_id = p_tenant_id
      AND organization_id = p_organization_id
      AND action = p_action
      AND target_resource = p_target_resource
    FOR UPDATE;
    IF NOT FOUND THEN
        IF p_generation <> 1 THEN
            RAISE EXCEPTION 'initial fencing generation must be one' USING ERRCODE = '42501';
        END IF;
        INSERT INTO public.g08_d10_fencing_state (
            tenant_id, organization_id, action, target_resource, current_generation
        ) VALUES (
            p_tenant_id, p_organization_id, p_action, p_target_resource, p_generation
        );
    ELSE
        IF p_generation <= existing_generation THEN
            RAISE EXCEPTION 'fencing generation must advance monotonically'
                USING ERRCODE = '42501';
        END IF;
        UPDATE public.g08_d10_fencing_state
        SET current_generation = p_generation, updated_at = clock_timestamp()
        WHERE tenant_id = p_tenant_id
          AND organization_id = p_organization_id
          AND action = p_action
          AND target_resource = p_target_resource;
    END IF;
    RETURN p_generation;
END
$$;
ALTER FUNCTION public.g08_d10_gateway_advance_fence(
    uuid, uuid, uuid, uuid, text, text, text, bigint
) OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_d10_gateway_advance_fence(
    uuid, uuid, uuid, uuid, text, text, text, bigint
) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_d10_gateway_advance_fence(
    uuid, uuid, uuid, uuid, text, text, text, bigint
) TO nxr_g08_gateway_executor;

CREATE FUNCTION public.g08_d10_gateway_current_fence(
    p_authorization_id uuid,
    p_operation_id uuid,
    p_tenant_id uuid,
    p_organization_id uuid,
    p_action text,
    p_target_resource text
) RETURNS bigint
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
    policy_claims jsonb;
    generation bigint;
BEGIN
    SELECT p.claims INTO policy_claims
    FROM public.g08_d10_policy_versions p
    JOIN public.g08_d10_authority_state s USING (authorization_id)
    WHERE p.authorization_id = p_authorization_id
      AND p.policy_version = s.current_policy_version
      AND p.authority_class = 'SYNTHETIC_QUALIFICATION';
    IF policy_claims IS NULL
       OR (policy_claims->>'operation_id', policy_claims->>'tenant_id',
           policy_claims->>'organization_id', policy_claims->>'action',
           policy_claims->>'target_resource')
          IS DISTINCT FROM
          (p_operation_id::text, p_tenant_id::text, p_organization_id::text,
           p_action, p_target_resource) THEN
        RAISE EXCEPTION 'current fencing scope is outside D10 authority'
            USING ERRCODE = '42501';
    END IF;
    SELECT current_generation INTO generation
    FROM public.g08_d10_fencing_state
    WHERE tenant_id = p_tenant_id
      AND organization_id = p_organization_id
      AND action = p_action
      AND target_resource = p_target_resource;
    IF generation IS NULL THEN
        RAISE EXCEPTION 'current fencing generation is unavailable' USING ERRCODE = '42501';
    END IF;
    RETURN generation;
END
$$;
ALTER FUNCTION public.g08_d10_gateway_current_fence(uuid, uuid, uuid, uuid, text, text)
    OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_d10_gateway_current_fence(uuid, uuid, uuid, uuid, text, text)
    FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_d10_gateway_current_fence(uuid, uuid, uuid, uuid, text, text)
    TO nxr_g08_gateway_executor;

CREATE FUNCTION public.g08_d10_gateway_assert_current(
    p_authorization_id uuid,
    p_operation_id uuid,
    p_tenant_id uuid,
    p_organization_id uuid,
    p_action text,
    p_target_resource text,
    p_policy_version text,
    p_requester_uid uuid,
    p_operator_uid uuid,
    p_operator_jti text,
    p_approval_ids text[],
    p_fence_jti text,
    p_fence_generation bigint,
    p_decision_time timestamptz
) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
    policy_claims jsonb;
    current_version text;
    expected_count integer;
    approval_count integer;
    current_generation bigint;
BEGIN
    PERFORM public.g08_lock_identity_history();
    SELECT current_policy_version INTO STRICT current_version
    FROM public.g08_d10_authority_state
    WHERE authorization_id = p_authorization_id
    FOR UPDATE;
    IF current_version IS DISTINCT FROM p_policy_version THEN
        RAISE EXCEPTION 'D10 policy changed before owner execution' USING ERRCODE = '42501';
    END IF;
    SELECT claims INTO STRICT policy_claims
    FROM public.g08_d10_policy_versions
    WHERE authorization_id = p_authorization_id
      AND policy_version = current_version
      AND authority_class = 'SYNTHETIC_QUALIFICATION'
      AND valid_from <= p_decision_time AND valid_to > p_decision_time;
    IF (policy_claims->>'authorization_id', policy_claims->>'operation_id',
        policy_claims->>'tenant_id', policy_claims->>'organization_id',
        policy_claims->>'action', policy_claims->>'target_resource',
        policy_claims->>'requester_uid')
       IS DISTINCT FROM
       (p_authorization_id::text, p_operation_id::text, p_tenant_id::text,
        p_organization_id::text, p_action, p_target_resource, p_requester_uid::text)
       OR p_tenant_id <> p_organization_id
       OR public.g08_d10_gateway_is_revoked(
           p_authorization_id, 'AUTHORIZATION', p_authorization_id::text
       )
       OR public.g08_d10_gateway_is_revoked(
           p_authorization_id, 'OPERATOR_EVIDENCE', p_operator_jti
       )
       OR (
           p_fence_jti IS NOT NULL
           AND public.g08_d10_gateway_is_revoked(
               p_authorization_id, 'FENCING_TOKEN', p_fence_jti
           )
       )
       OR current_database() <> 'nexora_m2c_g08gateway_20261111' THEN
        RAISE EXCEPTION 'D10 authority, tenant, or revocation check failed'
            USING ERRCODE = '42501';
    END IF;
    expected_count := (policy_claims->>'approval_threshold')::integer;
    IF expected_count < 1 OR coalesce(cardinality(p_approval_ids), 0) < expected_count THEN
        RAISE EXCEPTION 'D10 approval threshold is not met' USING ERRCODE = '42501';
    END IF;
    SELECT count(*) INTO approval_count
    FROM public.g08_d10_approval_evidence a
    WHERE a.authorization_id = p_authorization_id
      AND a.policy_version = current_version
      AND a.approval_id::text = ANY(p_approval_ids)
      AND a.valid_from <= p_decision_time AND a.valid_to > p_decision_time
      AND a.claims->>'requester_uid' = p_requester_uid::text
      AND a.claims->>'approver_uid' NOT IN (p_requester_uid::text, p_operator_uid::text)
      AND NOT public.g08_d10_gateway_is_revoked(
          p_authorization_id, 'APPROVAL', a.approval_id::text
      );
    IF approval_count <> cardinality(p_approval_ids) OR approval_count < expected_count THEN
        RAISE EXCEPTION 'D10 approval set is invalid, revoked, or insufficient'
            USING ERRCODE = '42501';
    END IF;
    IF p_fence_generation IS NOT NULL THEN
        SELECT fencing.current_generation INTO STRICT current_generation
        FROM public.g08_d10_fencing_state
            AS fencing
        WHERE fencing.tenant_id = p_tenant_id
          AND fencing.organization_id = p_organization_id
          AND fencing.action = p_action
          AND fencing.target_resource = p_target_resource
        FOR UPDATE;
        IF current_generation <> p_fence_generation THEN
            RAISE EXCEPTION 'fencing generation is stale' USING ERRCODE = '42501';
        END IF;
    END IF;
END
$$;
ALTER FUNCTION public.g08_d10_gateway_assert_current(
    uuid, uuid, uuid, uuid, text, text, text, uuid, uuid, text,
    text[], text, bigint, timestamptz
) OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_d10_gateway_assert_current(
    uuid, uuid, uuid, uuid, text, text, text, uuid, uuid, text,
    text[], text, bigint, timestamptz
) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_d10_gateway_assert_current(
    uuid, uuid, uuid, uuid, text, text, text, uuid, uuid, text,
    text[], text, bigint, timestamptz
) TO nxr_g08_gateway_executor;

DO $scope_receipt_reader$
DECLARE
    definition text;
    signature regprocedure := 'public.g08_gateway_read_owner_receipt(uuid,uuid,uuid,uuid,text,uuid)'::regprocedure;
BEGIN
    definition := pg_get_functiondef(signature);
    IF position('SELECT claims INTO policy_claims' IN definition) = 0
       OR position('IF policy_claims IS NULL' IN definition) = 0 THEN
        RAISE EXCEPTION 'installed D13 receipt reader differs from the reviewed repair baseline';
    END IF;
    definition := replace(
        definition,
        '    current_version text;',
        '    current_version text;' || E'\n' || '    authority_class text;'
    );
    definition := replace(
        definition,
        ' STABLE SECURITY DEFINER',
        ' VOLATILE SECURITY DEFINER'
    );
    definition := replace(
        definition,
        '    WHERE authorization_id = p_authorization_id;',
        '    WHERE authorization_id = p_authorization_id FOR SHARE;'
    );
    definition := replace(
        definition,
        'SELECT claims INTO policy_claims',
        'SELECT public.g08_d10_policy_versions.claims, ' ||
        'public.g08_d10_policy_versions.authority_class ' ||
        'INTO policy_claims, authority_class'
    );
    definition := replace(
        definition,
        'IF policy_claims IS NULL',
        'IF policy_claims IS NULL' || E'\n' ||
        '       OR authority_class <> ''SYNTHETIC_QUALIFICATION''' || E'\n' ||
        '       OR current_database() <> ''nexora_m2c_g08gateway_20261111'''
    );
    IF position('FOR SHARE' IN definition) = 0
       OR position('authority_class <> ''SYNTHETIC_QUALIFICATION''' IN definition) = 0
       OR position(' VOLATILE SECURITY DEFINER' IN definition) = 0 THEN
        RAISE EXCEPTION 'D13 receipt reader hardening did not apply exactly';
    END IF;
    EXECUTE definition;
END
$scope_receipt_reader$;

CREATE FUNCTION public.g08_gateway_stage_owner_authorization(
    p_authorization jsonb
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
    auth_record public.g08_owner_operation_authorizations;
BEGIN
    IF p_authorization IS NULL OR jsonb_typeof(p_authorization) <> 'object' THEN
        RAISE EXCEPTION 'canonical owner authorization is required' USING ERRCODE = '22023';
    END IF;
    SELECT * INTO STRICT auth_record
    FROM jsonb_populate_record(
        NULL::public.g08_owner_operation_authorizations, p_authorization
    );
    IF auth_record.operation <> 'grant'
       OR auth_record.scope_key <> 'global'
       OR auth_record.expected_revision IS NOT NULL
       OR auth_record.mutation->>'subject_auth_uid' IS NULL
       OR auth_record.mutation->>'valid_from' IS NULL
       OR auth_record.valid_from >= auth_record.valid_to
       OR auth_record.valid_to <= clock_timestamp()
       OR NOT EXISTS (
           SELECT 1 FROM auth.users
           WHERE id = (auth_record.mutation->>'subject_auth_uid')::uuid
       ) THEN
        RAISE EXCEPTION 'synthetic G08 grant authorization is invalid'
            USING ERRCODE = '23514';
    END IF;
    INSERT INTO public.g08_owner_operation_authorizations SELECT auth_record.*;
    RETURN auth_record.authorization_id;
END
$$;
ALTER FUNCTION public.g08_gateway_stage_owner_authorization(jsonb)
    OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_gateway_stage_owner_authorization(jsonb)
    FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_gateway_stage_owner_authorization(jsonb)
    TO nxr_g08_gateway_executor;

CREATE OR REPLACE FUNCTION public.g08_gateway_stage_admission(
    p_package jsonb
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
    auth_record public.g08_owner_operation_authorizations;
    persisted public.g08_owner_operation_authorizations;
    assertion public.g08_owner_operator_assertions;
    approvals public.g08_owner_operation_approval_links[];
    status_id uuid;
    existing boolean;
BEGIN
    IF p_package IS NULL OR jsonb_typeof(p_package) <> 'object' THEN
        RAISE EXCEPTION 'invalid owner admission package' USING ERRCODE = '22023';
    END IF;
    SELECT * INTO STRICT auth_record
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
    status_id := (p_package->>'status_id')::uuid;
    SELECT * INTO persisted
    FROM public.g08_owner_operation_authorizations
    WHERE authorization_id = auth_record.authorization_id
      AND owner_operation_id = auth_record.owner_operation_id;
    existing := FOUND;
    IF existing THEN
        IF persisted IS DISTINCT FROM auth_record
           OR EXISTS (
               SELECT 1 FROM public.g08_owner_authorization_status_history
               WHERE authorization_id = auth_record.authorization_id
           ) THEN
            RAISE EXCEPTION 'bootstrap authorization conflicts with canonical history'
                USING ERRCODE = '23505';
        END IF;
        INSERT INTO public.g08_owner_operator_assertions SELECT assertion.*;
        INSERT INTO public.g08_owner_operation_approval_links
            SELECT item.* FROM unnest(approvals) item;
        RETURN public.g08_stage_owner_status(
            auth_record.authorization_id, status_id, 'ADMITTED', NULL,
            assertion.assertion_id, p_package->>'evidence_ref',
            p_package->>'rationale'
        );
    END IF;
    RETURN public.g08_stage_owner_admission(
        auth_record, assertion, approvals, status_id,
        p_package->>'evidence_ref', p_package->>'rationale'
    );
END
$$;
ALTER FUNCTION public.g08_gateway_stage_admission(jsonb)
    OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_gateway_stage_admission(jsonb)
    FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_gateway_stage_admission(jsonb)
    TO nxr_g08_gateway_executor;

DO $repair_d11$
DECLARE
    definition text;
    signature regprocedure := 'public.g08_gateway_execute_owner_operation(jsonb)'::regprocedure;
BEGIN
    definition := pg_get_functiondef(signature);
    IF position('approval.policy_version = policy_version' IN definition) = 0
       OR position('assertion.assertion_id, event.event_id, 1::bigint,' IN definition) = 0
       OR position('SELECT p.claims INTO STRICT policy_claims' IN definition) = 0 THEN
        RAISE EXCEPTION 'installed D11 gateway differs from the reviewed repair baseline';
    END IF;
    definition := replace(
        definition,
        '    policy_claims jsonb;',
        '    policy_claims jsonb;' || E'\n' ||
        '    authority_class text;' || E'\n' ||
        '    admitted_status_id uuid;'
    );
    definition := replace(
        definition,
        'SELECT p.claims INTO STRICT policy_claims',
        'SELECT p.claims, p.authority_class INTO STRICT policy_claims, authority_class'
    );
    definition := replace(
        definition,
        '       OR scope->>''tenant_id'' <> scope->>''organization_id''',
        '       OR authority_class <> ''SYNTHETIC_QUALIFICATION''' || E'\n' ||
        '       OR current_database() <> ''nexora_m2c_g08gateway_20261111''' || E'\n' ||
        '       OR scope->>''tenant_id'' <> scope->>''organization_id'''
    );
    definition := replace(
        definition,
        'AND approval.policy_version = policy_version',
        'AND approval.policy_version = selected_policy_version'
    );
    definition := replace(
        definition,
        '    SELECT * INTO STRICT assertion',
        '    SELECT status_id INTO STRICT admitted_status_id' || E'\n' ||
        '    FROM public.g08_owner_authorization_status_history' || E'\n' ||
        '    WHERE authorization_id = auth_record.authorization_id' || E'\n' ||
        '      AND revision = 1 AND status = ''ADMITTED'';' || E'\n' ||
        '    SELECT * INTO STRICT assertion'
    );
    definition := replace(
        definition,
        'assertion.assertion_id, event.event_id, 1::bigint,',
        'assertion.assertion_id, admitted_status_id, 1::bigint,'
    );
    definition := replace(
        definition,
        '    INSERT INTO public.g08_d10_receipt_scope_bindings SELECT binding.*;',
        '    binding.recorded_at := clock_timestamp();' || E'\n' ||
        '    INSERT INTO public.g08_d10_receipt_scope_bindings SELECT binding.*;'
    );
    IF position(
        'binding.recorded_at := clock_timestamp();' IN definition
    ) = 0 THEN
        RAISE EXCEPTION 'D11 receipt binding timestamp repair did not apply exactly';
    END IF;
    EXECUTE definition;
END
$repair_d11$;

REVOKE CREATE ON SCHEMA public FROM nxr_g08_owner_fn_owner;

COMMIT;
