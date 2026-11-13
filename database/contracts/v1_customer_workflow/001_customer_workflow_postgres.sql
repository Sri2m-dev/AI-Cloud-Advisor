BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto') THEN
        RAISE EXCEPTION 'pgcrypto must be installed before the V1 workflow migration';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nxr_customer_workflow_owner') THEN
        CREATE ROLE nxr_customer_workflow_owner NOLOGIN NOSUPERUSER NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nxr_customer_workflow_runtime') THEN
        CREATE ROLE nxr_customer_workflow_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS;
    END IF;
END
$$;

CREATE SCHEMA IF NOT EXISTS nexora_customer_workflow
    AUTHORIZATION nxr_customer_workflow_owner;
GRANT USAGE ON SCHEMA nexora_customer_workflow TO nxr_customer_workflow_runtime;
CREATE SCHEMA IF NOT EXISTS nexora_identity
    AUTHORIZATION nxr_customer_workflow_owner;
GRANT USAGE ON SCHEMA nexora_identity
    TO nxr_customer_workflow_runtime, nxr_customer_workflow_owner;

DO $$
DECLARE
    crypto_schema name;
BEGIN
    SELECT namespace.nspname
      INTO crypto_schema
      FROM pg_extension AS extension
      JOIN pg_namespace AS namespace ON namespace.oid = extension.extnamespace
      JOIN pg_proc AS procedure ON procedure.pronamespace = namespace.oid
      JOIN pg_depend AS dependency
        ON dependency.classid = 'pg_proc'::regclass
       AND dependency.objid = procedure.oid
       AND dependency.refclassid = 'pg_extension'::regclass
       AND dependency.refobjid = extension.oid
       AND dependency.deptype = 'e'
     WHERE extension.extname = 'pgcrypto'
       AND procedure.proname = 'hmac'
       AND procedure.pronargs = 3
       AND procedure.proargtypes = '17 17 25'::oidvector;
    IF crypto_schema IS NULL THEN
        RAISE EXCEPTION 'pgcrypto hmac(bytea, bytea, text) is unavailable';
    END IF;
    EXECUTE format(
        'GRANT USAGE ON SCHEMA %I TO nxr_customer_workflow_owner',
        crypto_schema
    );
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION %I.hmac(bytea, bytea, text) '
        'TO nxr_customer_workflow_owner',
        crypto_schema
    );
END
$$;

CREATE TABLE IF NOT EXISTS nexora_identity.memberships (
    auth_user_id uuid NOT NULL,
    org_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    organization_name text NOT NULL CHECK (length(btrim(organization_name)) > 0),
    workspace_id text,
    role text NOT NULL CHECK (role IN (
        'super_admin', 'client_admin', 'executive', 'cio', 'finance',
        'operations', 'security', 'technical', 'auditor', 'viewer',
        'sales_engineer'
    )),
    status text NOT NULL CHECK (status IN ('active', 'revoked')),
    PRIMARY KEY (auth_user_id, org_id),
    CHECK (tenant_id = org_id)
);
ALTER TABLE nexora_identity.memberships OWNER TO nxr_customer_workflow_owner;
ALTER TABLE nexora_identity.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE nexora_identity.memberships FORCE ROW LEVEL SECURITY;
REVOKE ALL ON nexora_identity.memberships
    FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON nexora_identity.memberships TO nxr_customer_workflow_runtime;

CREATE TABLE IF NOT EXISTS nexora_customer_workflow.jwt_verification_settings (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    signing_secret text NOT NULL,
    issuer text NOT NULL,
    verification_mode text NOT NULL DEFAULT 'disabled'
        CHECK (verification_mode IN ('disabled', 'synthetic_hs256'))
);
ALTER TABLE nexora_customer_workflow.jwt_verification_settings
    ADD COLUMN IF NOT EXISTS verification_mode text NOT NULL DEFAULT 'disabled'
        CHECK (verification_mode IN ('disabled', 'synthetic_hs256'));
ALTER TABLE nexora_customer_workflow.jwt_verification_settings
    OWNER TO nxr_customer_workflow_owner;
REVOKE ALL ON nexora_customer_workflow.jwt_verification_settings
    FROM PUBLIC, anon, authenticated, service_role, nxr_customer_workflow_runtime;

