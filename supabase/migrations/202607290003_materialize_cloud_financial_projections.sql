-- PVT-003C.1: bounded canonical dashboard projections over raw CUR facts.
-- Raw evidence remains in cloud_cost_fact and is not granted to app roles.

begin;

create materialized view if not exists public.tenant_cloud_import_fact_rollup
as
select
    f.organization_id,
    f.tenant_id,
    f.import_id,
    count(*)::bigint as persisted_facts,
    coalesce(sum(f.unblended_cost), 0)::numeric as total_unblended_spend,
    coalesce(sum(f.blended_cost), 0)::numeric as total_blended_spend,
    count(distinct f.member_account_id) filter (
        where f.fact_status = 'quarantined'
    )::bigint as unknown_account_count,
    count(distinct f.member_account_id) filter (
        where f.fact_status = 'active'
    )::bigint as resolved_account_count
from public.cloud_cost_fact f
where f.fact_status in ('active', 'quarantined')
group by f.organization_id, f.tenant_id, f.import_id
with data;

create unique index if not exists tenant_cloud_import_fact_rollup_identity_idx
    on public.tenant_cloud_import_fact_rollup (
        organization_id,
        tenant_id,
        import_id
    );

create materialized view if not exists public.tenant_cloud_account_fact_rollup
as
select
    f.organization_id,
    f.tenant_id,
    f.payer_account_id,
    f.member_account_id as account_id,
    count(*)::bigint as row_count,
    coalesce(sum(f.unblended_cost), 0)::numeric as unblended_spend,
    coalesce(sum(f.blended_cost), 0)::numeric as blended_spend,
    min(f.usage_start_at) as first_usage_at,
    max(f.usage_end_at) as last_usage_at,
    min(f.billing_period_start) as period_start,
    max(f.billing_period_end) as period_end,
    coalesce(max(f.currency_code), 'USD') as currency
from public.cloud_cost_fact f
where f.fact_status in ('active', 'quarantined')
group by
    f.organization_id,
    f.tenant_id,
    f.payer_account_id,
    f.member_account_id
with data;

create unique index if not exists tenant_cloud_account_fact_rollup_identity_idx
    on public.tenant_cloud_account_fact_rollup (
        organization_id,
        tenant_id,
        payer_account_id,
        account_id
    );

create materialized view if not exists public.tenant_cloud_service_fact_rollup
as
select
    f.organization_id,
    f.tenant_id,
    f.service_code,
    f.service_name,
    f.fact_status,
    count(*)::bigint as row_count,
    coalesce(sum(f.unblended_cost), 0)::numeric as unblended_spend,
    coalesce(sum(f.blended_cost), 0)::numeric as blended_spend,
    min(f.billing_period_start) as period_start,
    max(f.billing_period_end) as period_end,
    coalesce(max(f.currency_code), 'USD') as currency
from public.cloud_cost_fact f
where f.fact_status in ('active', 'quarantined')
group by
    f.organization_id,
    f.tenant_id,
    f.service_code,
    f.service_name,
    f.fact_status
with data;

create unique index if not exists tenant_cloud_service_fact_rollup_identity_idx
    on public.tenant_cloud_service_fact_rollup (
        organization_id,
        tenant_id,
        service_code,
        service_name,
        fact_status
    );

revoke all on public.tenant_cloud_import_fact_rollup,
    public.tenant_cloud_account_fact_rollup,
    public.tenant_cloud_service_fact_rollup
from public, anon, authenticated;

grant select on public.tenant_cloud_import_fact_rollup,
    public.tenant_cloud_account_fact_rollup,
    public.tenant_cloud_service_fact_rollup
to service_role;

create or replace function public.refresh_tenant_cloud_financial_projections()
returns void
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    if auth.role() <> 'service_role' then
        raise insufficient_privilege using message = 'service role required';
    end if;
    refresh materialized view public.tenant_cloud_import_fact_rollup;
    refresh materialized view public.tenant_cloud_account_fact_rollup;
    refresh materialized view public.tenant_cloud_service_fact_rollup;
end;
$$;

revoke all on function public.refresh_tenant_cloud_financial_projections()
from public, anon, authenticated;
grant execute on function public.refresh_tenant_cloud_financial_projections()
to service_role;

