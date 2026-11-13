-- UNAPPLIED ADDITIVE CANDIDATE. Requires D11 on an isolated qualification target.
BEGIN;

GRANT CREATE ON SCHEMA public TO nxr_g08_owner_fn_owner;

CREATE OR REPLACE FUNCTION public.g08_gateway_load_owner_operation(
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

CREATE FUNCTION public.g08_gateway_stage_owner_status(
    p_package jsonb
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE
    assertion public.g08_owner_operator_assertions;
BEGIN
    SELECT * INTO assertion
    FROM jsonb_populate_record(
        NULL::public.g08_owner_operator_assertions, p_package->'assertion'
    );
    INSERT INTO public.g08_owner_operator_assertions SELECT assertion.*;
    RETURN public.g08_stage_owner_status(
        (p_package->>'authorization_id')::uuid,
        (p_package->>'status_id')::uuid,
        p_package->>'status',
        nullif(p_package->>'expected_predecessor', '')::uuid,
        assertion.assertion_id,
        p_package->>'evidence_ref',
        p_package->>'rationale'
    );
END
$$;
ALTER FUNCTION public.g08_gateway_stage_owner_status(jsonb) OWNER TO nxr_g08_owner_fn_owner;
REVOKE ALL ON FUNCTION public.g08_gateway_stage_owner_status(jsonb)
    FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.g08_gateway_stage_owner_status(jsonb)
    TO nxr_g08_gateway_executor;

REVOKE CREATE ON SCHEMA public FROM nxr_g08_owner_fn_owner;
COMMIT;
