-- Superseded security script.
--
-- The former implementation created broad FOR ALL policies and trusted
-- tenant_id/org_id JWT claims directly. That does not match the hardened DEV
-- identity chain and must not be applied.
--
-- Use the reviewed migration instead:
-- supabase/migrations/202607230001_public_security_reconciliation.sql

do $$
begin
    raise exception
        'tenant_rls_policies.sql is superseded; use the public security reconciliation migration';
end
$$;
