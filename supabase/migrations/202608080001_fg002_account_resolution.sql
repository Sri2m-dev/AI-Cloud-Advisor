begin;

alter table public.cloud_account_registry add column if not exists alias text;
alter table public.cloud_account_registry add column if not exists project_code text;
alter table public.cloud_account_registry add column if not exists criticality text;
alter table public.cloud_account_registry add column if not exists resolution_status text not null default 'DISCOVERED';
alter table public.cloud_account_registry add column if not exists resolution_reason text;
alter table public.cloud_account_registry add column if not exists effective_date date;
alter table public.cloud_account_registry add column if not exists version integer not null default 1;
alter table public.cloud_account_registry add column if not exists source_evidence jsonb not null default '{}'::jsonb;

create table if not exists public.cloud_account_registry_version (
 id uuid primary key default gen_random_uuid(), registry_id uuid not null references public.cloud_account_registry(id),
 organization_id uuid not null, tenant_id uuid not null, version integer not null,
 previous_state text, new_state text not null, previous_values jsonb not null default '{}'::jsonb,
 new_values jsonb not null, actor_id text not null, actor_email text not null, actor_role text not null,
 reason text not null, approval_identity text, source_import_id text,
 financial_before jsonb not null, financial_after jsonb not null, created_at timestamptz not null default now(),
 unique(registry_id,version), check(organization_id=tenant_id)
);
create table if not exists public.cloud_account_resolution_bulk_audit (
 id uuid primary key default gen_random_uuid(), organization_id uuid not null, tenant_id uuid not null,
 actor_id text not null, actor_email text not null, reason text not null, account_count integer not null,
 requested_changes jsonb not null, results jsonb not null, created_at timestamptz not null default now(),
 check(organization_id=tenant_id)
);
alter table public.cloud_account_registry_version enable row level security;
create policy cloud_account_registry_version_read on public.cloud_account_registry_version for select to authenticated
 using (public.pvt003c1_can_read_organization(organization_id) and organization_id=tenant_id);
revoke insert,update,delete on public.cloud_account_registry_version from authenticated;
grant select on public.cloud_account_registry_version to authenticated,service_role;
alter table public.cloud_account_resolution_bulk_audit enable row level security;
create policy cloud_account_resolution_bulk_read on public.cloud_account_resolution_bulk_audit for select to authenticated
 using (public.pvt003c1_can_read_organization(organization_id) and organization_id=tenant_id);
revoke insert,update,delete on public.cloud_account_resolution_bulk_audit from authenticated;
grant select on public.cloud_account_resolution_bulk_audit to authenticated,service_role;

alter function public.tenant_cloud_financial_posture(uuid,date,date)
 rename to tenant_cloud_financial_posture_fg001_base;

