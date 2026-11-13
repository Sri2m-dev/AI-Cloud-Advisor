-- UNAPPLIED ADDITIVE CANDIDATE. Qualification only; does not activate r5.
-- Replaces the unscoped receipt projection with an explicit tenant reader.
BEGIN;

GRANT EXECUTE ON FUNCTION public.g08_assert_identity_history()
    TO nxr_g08_owner_fn_owner;

CREATE OR REPLACE FUNCTION public.g08_gateway_lock_owner_history()
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    PERFORM public.g08_lock_identity_history();
    PERFORM public.g08_assert_identity_history();
    PERFORM public.g08_assert_owner_history();
END
$$;
ALTER FUNCTION public.g08_gateway_lock_owner_history()
    OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_gateway_lock_owner_history()
    FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_gateway_lock_owner_history()
    TO nxr_g08_gateway_executor;

CREATE OR REPLACE FUNCTION public.g08_gateway_load_owner_operation(
    p_operation_id uuid
) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
    auth_record public.g08_owner_operation_authorizations;
    history jsonb;
    policy_claims jsonb;
    consumed boolean;
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
    SELECT p.claims INTO policy_claims
    FROM public.g08_d10_authority_state state
    JOIN public.g08_d10_policy_versions p
      ON (p.authorization_id, p.policy_version)
       = (state.authorization_id, state.current_policy_version)
    WHERE state.authorization_id = auth_record.authorization_id;
    SELECT EXISTS (
        SELECT 1
        FROM public.g08_owner_operation_consumptions c
        WHERE c.owner_operation_id = p_operation_id
    ) INTO consumed;
    RETURN jsonb_build_object(
        'authorization', to_jsonb(auth_record),
        'history', history,
        'policy', policy_claims,
        'consumed', consumed
    );
END
$$;
ALTER FUNCTION public.g08_gateway_load_owner_operation(uuid)
    OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_gateway_load_owner_operation(uuid)
    FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_gateway_load_owner_operation(uuid)
    TO nxr_g08_gateway_executor;

CREATE OR REPLACE FUNCTION public.g08_gateway_read_owner_receipt(
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

COMMIT;
