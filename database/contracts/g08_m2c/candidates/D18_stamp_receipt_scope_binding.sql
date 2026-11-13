-- UNAPPLIED ADDITIVE CANDIDATE. Synthetic qualification only.
-- Persist the receipt binding timestamp from PostgreSQL, not a caller value.
BEGIN;

DO $stamp_receipt_binding$
DECLARE
    definition text;
    signature regprocedure :=
        'public.g08_gateway_execute_owner_operation(jsonb)'::regprocedure;
BEGIN
    definition := pg_get_functiondef(signature);
    IF position(
        'INSERT INTO public.g08_d10_receipt_scope_bindings SELECT binding.*;'
        IN definition
    ) = 0 OR position('binding.recorded_at := clock_timestamp();' IN definition) <> 0 THEN
        RAISE EXCEPTION 'installed owner gateway differs from the reviewed D18 baseline';
    END IF;
    definition := replace(
        definition,
        '    INSERT INTO public.g08_d10_receipt_scope_bindings SELECT binding.*;',
        '    binding.recorded_at := clock_timestamp();' || E'\n' ||
        '    INSERT INTO public.g08_d10_receipt_scope_bindings SELECT binding.*;'
    );
    IF position('binding.recorded_at := clock_timestamp();' IN definition) = 0 THEN
        RAISE EXCEPTION 'D18 receipt binding timestamp repair did not apply exactly';
    END IF;
    EXECUTE definition;
END
$stamp_receipt_binding$;

COMMIT;
