begin;

create table if not exists public.classification_policy (
 id uuid primary key default gen_random_uuid(), organization_id uuid not null, tenant_id uuid not null,
 policy_version integer not null, minimum_inference_confidence numeric(7,6) not null default .75,
 minimum_auto_approval_confidence numeric(7,6) not null default .95,
 auto_approval_enabled boolean not null default false,
 allow_provisional_spend_release boolean not null default false,
 allow_allocation_before_approval boolean not null default false,
 source_priority_rules jsonb not null default '{}'::jsonb, conflict_policy text not null default 'REVIEW',
 freshness_days integer not null default 365, effective_from timestamptz not null default now(),
 effective_to timestamptz, approved_by text, approved_at timestamptz, created_at timestamptz not null default now(),
 unique(organization_id,tenant_id,policy_version), check(organization_id=tenant_id),
 check(minimum_inference_confidence between 0 and 1),
 check(minimum_auto_approval_confidence between 0 and 1),
 check(not auto_approval_enabled or (approved_by is not null and approved_at is not null))
);

create table if not exists public.classification_result (
 id uuid primary key, organization_id uuid not null, tenant_id uuid not null,
 entity_type text not null, entity_id text not null, field_name text not null,
 inferred_value text, confidence_score numeric(7,6) not null,
 inference_method text not null, inference_status text not null,
 policy_version integer not null, engine_version text not null, evidence_set_hash text not null,
 source_timestamp timestamptz not null, created_at timestamptz not null default now(),
 valid_from timestamptz not null, valid_to timestamptz, approval_status text not null,
 approved_by text, approved_at timestamptz, correction_reason text, superseded_by uuid,
 version integer not null, candidate_values jsonb not null default '{}'::jsonb,
 conflict boolean not null default false, review_reason text,
 unique(organization_id,tenant_id,entity_type,entity_id,field_name,version),
 unique(organization_id,tenant_id,entity_type,entity_id,field_name,evidence_set_hash,policy_version),
 check(organization_id=tenant_id), check(confidence_score between 0 and 1), check(version > 0),
 check(inference_status in ('NEEDS_REVIEW','RESOLVED_INFERRED','RESOLVED_APPROVED','SUSPENDED','REOPENED','SUPERSEDED')),
 check(approval_status in ('UNAPPROVED','NEEDS_APPROVAL','APPROVED','AUTO_APPROVED')),
 check(approval_status not in ('APPROVED','AUTO_APPROVED') or (approved_by is not null and approved_at is not null))
);

create table if not exists public.classification_evidence_link (
 classification_result_id uuid not null references public.classification_result(id),
 organization_id uuid not null, tenant_id uuid not null, evidence_id text not null,
 evidence_hash text not null, lineage_reference text, provenance_reference text,
 evidence_role text not null default 'supporting', created_at timestamptz not null default now(),
 primary key(classification_result_id,evidence_id), check(organization_id=tenant_id),
 check(evidence_role in ('supporting','contradicting','context'))
);

alter table public.classification_policy enable row level security;
alter table public.classification_result enable row level security;
alter table public.classification_evidence_link enable row level security;

create policy classification_policy_tenant_read on public.classification_policy for select to authenticated
 using (organization_id=tenant_id and public.pvt003c1_can_read_organization(organization_id));
create policy classification_result_tenant_read on public.classification_result for select to authenticated
 using (organization_id=tenant_id and public.pvt003c1_can_read_organization(organization_id));
create policy classification_evidence_tenant_read on public.classification_evidence_link for select to authenticated
 using (organization_id=tenant_id and public.pvt003c1_can_read_organization(organization_id));

revoke insert,update,delete on public.classification_policy from authenticated;
revoke insert,update,delete on public.classification_result from authenticated;
revoke insert,update,delete on public.classification_evidence_link from authenticated;
grant select on public.classification_policy,public.classification_result,public.classification_evidence_link
 to authenticated,service_role;
grant insert,update,delete on public.classification_policy,public.classification_result,public.classification_evidence_link
 to service_role;

comment on table public.classification_evidence_link is
 'Thin immutable references to WP-010 evidence; raw CUR rows are never copied here.';

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
   when 'product' then 'application' when 'businessservice' then 'business_service'
   when 'owner' then 'owner' when 'technicalowner' then 'technical_owner'
   when 'financeowner' then 'finance_owner' when 'criticality' then 'criticality'
  end, tag.value, max(s.observed_at)
 from scoped s cross join lateral jsonb_each_text(
  coalesce(nullif(s.raw_fields->>'resource_tags','')::jsonb,'{}'::jsonb)
 ) tag
 where case regexp_replace(lower(tag.key),'[^a-z0-9]','','g')
   when 'businessunit' then true when 'bu' then true when 'department' then true
   when 'costcenter' then true when 'environment' then true when 'env' then true
   when 'application' then true when 'app' then true when 'product' then true
   when 'businessservice' then true when 'owner' then true when 'technicalowner' then true
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
revoke all on function public.tenant_cloud_account_classification_evidence(uuid,text) from public,anon;
grant execute on function public.tenant_cloud_account_classification_evidence(uuid,text)
 to authenticated,service_role;

commit;
