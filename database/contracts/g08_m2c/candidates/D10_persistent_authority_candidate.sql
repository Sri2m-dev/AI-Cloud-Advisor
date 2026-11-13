-- UNAPPLIED CANDIDATE. Never add to an automatic migration queue.
-- Additive D10 metadata proposal; no runtime grants/functions and no owner-operation
-- execution or receipt-read activation. Requires independent review and target approval.
BEGIN;

CREATE TABLE public.g08_d10_policy_versions (
    authorization_id uuid NOT NULL
        REFERENCES public.g08_owner_operation_authorizations(authorization_id) ON DELETE RESTRICT,
    policy_version text NOT NULL CHECK (length(btrim(policy_version)) BETWEEN 1 AND 128),
    policy_id text NOT NULL CHECK (length(btrim(policy_id)) BETWEEN 1 AND 256),
    issuer_key_id text NOT NULL CHECK (length(btrim(issuer_key_id)) BETWEEN 1 AND 256),
    policy_jti text NOT NULL UNIQUE CHECK (length(btrim(policy_jti)) BETWEEN 1 AND 256),
    claims jsonb NOT NULL CHECK (jsonb_typeof(claims) = 'object'),
    signature bytea NOT NULL CHECK (octet_length(signature) = 64),
    valid_from timestamptz NOT NULL,
    valid_to timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (authorization_id, policy_version),
    UNIQUE (authorization_id, policy_version, policy_id),
    CHECK (valid_to > valid_from)
);

CREATE TABLE public.g08_d10_authority_state (
    authorization_id uuid PRIMARY KEY
        REFERENCES public.g08_owner_operation_authorizations(authorization_id) ON DELETE RESTRICT,
    current_policy_version text NOT NULL,
    revision bigint NOT NULL CHECK (revision > 0),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (authorization_id, current_policy_version)
        REFERENCES public.g08_d10_policy_versions(authorization_id, policy_version)
        ON DELETE RESTRICT
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE public.g08_d10_approval_evidence (
    approval_id uuid PRIMARY KEY,
    authorization_id uuid NOT NULL,
    policy_version text NOT NULL,
    policy_id text NOT NULL,
    approver_auth_uid uuid NOT NULL,
    issuer_key_id text NOT NULL CHECK (length(btrim(issuer_key_id)) BETWEEN 1 AND 256),
    approval_jti text NOT NULL UNIQUE CHECK (length(btrim(approval_jti)) BETWEEN 1 AND 256),
    claims jsonb NOT NULL CHECK (jsonb_typeof(claims) = 'object'),
    signature bytea NOT NULL CHECK (octet_length(signature) = 64),
    valid_from timestamptz NOT NULL,
    valid_to timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (authorization_id, policy_version, policy_id)
        REFERENCES public.g08_d10_policy_versions(authorization_id, policy_version, policy_id)
        ON DELETE RESTRICT,
    UNIQUE (authorization_id, policy_version, approver_auth_uid),
    CHECK (valid_to > valid_from)
);

CREATE TABLE public.g08_d10_revocations (
    revocation_id uuid PRIMARY KEY,
    authorization_id uuid NOT NULL
        REFERENCES public.g08_owner_operation_authorizations(authorization_id) ON DELETE RESTRICT,
    subject_type text NOT NULL CHECK (
        subject_type IN ('AUTHORIZATION', 'APPROVAL', 'OPERATOR_EVIDENCE', 'FENCING_TOKEN')
    ),
    subject_id text NOT NULL CHECK (length(btrim(subject_id)) BETWEEN 1 AND 256),
    issuer_key_id text NOT NULL CHECK (length(btrim(issuer_key_id)) BETWEEN 1 AND 256),
    revocation_jti text NOT NULL UNIQUE CHECK (length(btrim(revocation_jti)) BETWEEN 1 AND 256),
    claims jsonb NOT NULL CHECK (jsonb_typeof(claims) = 'object'),
    signature bytea NOT NULL CHECK (octet_length(signature) = 64),
    revoked_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (authorization_id, subject_type, subject_id),
    -- JTI-based revocation lookups must not be ambiguous across authorizations.
    UNIQUE (subject_type, subject_id)
);

CREATE TABLE public.g08_d10_fencing_state (
    tenant_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    action text NOT NULL CHECK (length(btrim(action)) BETWEEN 1 AND 128),
    target_resource text NOT NULL CHECK (length(btrim(target_resource)) BETWEEN 1 AND 2048),
    current_generation bigint NOT NULL CHECK (current_generation > 0),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (
        tenant_id, organization_id, action, target_resource
    ),
    CHECK (tenant_id = organization_id)
);

-- Canonical receipts are global. This immutable edge records a separately
-- verified tenant projection; it must be staged atomically with the canonical receipt.
ALTER TABLE public.g08_owner_operation_receipts
    ADD CONSTRAINT g08_owner_receipt_scope_candidate_key
    UNIQUE (event_id, authorization_id, owner_operation_id);

CREATE TABLE public.g08_d10_receipt_scope_bindings (
    event_id uuid PRIMARY KEY,
    authorization_id uuid NOT NULL,
    owner_operation_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    policy_version text NOT NULL,
    binding_jti text NOT NULL UNIQUE CHECK (length(btrim(binding_jti)) BETWEEN 1 AND 256),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (event_id, authorization_id, owner_operation_id)
        REFERENCES public.g08_owner_operation_receipts(event_id, authorization_id, owner_operation_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (authorization_id, owner_operation_id)
        REFERENCES public.g08_owner_operation_authorizations(authorization_id, owner_operation_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (authorization_id, policy_version)
        REFERENCES public.g08_d10_policy_versions(authorization_id, policy_version)
        ON DELETE RESTRICT,
    CHECK (tenant_id = organization_id)
);

CREATE FUNCTION public.g08_d10_deny_history_mutation() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    RAISE EXCEPTION 'D10 authority history is append-only'
        USING ERRCODE = '55000';
END
$$;

CREATE TRIGGER g08_d10_policy_versions_immutable
    BEFORE UPDATE OR DELETE ON public.g08_d10_policy_versions
    FOR EACH ROW EXECUTE FUNCTION public.g08_d10_deny_history_mutation();
CREATE TRIGGER g08_d10_approval_evidence_immutable
    BEFORE UPDATE OR DELETE ON public.g08_d10_approval_evidence
    FOR EACH ROW EXECUTE FUNCTION public.g08_d10_deny_history_mutation();
CREATE TRIGGER g08_d10_revocations_immutable
    BEFORE UPDATE OR DELETE ON public.g08_d10_revocations
    FOR EACH ROW EXECUTE FUNCTION public.g08_d10_deny_history_mutation();
CREATE TRIGGER g08_d10_receipt_scope_immutable
    BEFORE UPDATE OR DELETE ON public.g08_d10_receipt_scope_bindings
    FOR EACH ROW EXECUTE FUNCTION public.g08_d10_deny_history_mutation();
REVOKE ALL ON FUNCTION public.g08_d10_deny_history_mutation()
    FROM PUBLIC, anon, authenticated, service_role;

DO $security$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'g08_d10_policy_versions',
        'g08_d10_authority_state',
        'g08_d10_approval_evidence',
        'g08_d10_revocations',
        'g08_d10_fencing_state',
        'g08_d10_receipt_scope_bindings'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC, anon, authenticated, service_role', t);
    END LOOP;
END
$security$;

-- Intentionally no policies, grants, writer functions, or runtime activation.
-- Transactional adapters require an independently reviewed, least-privilege
-- writer/reader API that serializes changes through g08_d10_authority_state.
COMMIT;