CREATE TABLE IF NOT EXISTS nexora_customer_workflow.events (
    event_id text PRIMARY KEY,
    event_type text NOT NULL CHECK (event_type IN (
        'WORKSPACE_CREATED', 'EVIDENCE_ADMITTED', 'ASK_ANSWERED',
        'DECISION_CREATED', 'APPROVAL_REQUESTED', 'APPROVAL_TRANSITIONED',
        'EVIDENCE_EXPORT_CREATED'
    )),
    organization_id text NOT NULL,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    CHECK (tenant_id = organization_id),
    actor_id text NOT NULL,
    idempotency_key text NOT NULL,
    payload_fingerprint text NOT NULL,
    payload_ciphertext text NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    approval_id text,
    approval_action text,
    approval_state text,
    approval_stage text,
    approval_version integer,
    approval_requesting_actor text,
    approval_escalated_to text,
    ask_event_id text,
    decision_event_id text,
    evidence_event_id text,
    UNIQUE (organization_id, tenant_id, idempotency_key),
    UNIQUE (event_id, organization_id, tenant_id, workspace_id),
    CHECK (
        (event_type NOT IN ('APPROVAL_REQUESTED', 'APPROVAL_TRANSITIONED',
                            'EVIDENCE_EXPORT_CREATED'))
        OR approval_id IS NOT NULL
    ),
    FOREIGN KEY (ask_event_id, organization_id, tenant_id, workspace_id)
        REFERENCES nexora_customer_workflow.events
            (event_id, organization_id, tenant_id, workspace_id),
    FOREIGN KEY (decision_event_id, organization_id, tenant_id, workspace_id)
        REFERENCES nexora_customer_workflow.events
            (event_id, organization_id, tenant_id, workspace_id),
    FOREIGN KEY (evidence_event_id, organization_id, tenant_id, workspace_id)
        REFERENCES nexora_customer_workflow.events
            (event_id, organization_id, tenant_id, workspace_id)
);

CREATE INDEX IF NOT EXISTS events_tenant_workspace_order
    ON nexora_customer_workflow.events
       (organization_id, tenant_id, workspace_id, occurred_at, event_id);
CREATE INDEX IF NOT EXISTS events_approval_order
    ON nexora_customer_workflow.events
       (organization_id, tenant_id, workspace_id, approval_id, approval_version);

CREATE TABLE IF NOT EXISTS nexora_customer_workflow.evidence_objects (
    event_id text PRIMARY KEY,
    organization_id text NOT NULL,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    CHECK (tenant_id = organization_id),
    encrypted_content bytea NOT NULL,
    ciphertext_sha256 text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (event_id, organization_id, tenant_id, workspace_id)
        REFERENCES nexora_customer_workflow.events
            (event_id, organization_id, tenant_id, workspace_id)
);

CREATE OR REPLACE FUNCTION nexora_customer_workflow.require_evidence_object()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, nexora_customer_workflow
AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM nexora_customer_workflow.evidence_objects AS evidence
        WHERE evidence.event_id = NEW.event_id
          AND evidence.organization_id = NEW.organization_id
          AND evidence.tenant_id = NEW.tenant_id
          AND evidence.workspace_id = NEW.workspace_id
    ) THEN
        RAISE EXCEPTION 'evidence admission requires its encrypted source object'
            USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END
$function$;

