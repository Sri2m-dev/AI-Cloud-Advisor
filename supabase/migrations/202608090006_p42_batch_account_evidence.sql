begin;

create or replace function public.tenant_cloud_accounts_classification_evidence(
 requested_organization_id uuid, requested_account_ids jsonb
) returns table (
 account_id text, source_type text, source_reference text, observed_field text,
 observed_value text, occurrence_count bigint, total_count bigint,
 coverage numeric, observed_at timestamptz
) language sql stable security definer set search_path=pg_catalog,public as $$
select account.value,e.source_type,e.source_reference,e.observed_field,e.observed_value,
 e.occurrence_count,e.total_count,e.coverage,e.observed_at
from jsonb_array_elements_text(requested_account_ids) account(value)
cross join lateral public.tenant_cloud_account_classification_evidence(
 requested_organization_id,account.value
) e
where public.pvt003c1_can_read_organization(requested_organization_id)
$$;
revoke all on function public.tenant_cloud_accounts_classification_evidence(uuid,jsonb)
 from public,anon;
grant execute on function public.tenant_cloud_accounts_classification_evidence(uuid,jsonb)
 to authenticated,service_role;

commit;
