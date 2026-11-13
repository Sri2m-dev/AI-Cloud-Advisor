-- STAGED / UNEXECUTED. After all three M2-A files, under continuous quiescence.
-- Additive to M2-A; no runtime activation, inferred identity, or history backfill.
BEGIN;
CREATE ROLE nxr_g08_owner_history_check_owner NOLOGIN NOSUPERUSER NOBYPASSRLS
 NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
CREATE ROLE nxr_g08_owner_fn_owner NOLOGIN NOSUPERUSER NOBYPASSRLS
 NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
CREATE ROLE nxr_g08_owner_reader_owner NOLOGIN NOSUPERUSER NOBYPASSRLS
 NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
GRANT USAGE ON SCHEMA public TO nxr_g08_owner_history_check_owner,nxr_g08_owner_fn_owner,nxr_g08_owner_reader_owner;
REVOKE CREATE ON SCHEMA public FROM nxr_g08_owner_history_check_owner,nxr_g08_owner_fn_owner,nxr_g08_owner_reader_owner;

-- A stored assertion is audit evidence, never an authentication source. Admission
-- requires the unresolved independently authenticated verifier, not caller JSON.
CREATE TABLE public.g08_owner_operator_assertions (
 assertion_id uuid PRIMARY KEY, authorization_id uuid NOT NULL, owner_operation_id uuid NOT NULL,
 purpose text NOT NULL CHECK(purpose IN ('ADMISSION','REVOCATION','INVALIDATION','EXECUTION','RECONCILIATION')),
 person_ref public.g08_evidence_ref NOT NULL,
 authentication_evidence_ref public.g08_evidence_ref NOT NULL,
 authentication_evidence_sha256 public.g08_sha256 NOT NULL,
 session_binding_ref public.g08_evidence_ref NOT NULL,
 db_session_user public.g08_evidence_ref NOT NULL, verified_auth_uid uuid,
 verifier_ref public.g08_evidence_ref NOT NULL,
 verified_at timestamptz NOT NULL, valid_until timestamptz NOT NULL,
 CHECK(valid_until>verified_at),
 FOREIGN KEY(authorization_id,owner_operation_id) REFERENCES
 public.g08_owner_operation_authorizations(authorization_id,owner_operation_id) ON DELETE RESTRICT,
 UNIQUE(assertion_id,authorization_id,owner_operation_id)
);
CREATE TABLE public.g08_owner_authorization_status_history (
 status_id uuid PRIMARY KEY, authorization_id uuid NOT NULL, owner_operation_id uuid NOT NULL,
 revision bigint NOT NULL CHECK(revision>0), predecessor_status_id uuid, predecessor_revision bigint,
 status text NOT NULL CHECK(status IN ('ADMITTED','REVOKED','INVALIDATED')),
 assertion_id uuid NOT NULL, occurred_at timestamptz NOT NULL,
 db_session_user public.g08_evidence_ref NOT NULL, db_effective_role public.g08_evidence_ref NOT NULL,
 evidence_ref public.g08_evidence_ref NOT NULL, rationale public.g08_rationale NOT NULL,
 approval_manifest jsonb NOT NULL CHECK(jsonb_typeof(approval_manifest)='array' AND jsonb_array_length(approval_manifest)>0),
 UNIQUE(authorization_id,revision), UNIQUE(authorization_id,owner_operation_id,revision,status_id),
 FOREIGN KEY(authorization_id,owner_operation_id) REFERENCES
 public.g08_owner_operation_authorizations(authorization_id,owner_operation_id) ON DELETE RESTRICT,
 FOREIGN KEY(assertion_id,authorization_id,owner_operation_id) REFERENCES
 public.g08_owner_operator_assertions(assertion_id,authorization_id,owner_operation_id) ON DELETE RESTRICT,
 FOREIGN KEY(authorization_id,owner_operation_id,predecessor_revision,predecessor_status_id) REFERENCES
 public.g08_owner_authorization_status_history(authorization_id,owner_operation_id,revision,status_id) ON DELETE RESTRICT,
 CHECK((revision=1 AND status='ADMITTED' AND predecessor_status_id IS NULL AND predecessor_revision IS NULL)
  OR (revision>1 AND status IN ('REVOKED','INVALIDATED') AND predecessor_status_id IS NOT NULL
   AND predecessor_revision IS NOT NULL AND predecessor_revision=revision-1))
);
CREATE TABLE public.g08_owner_execution_evidence (
 evidence_id uuid PRIMARY KEY, authorization_id uuid NOT NULL, owner_operation_id uuid NOT NULL,
 event_id uuid NOT NULL UNIQUE REFERENCES public.g08_identity_administrator_events(event_id)
 ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
 admitted_revision bigint NOT NULL CHECK(admitted_revision=1), admitted_status_id uuid NOT NULL,
 assertion_id uuid NOT NULL, decision_time timestamptz NOT NULL,
 request_digest public.g08_sha256 NOT NULL,
 result jsonb NOT NULL CHECK(jsonb_typeof(result)='object'),
 technical_evidence_ref public.g08_evidence_ref NOT NULL, technical_evidence_sha256 public.g08_sha256 NOT NULL,
 technical_verifier_ref public.g08_evidence_ref NOT NULL,
 authority_evidence_ref public.g08_evidence_ref NOT NULL,
 fencing_evidence_ref public.g08_evidence_ref NOT NULL,
 FOREIGN KEY(authorization_id,owner_operation_id,admitted_revision,admitted_status_id) REFERENCES
 public.g08_owner_authorization_status_history(authorization_id,owner_operation_id,revision,status_id) ON DELETE RESTRICT,
 FOREIGN KEY(assertion_id,authorization_id,owner_operation_id) REFERENCES
 public.g08_owner_operator_assertions(assertion_id,authorization_id,owner_operation_id) ON DELETE RESTRICT,
 UNIQUE(evidence_id,authorization_id,owner_operation_id,event_id)
);
CREATE TABLE public.g08_owner_operation_consumptions (
 owner_operation_id uuid PRIMARY KEY, authorization_id uuid NOT NULL UNIQUE,
 event_id uuid NOT NULL UNIQUE REFERENCES public.g08_identity_administrator_events(event_id) ON DELETE RESTRICT,
 evidence_id uuid NOT NULL UNIQUE,
 consumed_at timestamptz NOT NULL,
 FOREIGN KEY(authorization_id,owner_operation_id) REFERENCES
 public.g08_owner_operation_authorizations(authorization_id,owner_operation_id) ON DELETE RESTRICT,
 FOREIGN KEY(evidence_id,authorization_id,owner_operation_id,event_id) REFERENCES
 public.g08_owner_execution_evidence(evidence_id,authorization_id,owner_operation_id,event_id)
 ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
 UNIQUE(evidence_id,authorization_id,owner_operation_id,event_id)
);
ALTER TABLE public.g08_owner_execution_evidence ADD CONSTRAINT g08_owner_evidence_consumption_fk
 FOREIGN KEY(evidence_id,authorization_id,owner_operation_id,event_id) REFERENCES
 public.g08_owner_operation_consumptions(evidence_id,authorization_id,owner_operation_id,event_id)
 ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

