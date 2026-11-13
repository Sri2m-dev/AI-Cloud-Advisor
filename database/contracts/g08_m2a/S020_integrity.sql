-- M2-A staged migration. NOT installed or placed in the automatic migration queue.
-- Requires an authorized quiescent target, auth.users and role-creation authority.
-- Deliberately fail on existing objects: never replace an unknown accepted schema.
BEGIN;

CREATE ROLE nxr_g08_history_check_owner NOLOGIN NOSUPERUSER NOBYPASSRLS
  NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
CREATE ROLE nxr_g08_identity_fn_owner NOLOGIN NOSUPERUSER NOBYPASSRLS
  NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
REVOKE CREATE ON SCHEMA public FROM nxr_g08_history_check_owner, nxr_g08_identity_fn_owner;
GRANT USAGE ON SCHEMA public TO nxr_g08_history_check_owner, nxr_g08_identity_fn_owner;

CREATE DOMAIN public.g08_sha256 AS text CHECK (VALUE ~ '^[0-9a-f]{64}$');
CREATE DOMAIN public.g08_evidence_ref AS text
  CHECK (length(btrim(VALUE)) > 0 AND octet_length(VALUE) <= 2048);
CREATE DOMAIN public.g08_rationale AS text
  CHECK (length(btrim(VALUE)) > 0 AND octet_length(VALUE) <= 4096);
CREATE DOMAIN public.g08_operation_key AS text CHECK (VALUE ~ '^[A-Za-z0-9._:-]{1,128}$');

