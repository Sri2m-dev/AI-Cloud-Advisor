-- UNAPPLIED ADDITIVE CANDIDATE. Synthetic qualification only.
-- Qualify the fencing column reference inside transactional D10 revalidation.
BEGIN;

CREATE OR REPLACE FUNCTION public.g08_d10_gateway_assert_current(
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
        FROM public.g08_d10_fencing_state AS fencing
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

COMMIT;
