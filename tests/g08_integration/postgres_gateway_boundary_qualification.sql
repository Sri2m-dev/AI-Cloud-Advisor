-- Real PostgreSQL boundary checks for the deliberately closed G08 owner gateway.
-- Local disposable target only; all synthetic rows are rolled back.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL timezone='UTC';

DO $$
DECLARE
    expected_tables text[] := ARRAY[
        'g08_owner_operation_authorizations',
        'g08_owner_operation_receipts',
        'g08_owner_operation_consumptions',
        'g08_d10_policy_versions',
        'g08_d10_authority_state',
        'g08_d10_approval_evidence',
        'g08_d10_revocations',
        'g08_d10_fencing_state',
        'g08_d10_receipt_scope_bindings'
    ];
    table_name text;
    blocked boolean;
    error_message text;
BEGIN
    IF current_setting('nexora.qualification_authorized', true)
           IS DISTINCT FROM 'local-disposable'
       OR current_database() <> 'nexora_m2c_g08gateway_20261111'
       OR (
           inet_server_addr() IS NOT NULL
           AND inet_server_addr() NOT IN ('127.0.0.1'::inet, '::1'::inet)
       ) THEN
        RAISE EXCEPTION 'explicit isolated local PostgreSQL target required';
    END IF;

    FOREACH table_name IN ARRAY expected_tables LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname = table_name
              AND c.relrowsecurity
              AND c.relforcerowsecurity
        ) THEN
            RAISE EXCEPTION 'RLS missing or not forced on %', table_name;
        END IF;
        IF has_table_privilege(
            'authenticated', format('public.%I', table_name), 'SELECT,INSERT,UPDATE,DELETE'
        ) OR has_table_privilege(
            'service_role', format('public.%I', table_name), 'SELECT,INSERT,UPDATE,DELETE'
        ) THEN
            RAISE EXCEPTION 'runtime table access unexpectedly granted on %', table_name;
        END IF;
    END LOOP;

    IF has_function_privilege(
        'authenticated', 'public.g08_control_owner_operation(text,jsonb)', 'EXECUTE'
    ) OR has_function_privilege(
        'service_role', 'public.g08_control_owner_operation(text,jsonb)', 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'owner control RPC unexpectedly exposed';
    END IF;

    EXECUTE 'SET LOCAL ROLE nxr_g08_owner_fn_owner';
    blocked := false;
    BEGIN
        PERFORM public.g08_control_owner_operation('EXECUTION', '{"verified":true}');
    EXCEPTION WHEN SQLSTATE '55000' THEN
        GET STACKED DIAGNOSTICS error_message = MESSAGE_TEXT;
        blocked := error_message LIKE 'IDENTITY_ASSURANCE_UNAVAILABLE:%';
    END;
    EXECUTE 'RESET ROLE';
    IF NOT blocked THEN
        RAISE EXCEPTION 'owner execution did not fail closed at the identity boundary';
    END IF;

    EXECUTE 'SET LOCAL ROLE nxr_g08_owner_reader_owner';
    blocked := false;
    BEGIN
        PERFORM public.g08_read_owner_operation_receipt('{}');
    EXCEPTION WHEN SQLSTATE '55000' THEN
        GET STACKED DIAGNOSTICS error_message = MESSAGE_TEXT;
        blocked := error_message LIKE 'IDENTITY_ASSURANCE_UNAVAILABLE:%';
    END;
    EXECUTE 'RESET ROLE';
    IF NOT blocked THEN
        RAISE EXCEPTION 'owner receipt projection did not fail closed';
    END IF;
END
$$;

DO $$
DECLARE
    auth_id uuid := 'f0000000-0000-4000-8000-000000000001';
    blocked boolean := false;
BEGIN
    INSERT INTO public.g08_owner_operation_authorizations VALUES (
        auth_id,
        'f0000000-0000-4000-8000-000000000002',
        'grant',
        'global',
        'f0000000-0000-4000-8000-000000000003',
        NULL,
        '{}'::jsonb,
        NULL,
        'candidate-policy-v1',
        'synthetic-requester',
        'synthetic-operator',
        'synthetic-auth-evidence',
        repeat('a', 64),
        repeat('b', 64),
        repeat('c', 64),
        repeat('d', 64),
        'synthetic-authorization',
        clock_timestamp() - interval '1 minute',
        clock_timestamp() + interval '1 hour'
    );
    INSERT INTO public.g08_d10_policy_versions (
        authorization_id, policy_version, policy_id, issuer_key_id, policy_jti,
        claims, signature, valid_from, valid_to
    ) VALUES (
        auth_id, 'candidate-policy-v1', 'candidate-policy',
        'synthetic-issuer', 'synthetic-policy-jti', '{}'::jsonb,
        decode(repeat('00', 64), 'hex'),
        clock_timestamp() - interval '1 minute',
        clock_timestamp() + interval '1 hour'
    );
    INSERT INTO public.g08_d10_authority_state (
        authorization_id, current_policy_version, revision
    ) VALUES (auth_id, 'candidate-policy-v1', 1);

    BEGIN
        UPDATE public.g08_d10_policy_versions p
        SET policy_id = 'changed'
        WHERE p.authorization_id = auth_id
          AND p.policy_version = 'candidate-policy-v1';
        RAISE EXCEPTION 'D10 immutable policy update unexpectedly succeeded';
    EXCEPTION WHEN SQLSTATE '55000' THEN
        blocked := true;
    END;
    IF NOT blocked THEN
        RAISE EXCEPTION 'D10 policy history is mutable';
    END IF;
END
$$;

ROLLBACK;
