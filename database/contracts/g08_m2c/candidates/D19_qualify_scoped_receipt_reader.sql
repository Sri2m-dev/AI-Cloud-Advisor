-- UNAPPLIED ADDITIVE CANDIDATE. Synthetic qualification only.
-- Disambiguate the policy-class column from the reader's PL/pgSQL variable.
BEGIN;

DO $qualify_receipt_reader$
DECLARE
    definition text;
    signature regprocedure :=
        'public.g08_gateway_read_owner_receipt(uuid,uuid,uuid,uuid,text,uuid)'::regprocedure;
BEGIN
    definition := pg_get_functiondef(signature);
    IF position(
        'SELECT claims, authority_class INTO policy_claims, authority_class'
        IN definition
    ) = 0 THEN
        RAISE EXCEPTION 'installed receipt reader differs from the reviewed D19 baseline';
    END IF;
    definition := replace(
        definition,
        'SELECT claims, authority_class INTO policy_claims, authority_class',
        'SELECT public.g08_d10_policy_versions.claims, ' ||
        'public.g08_d10_policy_versions.authority_class ' ||
        'INTO policy_claims, authority_class'
    );
    EXECUTE definition;
END
$qualify_receipt_reader$;

COMMIT;
