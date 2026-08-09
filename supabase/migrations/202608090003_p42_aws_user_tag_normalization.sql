begin;

create or replace function public.tenant_cloud_account_classification_evidence(
 requested_organization_id uuid, requested_account_id text
) returns table (
 source_type text, source_reference text, observed_field text, observed_value text,
 occurrence_count bigint, total_count bigint, coverage numeric, observed_at timestamptz
) language sql stable security definer set search_path=pg_catalog,public as $$
with scoped as materialized (
 select raw_fields, coalesce(usage_end_at,ingested_at) observed_at
 from public.cloud_cost_fact
 where organization_id=requested_organization_id and tenant_id=requested_organization_id
  and member_account_id=requested_account_id and fact_status in ('active','quarantined')
), total as (select count(*)::bigint n from scoped), observations as (
 select 'account_alias'::text source_type, 'line_item_usage_account_name'::text source_reference,
  'account_name'::text observed_field, raw_fields->>'line_item_usage_account_name' observed_value,
  max(observed_at) observed_at from scoped
 where nullif(btrim(raw_fields->>'line_item_usage_account_name'),'') is not null
 group by raw_fields->>'line_item_usage_account_name'
 union all
 select 'resource_tags', 'resource_tags/'||tag.key,
  case regexp_replace(lower(tag.key),'[^a-z0-9]','','g')
   when 'businessunit' then 'business_unit' when 'bu' then 'business_unit'
   when 'department' then 'department' when 'costcenter' then 'cost_center'
   when 'environment' then 'environment' when 'env' then 'environment'
   when 'application' then 'application' when 'app' then 'application'
   when 'product' then 'application' when 'userproduct' then 'application' when 'businessservice' then 'business_service'
   when 'owner' then 'owner' when 'userowner' then 'owner' when 'technicalowner' then 'technical_owner'
   when 'financeowner' then 'finance_owner' when 'criticality' then 'criticality'
  end, tag.value, max(s.observed_at)
 from scoped s cross join lateral jsonb_each_text(
  coalesce(nullif(s.raw_fields->>'resource_tags','')::jsonb,'{}'::jsonb)
 ) tag
 where case regexp_replace(lower(tag.key),'[^a-z0-9]','','g')
   when 'businessunit' then true when 'bu' then true when 'department' then true
   when 'costcenter' then true when 'environment' then true when 'env' then true
   when 'application' then true when 'app' then true when 'product' then true when 'userproduct' then true
   when 'businessservice' then true when 'owner' then true when 'userowner' then true when 'technicalowner' then true
   when 'financeowner' then true when 'criticality' then true else false end
 group by tag.key,tag.value
), counted as (
 select o.*,count(*)::bigint occurrence_count from observations o
 join scoped s on case when o.source_type='account_alias'
  then s.raw_fields->>'line_item_usage_account_name'=o.observed_value
  else (s.raw_fields->>'resource_tags') like '%'||o.observed_value||'%' end
 group by o.source_type,o.source_reference,o.observed_field,o.observed_value,o.observed_at
)
select c.source_type,c.source_reference,c.observed_field,c.observed_value,c.occurrence_count,t.n,
 case when t.n=0 then 0 else c.occurrence_count::numeric/t.n end,c.observed_at
from counted c cross join total t
where public.pvt003c1_can_read_organization(requested_organization_id)
$$;

commit;