CREATE TABLE IF NOT EXISTS nexora_customer_workflow.approvals (
    approval_id text PRIMARY KEY,
    organization_id text NOT NULL,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    CHECK (tenant_id = organization_id),
    requesting_actor text NOT NULL,
    decision_event_id text NOT NULL,
    evidence_event_id text NOT NULL,
    state text NOT NULL CHECK (state IN (
        'PENDING', 'ESCALATED', 'APPROVED', 'REJECTED', 'COMPLETED', 'CLOSED'
    )),
    workflow_stage text NOT NULL CHECK (workflow_stage IN ('FINANCE', 'CIO', 'CEO')),
    current_approver_role text NOT NULL CHECK (
        current_approver_role IN ('finance', 'cio', 'ceo')
    ),
    version integer NOT NULL CHECK (version > 0),
    last_event_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (approval_id, organization_id, tenant_id, workspace_id),
    FOREIGN KEY (decision_event_id, organization_id, tenant_id, workspace_id)
        REFERENCES nexora_customer_workflow.events
            (event_id, organization_id, tenant_id, workspace_id),
    FOREIGN KEY (evidence_event_id, organization_id, tenant_id, workspace_id)
        REFERENCES nexora_customer_workflow.events
            (event_id, organization_id, tenant_id, workspace_id),
    FOREIGN KEY (last_event_id, organization_id, tenant_id, workspace_id)
        REFERENCES nexora_customer_workflow.events
            (event_id, organization_id, tenant_id, workspace_id)
        DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS approvals_tenant_workspace
    ON nexora_customer_workflow.approvals
       (organization_id, tenant_id, workspace_id, created_at);

ALTER TABLE nexora_customer_workflow.events OWNER TO nxr_customer_workflow_owner;
ALTER TABLE nexora_customer_workflow.evidence_objects OWNER TO nxr_customer_workflow_owner;
ALTER TABLE nexora_customer_workflow.approvals OWNER TO nxr_customer_workflow_owner;
ALTER SCHEMA nexora_customer_workflow OWNER TO nxr_customer_workflow_owner;

ALTER TABLE nexora_customer_workflow.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE nexora_customer_workflow.events FORCE ROW LEVEL SECURITY;
ALTER TABLE nexora_customer_workflow.evidence_objects ENABLE ROW LEVEL SECURITY;
ALTER TABLE nexora_customer_workflow.evidence_objects FORCE ROW LEVEL SECURITY;
ALTER TABLE nexora_customer_workflow.approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE nexora_customer_workflow.approvals FORCE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION nexora_customer_workflow.verified_subject()
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
DECLARE
    token text;
    parts text[];
    header jsonb;
    claims jsonb;
    signing_secret text;
    expected_issuer text;
    verification_mode text;
    crypto_schema name;
    signature bytea;
    expected_signature bytea;
    expiration numeric;
    not_before numeric;
    signature_difference integer := 0;
    byte_index integer;
BEGIN
    token := nullif(current_setting('nexora.access_token', true), '');
    IF token IS NULL THEN
        RETURN NULL;
    END IF;

    parts := string_to_array(token, '.');
    IF array_length(parts, 1) <> 3 THEN
        RETURN NULL;
    END IF;

    SELECT settings.signing_secret, settings.issuer, settings.verification_mode
      INTO signing_secret, expected_issuer, verification_mode
      FROM nexora_customer_workflow.jwt_verification_settings AS settings
     WHERE settings.singleton;
    IF signing_secret IS NULL OR expected_issuer IS NULL
       OR verification_mode <> 'synthetic_hs256' THEN
        RETURN NULL;
    END IF;

    header := convert_from(
        decode(
            translate(parts[1], '-_', '+/') ||
            repeat('=', (4 - length(parts[1]) % 4) % 4),
            'base64'
        ),
        'UTF8'
    )::jsonb;
    claims := convert_from(
        decode(
            translate(parts[2], '-_', '+/') ||
            repeat('=', (4 - length(parts[2]) % 4) % 4),
            'base64'
        ),
        'UTF8'
    )::jsonb;
    signature := decode(
        translate(parts[3], '-_', '+/') ||
        repeat('=', (4 - length(parts[3]) % 4) % 4),
        'base64'
    );

    IF header->>'alg' IS DISTINCT FROM 'HS256'
       OR claims->>'iss' IS DISTINCT FROM expected_issuer
       OR claims->>'role' IS DISTINCT FROM 'authenticated'
       OR NOT coalesce(
           claims->>'aud' = 'authenticated'
           OR (
               jsonb_typeof(claims->'aud') = 'array'
               AND claims->'aud' ? 'authenticated'
           ),
           false
       )
       OR coalesce(claims->>'sub', '') !~
          '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
       OR coalesce(claims->>'exp', '') !~ '^[0-9]+$' THEN
        RETURN NULL;
    END IF;

    expiration := (claims->>'exp')::numeric;
    IF expiration <= extract(epoch FROM statement_timestamp()) THEN
        RETURN NULL;
    END IF;
    IF coalesce(claims->>'nbf', '') <> '' THEN
        IF claims->>'nbf' !~ '^[0-9]+$' THEN
            RETURN NULL;
        END IF;
        not_before := (claims->>'nbf')::numeric;
        IF not_before > extract(epoch FROM statement_timestamp()) THEN
            RETURN NULL;
        END IF;
    END IF;

    SELECT namespace.nspname
      INTO crypto_schema
      FROM pg_extension AS extension
      JOIN pg_namespace AS namespace ON namespace.oid = extension.extnamespace
      JOIN pg_proc AS procedure ON procedure.pronamespace = namespace.oid
      JOIN pg_depend AS dependency
        ON dependency.classid = 'pg_proc'::regclass
       AND dependency.objid = procedure.oid
       AND dependency.refclassid = 'pg_extension'::regclass
       AND dependency.refobjid = extension.oid
       AND dependency.deptype = 'e'
     WHERE extension.extname = 'pgcrypto'
       AND procedure.proname = 'hmac'
       AND procedure.pronargs = 3
       AND procedure.proargtypes = '17 17 25'::oidvector;
    IF crypto_schema IS NULL THEN
        RETURN NULL;
    END IF;
    EXECUTE format('SELECT %I.hmac($1, $2, $3)', crypto_schema)
       INTO expected_signature
       USING convert_to(parts[1] || '.' || parts[2], 'UTF8'),
             convert_to(signing_secret, 'UTF8'),
             'sha256';
    IF octet_length(signature) <> octet_length(expected_signature) THEN
        RETURN NULL;
    END IF;
    FOR byte_index IN 0..octet_length(signature) - 1 LOOP
        signature_difference := signature_difference
            | (get_byte(signature, byte_index) # get_byte(expected_signature, byte_index));
    END LOOP;
    IF signature_difference <> 0 THEN
        RETURN NULL;
    END IF;
    RETURN lower(claims->>'sub');
EXCEPTION
    WHEN data_exception OR invalid_parameter_value THEN
        RETURN NULL;
END
$function$;

ALTER FUNCTION nexora_customer_workflow.verified_subject()
    OWNER TO nxr_customer_workflow_owner;

CREATE OR REPLACE FUNCTION nexora_customer_workflow.verified_scope()
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
DECLARE
    subject_id text;
    profile_role text;
    organization_id text;
BEGIN
    subject_id := nexora_customer_workflow.verified_subject();
    organization_id := nullif(current_setting('nexora.organization_id', true), '');
    IF subject_id IS NULL
       OR subject_id <> nullif(current_setting('nexora.actor_id', true), '')
       OR organization_id IS NULL
       OR organization_id <> nullif(current_setting('nexora.tenant_id', true), '') THEN
        RETURN false;
    END IF;

    SELECT member.role INTO profile_role
      FROM nexora_identity.memberships AS member
     WHERE member.auth_user_id::text = subject_id
       AND member.org_id::text = organization_id
       AND member.status = 'active';
    RETURN FOUND
       AND profile_role = nullif(current_setting('nexora.role', true), '');
END
$function$;

ALTER FUNCTION nexora_customer_workflow.verified_scope()
    OWNER TO nxr_customer_workflow_owner;

DROP POLICY IF EXISTS customer_workflow_profile_self ON nexora_identity.memberships;
CREATE POLICY customer_workflow_profile_self ON nexora_identity.memberships
    FOR SELECT TO nxr_customer_workflow_runtime, nxr_customer_workflow_owner
    USING (
        auth_user_id::text = nexora_customer_workflow.verified_subject()
        AND status = 'active'
    );

DROP POLICY IF EXISTS customer_workflow_profile_scope_guard
    ON nexora_identity.memberships;
CREATE POLICY customer_workflow_profile_scope_guard ON nexora_identity.memberships
    AS RESTRICTIVE FOR SELECT TO nxr_customer_workflow_runtime,
                                  nxr_customer_workflow_owner
    USING (
        auth_user_id::text = nexora_customer_workflow.verified_subject()
        AND status = 'active'
    );

DROP POLICY IF EXISTS events_runtime_scope ON nexora_customer_workflow.events;
CREATE POLICY events_runtime_scope ON nexora_customer_workflow.events
    FOR ALL TO nxr_customer_workflow_runtime
    USING (
        nexora_customer_workflow.verified_scope()
        AND
        organization_id = nullif(current_setting('nexora.organization_id', true), '')
        AND tenant_id = nullif(current_setting('nexora.tenant_id', true), '')
        AND EXISTS (
            SELECT 1 FROM nexora_identity.memberships AS member
            WHERE member.auth_user_id::text =
                    nullif(current_setting('nexora.actor_id', true), '')
              AND member.org_id::text = organization_id
              AND member.tenant_id::text =
                    nexora_customer_workflow.events.tenant_id
              AND member.status = 'active'
              AND (member.workspace_id IS NULL
                   OR member.workspace_id = nexora_customer_workflow.events.workspace_id)
              AND member.role = nullif(current_setting('nexora.role', true), '')
        )
    )
    WITH CHECK (
        nexora_customer_workflow.verified_scope()
        AND
        organization_id = nullif(current_setting('nexora.organization_id', true), '')
        AND tenant_id = nullif(current_setting('nexora.tenant_id', true), '')
        AND actor_id = nullif(current_setting('nexora.actor_id', true), '')
        AND EXISTS (
            SELECT 1 FROM nexora_identity.memberships AS member
            WHERE member.auth_user_id::text =
                    nullif(current_setting('nexora.actor_id', true), '')
              AND member.org_id::text = organization_id
              AND member.tenant_id::text =
                    nexora_customer_workflow.events.tenant_id
              AND member.status = 'active'
              AND (member.workspace_id IS NULL
                   OR member.workspace_id = nexora_customer_workflow.events.workspace_id)
              AND member.role = nullif(current_setting('nexora.role', true), '')
              AND (
                  event_type = 'ASK_ANSWERED'
                  OR (event_type IN ('WORKSPACE_CREATED', 'EVIDENCE_ADMITTED',
                                     'DECISION_CREATED', 'APPROVAL_REQUESTED')
                      AND member.role IN ('client_admin', 'executive', 'cio',
                                          'finance', 'operations'))
                  OR (event_type = 'EVIDENCE_EXPORT_CREATED'
                      AND member.role IN ('client_admin', 'executive', 'cio',
                                          'finance', 'operations'))
                  OR event_type = 'APPROVAL_TRANSITIONED'
              )
        )
    );

DROP POLICY IF EXISTS events_owner_scope ON nexora_customer_workflow.events;
CREATE POLICY events_owner_scope ON nexora_customer_workflow.events
    FOR SELECT TO nxr_customer_workflow_owner
    USING (
        nexora_customer_workflow.verified_scope()
        AND
        organization_id = nullif(current_setting('nexora.organization_id', true), '')
        AND tenant_id = nullif(current_setting('nexora.tenant_id', true), '')
        AND EXISTS (
            SELECT 1 FROM nexora_identity.memberships AS member
            WHERE member.auth_user_id::text =
                    nullif(current_setting('nexora.actor_id', true), '')
              AND member.org_id::text = organization_id
              AND member.tenant_id::text =
                    nexora_customer_workflow.events.tenant_id
              AND member.status = 'active'
              AND (member.workspace_id IS NULL
                   OR member.workspace_id = nexora_customer_workflow.events.workspace_id)
        )
    );

DROP POLICY IF EXISTS evidence_runtime_scope ON nexora_customer_workflow.evidence_objects;
CREATE POLICY evidence_runtime_scope ON nexora_customer_workflow.evidence_objects
    FOR ALL TO nxr_customer_workflow_runtime
    USING (
        nexora_customer_workflow.verified_scope()
        AND
        organization_id = nullif(current_setting('nexora.organization_id', true), '')
        AND tenant_id = nullif(current_setting('nexora.tenant_id', true), '')
        AND EXISTS (
            SELECT 1 FROM nexora_identity.memberships AS member
            WHERE member.auth_user_id::text =
                    nullif(current_setting('nexora.actor_id', true), '')
              AND member.org_id::text = organization_id
              AND member.tenant_id::text =
                    nexora_customer_workflow.evidence_objects.tenant_id
              AND member.status = 'active'
              AND (member.workspace_id IS NULL
                   OR member.workspace_id = nexora_customer_workflow.evidence_objects.workspace_id)
              AND member.role = nullif(current_setting('nexora.role', true), '')
        )
    )
    WITH CHECK (
        nexora_customer_workflow.verified_scope()
        AND
        organization_id = nullif(current_setting('nexora.organization_id', true), '')
        AND tenant_id = nullif(current_setting('nexora.tenant_id', true), '')
        AND EXISTS (
            SELECT 1 FROM nexora_identity.memberships AS member
            WHERE member.auth_user_id::text =
                    nullif(current_setting('nexora.actor_id', true), '')
              AND member.org_id::text = organization_id
              AND member.tenant_id::text =
                    nexora_customer_workflow.evidence_objects.tenant_id
              AND member.status = 'active'
              AND (member.workspace_id IS NULL
                   OR member.workspace_id = nexora_customer_workflow.evidence_objects.workspace_id)
              AND member.role = nullif(current_setting('nexora.role', true), '')
        )
    );

DROP POLICY IF EXISTS approvals_runtime_read ON nexora_customer_workflow.approvals;
CREATE POLICY approvals_runtime_read ON nexora_customer_workflow.approvals
    FOR SELECT TO nxr_customer_workflow_runtime
    USING (
        nexora_customer_workflow.verified_scope()
        AND
        organization_id = nullif(current_setting('nexora.organization_id', true), '')
        AND tenant_id = nullif(current_setting('nexora.tenant_id', true), '')
        AND EXISTS (
            SELECT 1 FROM nexora_identity.memberships AS member
            WHERE member.auth_user_id::text =
                    nullif(current_setting('nexora.actor_id', true), '')
              AND member.org_id::text = organization_id
              AND member.tenant_id::text =
                    nexora_customer_workflow.approvals.tenant_id
              AND member.status = 'active'
              AND (member.workspace_id IS NULL
                   OR member.workspace_id = nexora_customer_workflow.approvals.workspace_id)
              AND member.role = nullif(current_setting('nexora.role', true), '')
        )
    );

DROP POLICY IF EXISTS approvals_owner_scope ON nexora_customer_workflow.approvals;
CREATE POLICY approvals_owner_scope ON nexora_customer_workflow.approvals
    FOR ALL TO nxr_customer_workflow_owner
    USING (
        nexora_customer_workflow.verified_scope()
        AND
        organization_id = nullif(current_setting('nexora.organization_id', true), '')
        AND tenant_id = nullif(current_setting('nexora.tenant_id', true), '')
        AND EXISTS (
            SELECT 1 FROM nexora_identity.memberships AS member
            WHERE member.auth_user_id::text =
                    nullif(current_setting('nexora.actor_id', true), '')
              AND member.org_id::text = organization_id
              AND member.tenant_id::text =
                    nexora_customer_workflow.approvals.tenant_id
              AND member.status = 'active'
              AND (member.workspace_id IS NULL
                   OR member.workspace_id = nexora_customer_workflow.approvals.workspace_id)
        )
    )
    WITH CHECK (
        nexora_customer_workflow.verified_scope()
        AND
        organization_id = nullif(current_setting('nexora.organization_id', true), '')
        AND tenant_id = nullif(current_setting('nexora.tenant_id', true), '')
        AND EXISTS (
            SELECT 1 FROM nexora_identity.memberships AS member
            WHERE member.auth_user_id::text =
                    nullif(current_setting('nexora.actor_id', true), '')
              AND member.org_id::text = organization_id
              AND member.tenant_id::text =
                    nexora_customer_workflow.approvals.tenant_id
              AND member.status = 'active'
              AND (member.workspace_id IS NULL
                   OR member.workspace_id =
                        nexora_customer_workflow.approvals.workspace_id)
        )
    );

CREATE OR REPLACE FUNCTION nexora_customer_workflow.enforce_event_contract()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $function$
DECLARE
    profile_role text;
    approval_row nexora_customer_workflow.approvals%ROWTYPE;
    expected_state text;
    expected_stage text;
    expected_role text;
    workspace_exists boolean;
BEGIN
    SELECT member.role INTO profile_role
    FROM nexora_identity.memberships AS member
    WHERE member.auth_user_id::text = NEW.actor_id
      AND member.org_id::text = NEW.organization_id
      AND member.tenant_id::text = NEW.tenant_id
      AND member.status = 'active'
      AND (member.workspace_id IS NULL OR member.workspace_id = NEW.workspace_id);
    IF profile_role IS NULL
       OR NEW.actor_id <> nullif(current_setting('nexora.actor_id', true), '')
       OR profile_role <> nullif(current_setting('nexora.role', true), '') THEN
        RAISE EXCEPTION 'customer workflow actor membership mismatch'
            USING ERRCODE = '42501';
    END IF;

    IF NEW.event_type <> 'WORKSPACE_CREATED' THEN
        SELECT EXISTS (
            SELECT 1 FROM nexora_customer_workflow.events AS existing
            WHERE existing.organization_id = NEW.organization_id
              AND existing.tenant_id = NEW.tenant_id
              AND existing.workspace_id = NEW.workspace_id
              AND existing.event_type = 'WORKSPACE_CREATED'
        ) INTO workspace_exists;
        IF NOT workspace_exists THEN
            RAISE EXCEPTION 'customer workflow workspace is not available'
                USING ERRCODE = '42501';
        END IF;
    END IF;

    IF NEW.event_type = 'ASK_ANSWERED'
       AND NOT EXISTS (
           SELECT 1 FROM nexora_customer_workflow.events AS evidence
           WHERE evidence.event_id = NEW.evidence_event_id
             AND evidence.organization_id = NEW.organization_id
             AND evidence.tenant_id = NEW.tenant_id
             AND evidence.workspace_id = NEW.workspace_id
             AND evidence.event_type = 'EVIDENCE_ADMITTED'
       ) THEN
        RAISE EXCEPTION 'customer Ask must reference admitted evidence'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.event_type = 'DECISION_CREATED'
       AND NOT EXISTS (
           SELECT 1
           FROM nexora_customer_workflow.events AS source_ask
           JOIN nexora_customer_workflow.events AS source_evidence
             ON source_evidence.event_id = source_ask.evidence_event_id
            AND source_evidence.organization_id = source_ask.organization_id
            AND source_evidence.tenant_id = source_ask.tenant_id
            AND source_evidence.workspace_id = source_ask.workspace_id
           WHERE source_ask.event_id = NEW.ask_event_id
             AND source_ask.organization_id = NEW.organization_id
             AND source_ask.tenant_id = NEW.tenant_id
             AND source_ask.workspace_id = NEW.workspace_id
             AND source_ask.event_type = 'ASK_ANSWERED'
             AND source_evidence.event_type = 'EVIDENCE_ADMITTED'
             AND source_evidence.event_id = NEW.evidence_event_id
       ) THEN
        RAISE EXCEPTION 'customer decision must reference its grounded Ask and evidence'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.event_type = 'APPROVAL_REQUESTED' THEN
        IF profile_role NOT IN ('client_admin', 'executive', 'cio', 'finance', 'operations')
           OR NEW.approval_version IS DISTINCT FROM 1
           OR NEW.approval_state <> 'PENDING'
           OR NEW.approval_stage <> 'FINANCE'
           OR NEW.approval_requesting_actor <> NEW.actor_id
           OR NOT EXISTS (
               SELECT 1 FROM nexora_customer_workflow.events AS decision
               WHERE decision.event_id = NEW.decision_event_id
                 AND decision.organization_id = NEW.organization_id
                 AND decision.tenant_id = NEW.tenant_id
                 AND decision.workspace_id = NEW.workspace_id
                 AND decision.event_type = 'DECISION_CREATED'
           )
           OR NOT EXISTS (
               SELECT 1 FROM nexora_customer_workflow.events AS evidence
               WHERE evidence.event_id = NEW.evidence_event_id
                 AND evidence.organization_id = NEW.organization_id
                 AND evidence.tenant_id = NEW.tenant_id
                 AND evidence.workspace_id = NEW.workspace_id
                 AND evidence.event_type = 'EVIDENCE_ADMITTED'
           ) THEN
            RAISE EXCEPTION 'customer approval request contract is invalid'
                USING ERRCODE = '42501';
        END IF;
        INSERT INTO nexora_customer_workflow.approvals (
            approval_id, organization_id, tenant_id, workspace_id,
            requesting_actor, decision_event_id, evidence_event_id, state,
            workflow_stage, current_approver_role, version, last_event_id
        ) VALUES (
            NEW.approval_id, NEW.organization_id, NEW.tenant_id, NEW.workspace_id,
            NEW.approval_requesting_actor, NEW.decision_event_id, NEW.evidence_event_id,
            NEW.approval_state, NEW.approval_stage, 'finance', 1, NEW.event_id
        );
    ELSIF NEW.event_type = 'APPROVAL_TRANSITIONED' THEN
        PERFORM pg_advisory_xact_lock(
            hashtextextended(
                NEW.organization_id || ':' || NEW.tenant_id || ':' ||
                NEW.workspace_id || ':' || NEW.approval_id,
                0
            )
        );
        SELECT * INTO STRICT approval_row
        FROM nexora_customer_workflow.approvals AS approval
        WHERE approval.approval_id = NEW.approval_id
          AND approval.organization_id = NEW.organization_id
          AND approval.tenant_id = NEW.tenant_id
          AND approval.workspace_id = NEW.workspace_id
        FOR UPDATE;
        expected_role := CASE approval_row.workflow_stage
            WHEN 'FINANCE' THEN 'finance'
            WHEN 'CIO' THEN 'cio'
            ELSE 'executive'
        END;
        IF approval_row.state NOT IN ('PENDING', 'ESCALATED')
           OR NEW.approval_requesting_actor <> approval_row.requesting_actor
           OR NEW.actor_id = approval_row.requesting_actor
           OR profile_role <> expected_role
           OR NEW.approval_version IS DISTINCT FROM approval_row.version + 1 THEN
            RAISE EXCEPTION 'customer approval stage, actor, or version mismatch'
                USING ERRCODE = '42501';
        END IF;
        expected_state := NEW.approval_action;
        expected_stage := approval_row.workflow_stage;
        IF NEW.approval_action = 'APPROVED' THEN
            IF approval_row.workflow_stage = 'FINANCE' THEN
                expected_state := 'PENDING';
                expected_stage := 'CIO';
            ELSIF approval_row.workflow_stage = 'CIO' THEN
                expected_state := 'PENDING';
                expected_stage := 'CEO';
            ELSE
                expected_state := 'APPROVED';
            END IF;
        ELSIF NEW.approval_action = 'REJECTED' THEN
            expected_state := 'REJECTED';
        ELSIF NEW.approval_action = 'ESCALATED' THEN
            expected_state := 'ESCALATED';
            IF NEW.approval_escalated_to NOT IN ('cio', 'ceo') THEN
                RAISE EXCEPTION 'customer approval escalation target is invalid'
                    USING ERRCODE = '23514';
            END IF;
        ELSE
            RAISE EXCEPTION 'customer approval action is invalid'
                USING ERRCODE = '23514';
        END IF;
        expected_role := CASE expected_stage
            WHEN 'FINANCE' THEN 'finance'
            WHEN 'CIO' THEN 'cio'
            ELSE 'ceo'
        END;
        IF NEW.approval_state <> expected_state
           OR NEW.approval_stage <> expected_stage THEN
            RAISE EXCEPTION 'customer approval transition does not follow stage order'
                USING ERRCODE = '42501';
        END IF;
        UPDATE nexora_customer_workflow.approvals
        SET state = expected_state, workflow_stage = expected_stage,
            current_approver_role = expected_role, version = NEW.approval_version,
            last_event_id = NEW.event_id
        WHERE approval_id = NEW.approval_id;
    ELSIF NEW.event_type = 'EVIDENCE_EXPORT_CREATED' THEN
        SELECT * INTO STRICT approval_row
        FROM nexora_customer_workflow.approvals AS approval
        WHERE approval.approval_id = NEW.approval_id
          AND approval.organization_id = NEW.organization_id
          AND approval.tenant_id = NEW.tenant_id
          AND approval.workspace_id = NEW.workspace_id;
        IF approval_row.state <> 'APPROVED'
           OR profile_role NOT IN ('client_admin', 'executive', 'cio',
                                   'finance', 'operations')
           OR NEW.decision_event_id <> approval_row.decision_event_id
           OR NEW.evidence_event_id <> approval_row.evidence_event_id
           OR NOT EXISTS (
               SELECT 1 FROM nexora_customer_workflow.events AS decision
               WHERE decision.event_id = NEW.decision_event_id
                 AND decision.ask_event_id = NEW.ask_event_id
                 AND decision.evidence_event_id = NEW.evidence_event_id
                 AND decision.organization_id = NEW.organization_id
                 AND decision.tenant_id = NEW.tenant_id
                 AND decision.workspace_id = NEW.workspace_id
                 AND decision.event_type = 'DECISION_CREATED'
           )
           OR NOT EXISTS (
               SELECT 1 FROM nexora_customer_workflow.events AS ask
               WHERE ask.event_id = NEW.ask_event_id
                 AND ask.evidence_event_id = NEW.evidence_event_id
                 AND ask.organization_id = NEW.organization_id
                 AND ask.tenant_id = NEW.tenant_id
                 AND ask.workspace_id = NEW.workspace_id
                 AND ask.event_type = 'ASK_ANSWERED'
           ) THEN
            RAISE EXCEPTION 'customer evidence export is not authorized'
                USING ERRCODE = '42501';
        END IF;
    END IF;
    RETURN NEW;
END
$function$;
ALTER FUNCTION nexora_customer_workflow.enforce_event_contract()
    OWNER TO nxr_customer_workflow_owner;

ALTER FUNCTION nexora_customer_workflow.enforce_event_contract()
    OWNER TO nxr_customer_workflow_owner;

DROP TRIGGER IF EXISTS enforce_customer_workflow_event ON nexora_customer_workflow.events;
CREATE TRIGGER enforce_customer_workflow_event
BEFORE INSERT ON nexora_customer_workflow.events
FOR EACH ROW EXECUTE FUNCTION nexora_customer_workflow.enforce_event_contract();

CREATE OR REPLACE FUNCTION nexora_customer_workflow.reject_event_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $function$
BEGIN
    RAISE EXCEPTION 'customer workflow events are append-only'
        USING ERRCODE = '42501';
END
$function$;

DROP TRIGGER IF EXISTS customer_workflow_events_no_update
    ON nexora_customer_workflow.events;
CREATE TRIGGER customer_workflow_events_no_update
BEFORE UPDATE OR DELETE ON nexora_customer_workflow.events
FOR EACH ROW EXECUTE FUNCTION nexora_customer_workflow.reject_event_mutation();

DROP TRIGGER IF EXISTS customer_workflow_evidence_object_required
    ON nexora_customer_workflow.events;
CREATE CONSTRAINT TRIGGER customer_workflow_evidence_object_required
AFTER INSERT ON nexora_customer_workflow.events
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
WHEN (NEW.event_type = 'EVIDENCE_ADMITTED')
EXECUTE FUNCTION nexora_customer_workflow.require_evidence_object();

DROP TRIGGER IF EXISTS customer_workflow_evidence_no_update
    ON nexora_customer_workflow.evidence_objects;
CREATE TRIGGER customer_workflow_evidence_no_update
BEFORE UPDATE OR DELETE ON nexora_customer_workflow.evidence_objects
FOR EACH ROW EXECUTE FUNCTION nexora_customer_workflow.reject_event_mutation();

GRANT SELECT, INSERT ON nexora_customer_workflow.events,
    nexora_customer_workflow.evidence_objects
    TO nxr_customer_workflow_runtime;
GRANT SELECT ON nexora_customer_workflow.approvals
    TO nxr_customer_workflow_runtime;
REVOKE UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA
    nexora_customer_workflow FROM nxr_customer_workflow_runtime;
GRANT USAGE ON SCHEMA nexora_customer_workflow TO nxr_customer_workflow_owner;
GRANT SELECT, INSERT, UPDATE ON nexora_customer_workflow.approvals
    TO nxr_customer_workflow_owner;
GRANT SELECT ON nexora_customer_workflow.events TO nxr_customer_workflow_owner;
REVOKE ALL ON FUNCTION nexora_customer_workflow.enforce_event_contract()
    FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION nexora_customer_workflow.verified_subject()
    FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION nexora_customer_workflow.verified_scope()
    FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION nexora_customer_workflow.reject_event_mutation()
    FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION nexora_customer_workflow.require_evidence_object()
    FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION nexora_customer_workflow.verified_subject()
    TO nxr_customer_workflow_runtime, nxr_customer_workflow_owner;
GRANT EXECUTE ON FUNCTION nexora_customer_workflow.verified_scope()
    TO nxr_customer_workflow_runtime, nxr_customer_workflow_owner;

COMMIT;