create or replace function public.tenant_cloud_import_history(
    requested_organization_id uuid
)
returns table (
    import_id uuid,
    provider text,
    source_filename text,
    payer_account_id text,
    status text,
    source_rows bigint,
    persisted_facts bigint,
    total_unblended_spend numeric,
    total_blended_spend numeric,
    reconciliation_variance numeric,
    reconciliation_status text,
    unknown_account_count bigint,
    resolved_account_count bigint,
    started_at timestamptz,
    completed_at timestamptz,
    replay_state text
)
language plpgsql
stable
security definer
set search_path = pg_catalog, public
as $$
begin
    if not public.pvt003c1_can_read_organization(requested_organization_id) then
        raise insufficient_privilege using message = 'organization membership required';
    end if;
    return query
    select
        i.import_id,
        'aws'::text,
        i.source_file_name,
        i.payer_account_id,
        i.status,
        coalesce(i.source_row_count, 0)::bigint,
        coalesce(fr.persisted_facts, i.accepted_row_count, 0)::bigint,
        coalesce(fr.total_unblended_spend, i.normalized_cost_total, 0)::numeric,
        coalesce(fr.total_blended_spend, 0)::numeric,
        coalesce(r.variance_amount, 0)::numeric,
        coalesce(r.status, 'pending'),
        coalesce(fr.unknown_account_count, 0)::bigint,
        coalesce(fr.resolved_account_count, 0)::bigint,
        i.created_at,
        i.completed_at,
        case when i.duplicate_row_count > 0 then 'replayed-idempotently'
             when i.status in ('completed', 'quarantined') then 'terminal'
             else 'not-terminal' end
    from public.cloud_cost_import i
    left join public.tenant_cloud_import_fact_rollup fr
      on fr.organization_id = i.organization_id
     and fr.tenant_id = i.tenant_id
     and fr.import_id = i.import_id
    left join public.cloud_cost_reconciliation r
      on r.organization_id = i.organization_id
     and r.tenant_id = i.tenant_id
     and r.import_id = i.import_id
    where i.organization_id = requested_organization_id
      and i.tenant_id = requested_organization_id
    order by i.created_at desc, i.import_id desc;
end;
$$;

create or replace function public.tenant_cloud_account_posture(
    requested_organization_id uuid,
    requested_period_start date default null,
    requested_period_end date default null
)
returns table (
    payer_account_id text,
    account_id text,
    mapping_status text,
    row_count bigint,
    unblended_spend numeric,
    blended_spend numeric,
    first_usage_at timestamptz,
    last_usage_at timestamptz,
    currency text
)
language plpgsql
stable
security definer
set search_path = pg_catalog, public
as $$
begin
    if not public.pvt003c1_can_read_organization(requested_organization_id) then
        raise insufficient_privilege using message = 'organization membership required';
    end if;
    return query
    select
        a.payer_account_id,
        a.account_id,
        case when exists (
            select 1
            from public.cloud_account_mapping m
            where m.organization_id = a.organization_id
              and m.tenant_id = a.tenant_id
              and m.payer_account_id = a.payer_account_id
              and m.account_id = a.account_id
              and m.status = 'active'
        ) then 'resolved' else 'unknown' end,
        a.row_count,
        a.unblended_spend,
        a.blended_spend,
        a.first_usage_at,
        a.last_usage_at,
        a.currency
    from public.tenant_cloud_account_fact_rollup a
    where a.organization_id = requested_organization_id
      and a.tenant_id = requested_organization_id
      and (requested_period_start is null or a.period_end >= requested_period_start)
      and (requested_period_end is null or a.period_start <= requested_period_end)
    order by a.unblended_spend desc nulls last, a.payer_account_id, a.account_id;
end;
$$;

create or replace function public.tenant_cloud_service_spend(
    requested_organization_id uuid,
    requested_period_start date default null,
    requested_period_end date default null
)
returns table (
    service_code text,
    service_name text,
    fact_status text,
    row_count bigint,
    unblended_spend numeric,
    blended_spend numeric,
    currency text
)
language plpgsql
stable
security definer
set search_path = pg_catalog, public
as $$
begin
    if not public.pvt003c1_can_read_organization(requested_organization_id) then
        raise insufficient_privilege using message = 'organization membership required';
    end if;
    return query
    select
        s.service_code,
        s.service_name,
        s.fact_status,
        s.row_count,
        s.unblended_spend,
        s.blended_spend,
        s.currency
    from public.tenant_cloud_service_fact_rollup s
    where s.organization_id = requested_organization_id
      and s.tenant_id = requested_organization_id
      and (requested_period_start is null or s.period_end >= requested_period_start)
      and (requested_period_end is null or s.period_start <= requested_period_end)
    order by s.unblended_spend desc nulls last, s.service_code, s.fact_status;
end;
$$;

commit;
