-- UNAPPLIED ADDITIVE CANDIDATE. Synthetic qualification only.
-- Bind D10's authenticated requester UID separately from the canonical person reference.
BEGIN;

CREATE OR REPLACE FUNCTION public.g08_d10_gateway_append_policy(
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
    PERFORM (p_claims->>'requester_uid')::uuid;
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

COMMIT;
