-- STAGED / UNEXECUTED. Additive correction after the six retained migrations.
-- Match the M2-B coordinator's event-ID evidence envelope at the database layer.
-- No authority semantics, identity provider, RPC grants or prior source edits.
BEGIN;
ALTER TABLE public.g08_owner_execution_evidence
 ADD CONSTRAINT g08_owner_evidence_result_event_check
 CHECK ((result->>'event_id') IS NOT NULL AND result->>'event_id'=event_id::text);
COMMIT;