create function public.tenant_cloud_financial_posture(
 requested_organization_id uuid, requested_period_start date default null, requested_period_end date default null
) returns table (
 organization_id uuid,currency text,period_start date,period_end date,generated_at timestamptz,
 import_count bigint,latest_import_id uuid,latest_import_status text,source_rows bigint,persisted_facts bigint,
 total_ingested_spend numeric,cloud_spend numeric,resolved_spend numeric,quarantined_spend numeric,
 allocated_spend numeric,unallocated_resolved_spend numeric,reconciled_spend numeric,unreconciled_spend numeric,
 resolved_account_count bigint,unknown_account_count bigint,foreign_account_count bigint,ambiguous_account_count bigint,
 allocation_coverage_percentage numeric,reconciliation_status text,reconciliation_variance numeric,warnings text[]
) language sql stable security definer set search_path=pg_catalog,public as $$
with base as materialized (
 select * from public.tenant_cloud_financial_posture_fg001_base(
   requested_organization_id,requested_period_start,requested_period_end)
), account_posture as (
 select
  coalesce(sum(a.unblended_spend) filter(where exists(
   select 1 from public.cloud_account_mapping m where m.organization_id=a.organization_id
    and m.tenant_id=a.tenant_id and m.provider='aws' and m.payer_account_id=a.payer_account_id
    and m.account_id=a.account_id and m.status='active'
  )),0)::numeric resolved,
  count(*) filter(where exists(
   select 1 from public.cloud_account_mapping m where m.organization_id=a.organization_id
    and m.tenant_id=a.tenant_id and m.provider='aws' and m.payer_account_id=a.payer_account_id
    and m.account_id=a.account_id and m.status='active'
  ))::bigint resolved_accounts,
  count(*) filter(where not exists(
   select 1 from public.cloud_account_mapping m where m.organization_id=a.organization_id
    and m.tenant_id=a.tenant_id and m.provider='aws' and m.payer_account_id=a.payer_account_id
    and m.account_id=a.account_id and m.status='active'
  ))::bigint unknown_accounts
 from public.tenant_cloud_account_fact_rollup a where a.organization_id=requested_organization_id
  and a.tenant_id=requested_organization_id
  and (requested_period_start is null or a.period_end>=requested_period_start)
  and (requested_period_end is null or a.period_start<=requested_period_end)
)
select b.organization_id,b.currency,b.period_start,b.period_end,statement_timestamp(),b.import_count,
 b.latest_import_id,b.latest_import_status,b.source_rows,b.persisted_facts,b.total_ingested_spend,b.cloud_spend,
 least(ap.resolved,b.total_ingested_spend),b.total_ingested_spend-least(ap.resolved,b.total_ingested_spend),
 0::numeric,least(ap.resolved,b.total_ingested_spend),b.reconciled_spend,b.unreconciled_spend,
 ap.resolved_accounts,ap.unknown_accounts,b.foreign_account_count,b.ambiguous_account_count,0::numeric,
 b.reconciliation_status,b.reconciliation_variance,
 case when b.total_ingested_spend-least(ap.resolved,b.total_ingested_spend)>0
  then array['Cloud cost data is reconciled; unresolved account ownership remains quarantined.']::text[]
  else array[]::text[] end
from base b cross join account_posture ap
$$;
revoke all on function public.tenant_cloud_financial_posture_fg001_base(uuid,date,date) from public,anon;
grant execute on function public.tenant_cloud_financial_posture_fg001_base(uuid,date,date) to service_role;
revoke all on function public.tenant_cloud_financial_posture(uuid,date,date) from public,anon;
grant execute on function public.tenant_cloud_financial_posture(uuid,date,date) to authenticated,service_role;

create or replace function public.fg002_resolve_cloud_account(
 requested_organization_id uuid, requested_payer_account_id text, requested_account_id text,
 requested_mapping jsonb, requested_reason text, requested_confirmed boolean,
 requested_expected_state text default 'DISCOVERED'
) returns jsonb language plpgsql security definer set search_path=pg_catalog,public as $$
declare
 actor_email text := lower(coalesce(auth.jwt()->>'email','service-role'));
 actor_id text := coalesce(auth.uid()::text,actor_email);
 actor_role text;
 existing_registry public.cloud_account_registry%rowtype;
 registry_row public.cloud_account_registry%rowtype;
 before_posture jsonb; after_posture jsonb; evidence jsonb; next_version integer;
 complete boolean; target_state text; effective_on date;