DO $security$
DECLARE t text;
BEGIN
 FOREACH t IN ARRAY ARRAY['g08_owner_operator_assertions','g08_owner_authorization_status_history',
 'g08_owner_execution_evidence','g08_owner_operation_consumptions'] LOOP
  EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',t);
  EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC,anon,authenticated,service_role,nxr_g08_identity_fn_owner,nxr_g08_owner_fn_owner,nxr_g08_owner_reader_owner',t);
 END LOOP;
 FOREACH t IN ARRAY ARRAY['g08_owner_operator_assertions','g08_owner_authorization_status_history',
 'g08_owner_execution_evidence','g08_owner_operation_consumptions','g08_owner_operation_authorizations',
 'g08_owner_operation_approval_links','g08_owner_operation_receipts','g08_identity_administrator_events'] LOOP
  EXECUTE format('GRANT SELECT ON public.%I TO nxr_g08_owner_history_check_owner',t);
  EXECUTE format('CREATE POLICY g08_owner_checker_select ON public.%I FOR SELECT TO nxr_g08_owner_history_check_owner USING(true)',t);
 END LOOP;
END $security$;
CREATE INDEX g08_owner_status_time_idx ON public.g08_owner_authorization_status_history(authorization_id,occurred_at,revision);
-- No business owner can mint assertions/status/evidence or consume operations.
COMMIT;
