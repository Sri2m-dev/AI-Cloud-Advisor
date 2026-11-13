-- UNAPPLIED ADDITIVE CANDIDATE. Synthetic qualification only.
-- Grant only the canonical helper and subject-ID lookup required by the gateway owner.
BEGIN;

REVOKE SELECT ON TABLE auth.users FROM nxr_g08_owner_fn_owner;
GRANT USAGE ON SCHEMA auth TO nxr_g08_owner_fn_owner;
GRANT SELECT (id) ON TABLE auth.users TO nxr_g08_owner_fn_owner;
GRANT EXECUTE ON FUNCTION public.g08_owner_decision_time(uuid, uuid)
    TO nxr_g08_owner_fn_owner;

COMMIT;