begin
 if not requested_confirmed then raise exception 'explicit confirmation required' using errcode='22023'; end if;
 if nullif(btrim(requested_reason),'') is null then raise exception 'resolution reason required' using errcode='22023'; end if;
 if not public.pvt003c1_can_read_organization(requested_organization_id) then
   raise insufficient_privilege using message='organization membership required';
 end if;
 select lower(coalesce(u.role,'')) into actor_role from public.users u where lower(u.email)=actor_email limit 1;
 if coalesce(actor_role,'') not in ('super_admin','global_admin','client_admin','organization_admin','finance','operations')
 then raise insufficient_privilege using message='account resolution permission required'; end if;
 if requested_account_id is null or requested_payer_account_id is null then raise exception 'discovered identity required'; end if;

 perform pg_advisory_xact_lock(hashtextextended(requested_organization_id::text||':'||requested_payer_account_id||':'||requested_account_id,0));
 perform 1 from public.tenant_cloud_account_fact_rollup a
  where a.organization_id=requested_organization_id and a.tenant_id=requested_organization_id
    and a.payer_account_id=requested_payer_account_id and a.account_id=requested_account_id;
 if not found then raise exception 'unresolved discovered account not found'; end if;
 if requested_expected_state='DISCOVERED' and exists(select 1 from public.cloud_account_mapping m where m.organization_id=requested_organization_id
   and m.tenant_id=requested_organization_id and m.payer_account_id=requested_payer_account_id
   and m.account_id=requested_account_id and m.status='active') then raise exception 'account is already resolved'; end if;

 select to_jsonb(p) into before_posture from public.tenant_cloud_financial_posture(requested_organization_id,null,null) p;
 select * into existing_registry from public.cloud_account_registry r where r.organization_id=requested_organization_id
   and r.tenant_id=requested_organization_id and r.provider='aws' and r.account_id=requested_account_id for update;
 if found and existing_registry.resolution_status <> requested_expected_state then raise exception 'stale account resolution state'; end if;
 effective_on := coalesce(nullif(requested_mapping->>'effective_date','')::date,current_date);
 select greatest(effective_on,coalesce(max(m.effective_from)+1,effective_on)) into effective_on
 from public.cloud_account_mapping m where m.organization_id=requested_organization_id
  and m.tenant_id=requested_organization_id and m.provider='aws'
  and m.payer_account_id=requested_payer_account_id and m.account_id=requested_account_id;
 complete := nullif(btrim(requested_mapping->>'owner'),'') is not null
   and (nullif(btrim(requested_mapping->>'business_unit'),'') is not null or nullif(btrim(requested_mapping->>'department'),'') is not null)
   and nullif(btrim(requested_mapping->>'cost_center'),'') is not null
   and nullif(btrim(requested_mapping->>'environment'),'') is not null
   and upper(coalesce(requested_mapping->>'resolution_status','')) in ('APPROVED','ACTIVE');
 target_state := case when complete then 'ACTIVE'
   when upper(coalesce(requested_mapping->>'resolution_status','')) in ('REJECTED','SUSPENDED') then upper(requested_mapping->>'resolution_status')
   when upper(coalesce(requested_mapping->>'resolution_status',''))='READY_FOR_APPROVAL' then 'READY_FOR_APPROVAL'
   when nullif(btrim(requested_mapping->>'owner'),'') is null then 'PENDING_REVIEW'
   else 'PARTIALLY_MAPPED' end;
 evidence := jsonb_build_object('original_provider','aws','provider_account_id',requested_account_id,
   'payer_account_id',requested_payer_account_id,'source_import_id',requested_mapping->>'source_import_id',
   'first_seen_at',requested_mapping->>'first_seen_at','last_seen_at',requested_mapping->>'last_seen_at',
   'billing_period',requested_mapping->>'billing_period','quarantined_spend',requested_mapping->>'quarantined_spend',
   'currency',requested_mapping->>'currency','source_state','DISCOVERED');
 next_version := coalesce(existing_registry.version,0)+1;

 insert into public.cloud_account_registry(organization_id,tenant_id,provider,account_id,account_name,alias,environment,
   business_unit,department,application,business_service,owner,technical_owner,finance_owner,cost_center,project,
   criticality,status,resolution_status,resolution_reason,effective_date,version,source_evidence)
 values(requested_organization_id,requested_organization_id,'aws',requested_account_id,
   coalesce(requested_mapping->>'account_name',requested_account_id),requested_mapping->>'alias',requested_mapping->>'environment',
   requested_mapping->>'business_unit',requested_mapping->>'department',requested_mapping->>'application',requested_mapping->>'business_service',
   requested_mapping->>'owner',requested_mapping->>'technical_owner',requested_mapping->>'finance_owner',requested_mapping->>'cost_center',
   requested_mapping->>'project_code',requested_mapping->>'criticality',lower(target_state),target_state,requested_reason,effective_on,next_version,evidence)
 on conflict(organization_id,tenant_id,provider,account_id) do update set
   account_name=excluded.account_name,alias=excluded.alias,environment=excluded.environment,business_unit=excluded.business_unit,
   department=excluded.department,application=excluded.application,business_service=excluded.business_service,owner=excluded.owner,
   technical_owner=excluded.technical_owner,finance_owner=excluded.finance_owner,cost_center=excluded.cost_center,project=excluded.project,
   criticality=excluded.criticality,status=excluded.status,resolution_status=excluded.resolution_status,
   resolution_reason=excluded.resolution_reason,effective_date=excluded.effective_date,version=excluded.version,
   source_evidence=public.cloud_account_registry.source_evidence,updated_at=now()
 returning * into registry_row;

 update public.cloud_account_mapping set effective_to=effective_on-1,status='inactive',updated_at=now()
  where organization_id=requested_organization_id and tenant_id=requested_organization_id and provider='aws'
    and payer_account_id=requested_payer_account_id and account_id=requested_account_id and effective_to is null;
 insert into public.cloud_account_mapping(cloud_account_mapping_id,organization_id,tenant_id,provider,payer_account_id,
   account_id,account_kind,status,display_name,effective_from,mapping_source)
 values(gen_random_uuid(),requested_organization_id,requested_organization_id,'aws',requested_payer_account_id,
   requested_account_id,case when requested_payer_account_id=requested_account_id then 'payer' else 'member' end,
   case when complete then 'active' else 'quarantined' end,registry_row.account_name,effective_on,'fg002_governed_resolution');
 select to_jsonb(p) into after_posture from public.tenant_cloud_financial_posture(requested_organization_id,null,null) p;
 if (before_posture->>'total_ingested_spend')::numeric <> (after_posture->>'total_ingested_spend')::numeric
   or coalesce((after_posture->>'reconciliation_variance')::numeric,0) <> 0 then raise exception 'financial reconciliation invariant failed'; end if;
 insert into public.cloud_account_registry_audit(registry_id,organization_id,tenant_id,actor_id,actor_email,action,old_value,new_value,reason)
 values(registry_row.id,requested_organization_id,requested_organization_id,actor_id,actor_email,'resolve',to_jsonb(existing_registry),to_jsonb(registry_row),requested_reason);
 insert into public.cloud_account_registry_version(registry_id,organization_id,tenant_id,version,previous_state,new_state,
   previous_values,new_values,actor_id,actor_email,actor_role,reason,approval_identity,source_import_id,financial_before,financial_after)
 values(registry_row.id,requested_organization_id,requested_organization_id,next_version,existing_registry.resolution_status,target_state,
   coalesce(to_jsonb(existing_registry),'{}'),to_jsonb(registry_row),actor_id,actor_email,actor_role,requested_reason,
   case when complete then actor_email end,requested_mapping->>'source_import_id',before_posture,after_posture);
 return jsonb_build_object('registry',to_jsonb(registry_row),'financial_before',before_posture,'financial_after',after_posture,
   'allocation_ready',complete,'version',next_version);