CREATE TABLE public.g08_identity_administrator_requests (
 request_id uuid PRIMARY KEY, requester_auth_uid uuid NOT NULL,
 requester_person_ref public.g08_evidence_ref NOT NULL,
 requester_identity_evidence_ref public.g08_evidence_ref NOT NULL,
 intended_executor_auth_uid uuid NOT NULL,
 action text NOT NULL CHECK (action IN ('grant','revise','revoke')),
 administrator_id uuid NOT NULL, expected_revision bigint,
 subject_auth_uid uuid, valid_from timestamptz, valid_to timestamptz,
 rationale public.g08_rationale NOT NULL, evidence_ref public.g08_evidence_ref NOT NULL,
 policy_version public.g08_evidence_ref NOT NULL, intent_version text NOT NULL,
 intent_sha256 public.g08_sha256 NOT NULL, submitted_at timestamptz NOT NULL,
 submission_key public.g08_operation_key NOT NULL, correlation_id uuid NOT NULL,
 UNIQUE (requester_auth_uid, submission_key),
 UNIQUE (request_id, intent_sha256, policy_version),
 CHECK ((action='grant' AND expected_revision IS NULL AND subject_auth_uid IS NOT NULL
         AND valid_from IS NOT NULL AND (valid_to IS NULL OR valid_to > valid_from))
     OR (action='revise' AND expected_revision IS NOT NULL AND expected_revision BETWEEN 1 AND 9223372036854775806
         AND subject_auth_uid IS NULL AND valid_from IS NULL)
     OR (action='revoke' AND expected_revision IS NOT NULL AND expected_revision BETWEEN 1 AND 9223372036854775806
         AND subject_auth_uid IS NULL AND valid_from IS NULL AND valid_to IS NULL))
);
CREATE TABLE public.g08_identity_administrator_approvals (
 approval_id uuid PRIMARY KEY, request_id uuid NOT NULL,
 intent_sha256 public.g08_sha256 NOT NULL, approver_auth_uid uuid NOT NULL,
 approver_person_ref public.g08_evidence_ref NOT NULL,
 approver_identity_evidence_ref public.g08_evidence_ref NOT NULL,
 validator_ref public.g08_evidence_ref NOT NULL,
 validation_evidence_ref public.g08_evidence_ref NOT NULL,
 approval_evidence_ref public.g08_evidence_ref NOT NULL,
 approved_at timestamptz NOT NULL, expires_at timestamptz NOT NULL,
 policy_version public.g08_evidence_ref NOT NULL,
 UNIQUE(request_id, approver_auth_uid),
 FOREIGN KEY (request_id, intent_sha256, policy_version) REFERENCES
 public.g08_identity_administrator_requests(request_id, intent_sha256, policy_version) ON DELETE RESTRICT,
 CHECK (expires_at > approved_at)
);
CREATE TABLE public.g08_identity_administrator_approval_withdrawals (
 withdrawal_id uuid PRIMARY KEY, approval_id uuid NOT NULL UNIQUE REFERENCES
 public.g08_identity_administrator_approvals(approval_id) ON DELETE RESTRICT,
 actor_auth_uid uuid NOT NULL, validator_ref public.g08_evidence_ref NOT NULL,
 evidence_ref public.g08_evidence_ref NOT NULL, rationale public.g08_rationale NOT NULL,
 occurred_at timestamptz NOT NULL
);
CREATE TABLE public.g08_identity_administrators (
 administrator_id uuid PRIMARY KEY,
 subject_auth_uid uuid NOT NULL REFERENCES auth.users(id) ON DELETE RESTRICT,
 valid_from timestamptz NOT NULL, valid_to timestamptz,
 revision bigint NOT NULL CHECK (revision > 0), revoked_at timestamptz,
 bootstrap_evidence_ref public.g08_evidence_ref NOT NULL,
 origin_event_id uuid NOT NULL, current_event_id uuid NOT NULL,
 CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE TABLE public.g08_identity_administrator_versions (
 administrator_id uuid NOT NULL REFERENCES public.g08_identity_administrators(administrator_id) ON DELETE RESTRICT,
 subject_auth_uid uuid NOT NULL, valid_from timestamptz NOT NULL, valid_to timestamptz,
 revision bigint NOT NULL CHECK (revision > 0), revoked_at timestamptz,
 bootstrap_evidence_ref public.g08_evidence_ref NOT NULL,
 origin_event_id uuid NOT NULL, current_event_id uuid NOT NULL, event_id uuid NOT NULL UNIQUE,
 PRIMARY KEY(administrator_id, revision), UNIQUE(administrator_id, revision, event_id),
 CHECK(current_event_id=event_id), CHECK(valid_to IS NULL OR valid_to > valid_from)
);

-- Opaque validated intent; no admission grants. These columns do not authenticate a person.
CREATE TABLE public.g08_owner_operation_authorizations (
 authorization_id uuid PRIMARY KEY, owner_operation_id uuid NOT NULL UNIQUE,
 operation text NOT NULL CHECK(operation IN ('grant','revise','revoke')),
 scope_key text NOT NULL CHECK(scope_key='global'), administrator_id uuid NOT NULL,
 expected_revision bigint, mutation jsonb NOT NULL CHECK(jsonb_typeof(mutation)='object'),
 parent_operation_id uuid REFERENCES public.g08_owner_operation_authorizations(owner_operation_id) ON DELETE RESTRICT,
 policy_version public.g08_evidence_ref NOT NULL, requester_person_ref public.g08_evidence_ref NOT NULL,
 operator_person_ref public.g08_evidence_ref NOT NULL,
 operator_authentication_evidence_ref public.g08_evidence_ref NOT NULL,
 operator_authentication_evidence_sha256 public.g08_sha256 NOT NULL,
 authorization_sha256 public.g08_sha256 NOT NULL, approval_manifest_sha256 public.g08_sha256 NOT NULL,
 intent_sha256 public.g08_sha256 NOT NULL, evidence_ref public.g08_evidence_ref NOT NULL,
 valid_from timestamptz NOT NULL, valid_to timestamptz NOT NULL,
 CHECK(valid_to > valid_from), UNIQUE(authorization_id, owner_operation_id),
 CHECK((operation='grant' AND expected_revision IS NULL) OR
       (operation<>'grant' AND expected_revision IS NOT NULL AND expected_revision BETWEEN 1 AND 9223372036854775806))
);
CREATE TABLE public.g08_owner_operation_approval_links (
 authorization_id uuid NOT NULL REFERENCES public.g08_owner_operation_authorizations(authorization_id) ON DELETE RESTRICT,
 approval_ref public.g08_evidence_ref NOT NULL, approver_person_ref public.g08_evidence_ref NOT NULL,
 attestation_sha256 public.g08_sha256 NOT NULL, evidence_ref public.g08_evidence_ref NOT NULL,
 PRIMARY KEY(authorization_id, approval_ref), UNIQUE(authorization_id, approver_person_ref)
);
-- DBR-02 status/consumption are intentionally not inferred from mutable flags here.
CREATE TABLE public.g08_identity_administrator_events (
 event_id uuid PRIMARY KEY, administrator_id uuid NOT NULL,
 action text NOT NULL CHECK(action IN ('grant','revise','revoke')),
 before_revision bigint, after_revision bigint NOT NULL CHECK(after_revision > 0),
 request_id uuid UNIQUE REFERENCES public.g08_identity_administrator_requests(request_id) ON DELETE RESTRICT,
 requester_auth_uid uuid, executor_auth_uid uuid, executor_db_role public.g08_evidence_ref NOT NULL,
 execution_mode text NOT NULL CHECK(execution_mode IN ('authenticated','owner_controlled')),
 authorizing_administrator_id uuid, authorizing_revision bigint,
 owner_operation_id uuid UNIQUE REFERENCES public.g08_owner_operation_authorizations(owner_operation_id) ON DELETE RESTRICT,
 intent_sha256 public.g08_sha256 NOT NULL, request_digest public.g08_sha256 NOT NULL,
 fingerprint_version text NOT NULL, rationale public.g08_rationale NOT NULL,
 evidence_ref public.g08_evidence_ref NOT NULL, occurred_at timestamptz NOT NULL, correlation_id uuid NOT NULL,
 UNIQUE(administrator_id, after_revision), UNIQUE(administrator_id, event_id),
 UNIQUE(administrator_id, after_revision, event_id),
 FOREIGN KEY(administrator_id, before_revision) REFERENCES
 public.g08_identity_administrator_versions(administrator_id, revision) ON DELETE NO ACTION,
 FOREIGN KEY(authorizing_administrator_id, authorizing_revision) REFERENCES
 public.g08_identity_administrator_versions(administrator_id, revision) ON DELETE NO ACTION,
 CHECK((authorizing_administrator_id IS NULL)=(authorizing_revision IS NULL)),
 CHECK((action='grant' AND before_revision IS NULL AND after_revision=1) OR
       (action<>'grant' AND before_revision IS NOT NULL AND before_revision BETWEEN 1 AND 9223372036854775806 AND after_revision=before_revision+1)),
 CHECK((execution_mode='authenticated' AND request_id IS NOT NULL AND requester_auth_uid IS NOT NULL
   AND executor_auth_uid IS NOT NULL AND authorizing_administrator_id IS NOT NULL AND owner_operation_id IS NULL)
 OR (execution_mode='owner_controlled' AND owner_operation_id IS NOT NULL AND request_id IS NULL
   AND requester_auth_uid IS NULL AND executor_auth_uid IS NULL AND authorizing_administrator_id IS NULL))
);
ALTER TABLE public.g08_identity_administrators ADD CONSTRAINT g08_current_version_fk
 FOREIGN KEY(administrator_id,revision,current_event_id) REFERENCES
 public.g08_identity_administrator_versions(administrator_id,revision,event_id)
 ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE public.g08_identity_administrators ADD CONSTRAINT g08_origin_event_fk
 FOREIGN KEY(administrator_id,origin_event_id) REFERENCES
 public.g08_identity_administrator_events(administrator_id,event_id)
 ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE public.g08_identity_administrator_versions ADD CONSTRAINT g08_version_event_fk
 FOREIGN KEY(administrator_id,revision,event_id) REFERENCES
 public.g08_identity_administrator_events(administrator_id,after_revision,event_id)
 ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE public.g08_identity_administrator_events ADD CONSTRAINT g08_event_version_fk
 FOREIGN KEY(administrator_id,after_revision,event_id) REFERENCES
 public.g08_identity_administrator_versions(administrator_id,revision,event_id)
 ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE public.g08_identity_administrator_event_approvals (
 event_id uuid NOT NULL REFERENCES public.g08_identity_administrator_events(event_id) ON DELETE RESTRICT,
 approval_id uuid NOT NULL REFERENCES public.g08_identity_administrator_approvals(approval_id) ON DELETE RESTRICT,
 PRIMARY KEY(event_id,approval_id)
);
CREATE TABLE public.g08_administration_receipts (
 event_id uuid PRIMARY KEY, namespace text NOT NULL, scope_key text NOT NULL,
 operation text NOT NULL, idempotency_key public.g08_operation_key NOT NULL,
 actor_auth_uid uuid NOT NULL, fingerprint_version text NOT NULL,
 request_digest public.g08_sha256 NOT NULL,
 canonical_request jsonb NOT NULL CHECK(jsonb_typeof(canonical_request)='object'),
 result jsonb NOT NULL CHECK(jsonb_typeof(result)='object'), occurred_at timestamptz NOT NULL,
 UNIQUE(namespace,scope_key,operation,idempotency_key),
 -- Other namespaces must be added only by their own approved migration.
 CHECK(namespace='identity_admin' AND scope_key='global'),
 CHECK(operation IN ('grant','revise','revoke'))
);
CREATE TABLE public.g08_owner_operation_receipts (
 event_id uuid PRIMARY KEY REFERENCES public.g08_identity_administrator_events(event_id) ON DELETE RESTRICT,
 owner_operation_id uuid NOT NULL UNIQUE, authorization_id uuid NOT NULL,
 operation text NOT NULL, scope_key text NOT NULL CHECK(scope_key='global'),
 idempotency_key public.g08_operation_key NOT NULL,
 operator_person_ref public.g08_evidence_ref NOT NULL,
 operator_authentication_evidence_ref public.g08_evidence_ref NOT NULL,
 operator_authentication_evidence_sha256 public.g08_sha256 NOT NULL,
 verified_operator_auth_uid uuid,
 db_session_user public.g08_evidence_ref NOT NULL, db_effective_role public.g08_evidence_ref NOT NULL,
 procedure_identity public.g08_evidence_ref NOT NULL, procedure_version public.g08_evidence_ref NOT NULL,
 authorization_sha256 public.g08_sha256 NOT NULL, approval_manifest_sha256 public.g08_sha256 NOT NULL,
 policy_version public.g08_evidence_ref NOT NULL, evidence_ref public.g08_evidence_ref NOT NULL,
 -- Integrity projection of the admitted manifest, not an approval policy/validator.
 approval_refs jsonb NOT NULL CHECK(jsonb_typeof(approval_refs)='array' AND jsonb_array_length(approval_refs)>0),
 fingerprint_version text NOT NULL, intent_sha256 public.g08_sha256 NOT NULL,
 request_digest public.g08_sha256 NOT NULL,
 canonical_request jsonb NOT NULL CHECK(jsonb_typeof(canonical_request)='object'),
 result jsonb NOT NULL CHECK(jsonb_typeof(result)='object'), occurred_at timestamptz NOT NULL,
 FOREIGN KEY(authorization_id,owner_operation_id) REFERENCES
 public.g08_owner_operation_authorizations(authorization_id,owner_operation_id) ON DELETE RESTRICT,
 UNIQUE(scope_key,operation,idempotency_key)
);
CREATE INDEX g08_subject_interval_idx ON public.g08_identity_administrators(subject_auth_uid,valid_from);
CREATE INDEX g08_current_validity_idx ON public.g08_identity_administrators(revoked_at,valid_from,valid_to);
CREATE INDEX g08_version_subject_idx ON public.g08_identity_administrator_versions(subject_auth_uid,administrator_id,revision);
CREATE INDEX g08_approval_expiry_idx ON public.g08_identity_administrator_approvals(request_id,expires_at);
CREATE INDEX g08_event_time_idx ON public.g08_identity_administrator_events(administrator_id,occurred_at,event_id);

-- Explicit table inventory; never revoke unrelated existing objects.
DO $security$
DECLARE t text;
BEGIN
 FOREACH t IN ARRAY ARRAY[
 'g08_identity_administrators','g08_identity_administrator_versions',
 'g08_identity_administrator_events','g08_identity_administrator_requests',
 'g08_identity_administrator_approvals','g08_identity_administrator_approval_withdrawals',
 'g08_identity_administrator_event_approvals','g08_administration_receipts',
 'g08_owner_operation_authorizations','g08_owner_operation_approval_links','g08_owner_operation_receipts'] LOOP
  EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',t);
  EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC, anon, authenticated, service_role, nxr_g08_identity_fn_owner',t);
  EXECUTE format('GRANT SELECT ON TABLE public.%I TO nxr_g08_history_check_owner',t);
  EXECUTE format('CREATE POLICY g08_checker_select ON public.%I FOR SELECT TO nxr_g08_history_check_owner USING (true)',t);
 END LOOP;
END
$security$;
-- No runtime membership, no table ownership and no writer grants are installed.
COMMIT;
