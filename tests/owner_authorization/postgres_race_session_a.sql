-- UNEXECUTED. Separately authorized disposable fixture only.
-- Custodian pre-provisions a committed ADMITTED authorization and a verified
-- REVOCATION assertion, bound to this actual session principal. No trusted source
-- is supplied here. Set psql variables auth_id, revocation_assertion_id,
-- admission_status_id, revocation_status_id to those fixture UUIDs.
\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL READ COMMITTED;
SELECT public.g08_lock_identity_history();
SELECT public.g08_stage_owner_status(:'auth_id'::uuid,:'revocation_status_id'::uuid,
 'REVOKED',:'admission_status_id'::uuid,:'revocation_assertion_id'::uuid,
 'fixture-revocation','fixture concurrency rationale');
-- Start B now: it must wait on A's global lock, then freshly read REVOKED.
SELECT pg_catalog.pg_sleep(10);
COMMIT;