end $$;
revoke all on function public.fg002_resolve_cloud_account(uuid,text,text,jsonb,text,boolean,text) from public,anon;
grant execute on function public.fg002_resolve_cloud_account(uuid,text,text,jsonb,text,boolean,text) to authenticated,service_role;

create or replace function public.fg002_bulk_resolve_cloud_accounts(
 requested_organization_id uuid, requested_accounts jsonb, requested_mapping jsonb,
 requested_reason text, requested_confirmed boolean
) returns jsonb language plpgsql security definer set search_path=pg_catalog,public as $$
declare item jsonb; result jsonb; results jsonb := '[]'::jsonb; actor_email text := lower(coalesce(auth.jwt()->>'email','service-role'));
begin
 if not requested_confirmed then raise exception 'explicit bulk confirmation required' using errcode='22023'; end if;
 if nullif(btrim(requested_reason),'') is null then raise exception 'bulk resolution reason required' using errcode='22023'; end if;
 if jsonb_typeof(requested_accounts)<>'array' or jsonb_array_length(requested_accounts)=0 then raise exception 'bulk accounts required'; end if;
 for item in select value from jsonb_array_elements(requested_accounts) loop
   result := public.fg002_resolve_cloud_account(requested_organization_id,item->>'payer_account_id',item->>'account_id',
     requested_mapping || item,requested_reason,true,coalesce(item->>'expected_state','DISCOVERED'));
   results := results || jsonb_build_array(result);
 end loop;
 insert into public.cloud_account_resolution_bulk_audit(organization_id,tenant_id,actor_id,actor_email,reason,account_count,requested_changes,results)
 values(requested_organization_id,requested_organization_id,coalesce(auth.uid()::text,actor_email),actor_email,requested_reason,
   jsonb_array_length(requested_accounts),requested_mapping,results);
 return jsonb_build_object('count',jsonb_array_length(results),'results',results);
end $$;
revoke all on function public.fg002_bulk_resolve_cloud_accounts(uuid,jsonb,jsonb,text,boolean) from public,anon;
grant execute on function public.fg002_bulk_resolve_cloud_accounts(uuid,jsonb,jsonb,text,boolean) to authenticated,service_role;
commit;
