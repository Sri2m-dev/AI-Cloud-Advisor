begin;

create or replace function public.tenant_cloud_accounts_classification_evidence(
 requested_organization_id uuid, requested_account_ids jsonb
) returns table (
 account_id text, source_type text, source_reference text, observed_field text,
 observed_value text, occurrence_count bigint, total_count bigint,
 coverage numeric, observed_at timestamptz
) language sql stable security definer set search_path=pg_catalog,public as $$
with requested as materialized (
 select value account_id from jsonb_array_elements_text(requested_account_ids)
), scoped as materialized (
 select f.member_account_id account_id,f.raw_fields,coalesce(f.usage_end_at,f.ingested_at) observed_at
 from public.cloud_cost_fact f join requested r on r.account_id=f.member_account_id
 where f.organization_id=requested_organization_id and f.tenant_id=requested_organization_id
  and f.fact_status in ('active','quarantined')
), totals as (
 select account_id,count(*)::bigint n from scoped group by account_id
), observations as (
 select account_id,'account_alias'::text source_type,
  'line_item_usage_account_name'::text source_reference,'account_name'::text observed_field,
  raw_fields->>'line_item_usage_account_name' observed_value,max(observed_at) observed_at
 from scoped where nullif(btrim(raw_fields->>'line_item_usage_account_name'),'') is not null
 group by account_id,raw_fields->>'line_item_usage_account_name'
 union all
 select s.account_id,'resource_tags','resource_tags/'||tag.key,
  case regexp_replace(lower(tag.key),'[^a-z0-9]','','g')
   when 'businessunit' then 'business_unit' when 'bu' then 'business_unit'
   when 'department' then 'department' when 'costcenter' then 'cost_center'
   when 'environment' then 'environment' when 'env' then 'environment'
   when 'application' then 'application' when 'app' then 'application'
   when 'product' then 'application' when 'userproduct' then 'application'
   when 'businessservice' then 'business_service' when 'owner' then 'owner'
   when 'userowner' then 'owner' when 'technicalowner' then 'technical_owner'
   when 'financeowner' then 'finance_owner' when 'criticality' then 'criticality'
  end,tag.value,max(s.observed_at)
 from scoped s cross join lateral jsonb_each_text(
  coalesce(nullif(s.raw_fields->>'resource_tags','')::jsonb,'{}'::jsonb)
 ) tag
 where regexp_replace(lower(tag.key),'[^a-z0-9]','','g') in (
  'businessunit','bu','department','costcenter','environment','env','application','app',
  'product','userproduct','businessservice','owner','userowner','technicalowner',
  'financeowner','criticality'
 ) group by s.account_id,tag.key,tag.value
), counted as (
 select o.*,count(*)::bigint occurrence_count from observations o join scoped s
  on s.account_id=o.account_id and case when o.source_type='account_alias'
   then s.raw_fields->>'line_item_usage_account_name'=o.observed_value
   else (s.raw_fields->>'resource_tags') like '%'||o.observed_value||'%' end
 group by o.account_id,o.source_type,o.source_reference,o.observed_field,
  o.observed_value,o.observed_at
)
select c.account_id,c.source_type,c.source_reference,c.observed_field,c.observed_value,
 c.occurrence_count,t.n,case when t.n=0 then 0 else c.occurrence_count::numeric/t.n end,
 c.observed_at from counted c join totals t using(account_id)
where public.pvt003c1_can_read_organization(requested_organization_id)
$$;
revoke all on function public.tenant_cloud_accounts_classification_evidence(uuid,jsonb)
 from public,anon;
grant execute on function public.tenant_cloud_accounts_classification_evidence(uuid,jsonb)
 to authenticated,service_role;

commit;
