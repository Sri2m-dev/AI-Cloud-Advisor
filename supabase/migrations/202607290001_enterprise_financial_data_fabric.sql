-- PVT-003C.1: tenant-guarded, database-side canonical CUR aggregations.
-- Additive only: no fact, import, reconciliation, mapping, or RLS semantics change.

begin;

create or replace function public.pvt003c1_can_read_organization(requested_organization_id uuid)
returns boolean
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
    select
        requested_organization_id is not null
        and (
            auth.role() = 'service_role'
            or exists (
                select 1
                from public.users u
                where lower(u.email) = lower(auth.jwt() ->> 'email')
                  and u.org_id = requested_organization_id
            )
        );
$$;

revoke all on function public.pvt003c1_can_read_organization(uuid) from public, anon;
grant execute on function public.pvt003c1_can_read_organization(uuid) to authenticated, service_role;

create or replace function public.tenant_cloud_financial_posture(
    requested_organization_id uuid,
    requested_period_start date default null,
    requested_period_end date default null
)
returns table (
    organization_id uuid,
    currency text,
    period_start date,
    period_end date,
    generated_at timestamptz,
    import_count bigint,
    latest_import_id uuid,
    latest_import_status text,
    source_rows bigint,
    persisted_facts bigint,
    total_ingested_spend numeric,
    cloud_spend numeric,
    resolved_spend numeric,
    quarantined_spend numeric,
    allocated_spend numeric,
    unallocated_resolved_spend numeric,
    reconciled_spend numeric,
    unreconciled_spend numeric,
    resolved_account_count bigint,
    unknown_account_count bigint,
    foreign_account_count bigint,
    ambiguous_account_count bigint,
    allocation_coverage_percentage numeric,
    reconciliation_status text,
    reconciliation_variance numeric,
    warnings text[]
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
    with scoped_facts as (
        select f.*
        from public.cloud_cost_fact f
        where f.organization_id = requested_organization_id
          and f.tenant_id = requested_organization_id
          and f.fact_status in ('active', 'quarantined')
          and (requested_period_start is null or f.billing_period_end >= requested_period_start)
          and (requested_period_end is null or f.billing_period_start <= requested_period_end)
    ),
    fact_rollup as (
        select
            count(*)::bigint facts,
            min(billing_period_start) min_period,
            max(billing_period_end) max_period,
            coalesce(sum(unblended_cost), 0)::numeric total_spend,
            coalesce(sum(unblended_cost) filter (where fact_status = 'active'), 0)::numeric resolved,
            coalesce(sum(unblended_cost) filter (where fact_status = 'quarantined'), 0)::numeric quarantined,
            coalesce(max(currency_code), 'USD') currency_code
        from scoped_facts
    ),
    scoped_imports as (
        select i.*
        from public.cloud_cost_import i
        where i.organization_id = requested_organization_id
          and i.tenant_id = requested_organization_id
          and (requested_period_start is null or i.billing_period_end >= requested_period_start)
          and (requested_period_end is null or i.billing_period_start <= requested_period_end)
    ),
    import_rollup as (
        select count(*)::bigint imports, coalesce(sum(source_row_count), 0)::bigint rows
        from scoped_imports
    ),
    latest_import as (
        select i.import_id, i.status
        from scoped_imports i
        order by i.created_at desc, i.import_id desc
        limit 1
    ),
    latest_reconciliation as (
        select r.status, coalesce(r.variance_amount, 0)::numeric variance
        from public.cloud_cost_reconciliation r
        join latest_import i on i.import_id = r.import_id
        where r.organization_id = requested_organization_id
          and r.tenant_id = requested_organization_id
        order by r.created_at desc, r.cloud_cost_reconciliation_id desc
        limit 1
    ),
    account_rollup as (
        select
            count(distinct f.member_account_id) filter (
                where exists (
                    select 1 from public.cloud_account_mapping m
                    where m.organization_id = f.organization_id
                      and m.tenant_id = f.tenant_id
                      and m.payer_account_id = f.payer_account_id
                      and m.account_id = f.member_account_id
                      and m.status = 'active'
                )
            )::bigint resolved_accounts,
            count(distinct f.member_account_id) filter (
                where not exists (
                    select 1 from public.cloud_account_mapping m
                    where m.organization_id = f.organization_id
                      and m.tenant_id = f.tenant_id
                      and m.payer_account_id = f.payer_account_id
                      and m.account_id = f.member_account_id
                      and m.status = 'active'
                )
            )::bigint unknown_accounts
        from scoped_facts f
    )
    select
        requested_organization_id,
        fr.currency_code,
        fr.min_period,
        fr.max_period,
        statement_timestamp(),
        ir.imports,
        li.import_id,
        li.status,
        ir.rows,
        fr.facts,
        fr.total_spend,
        fr.total_spend,
        fr.resolved,
        fr.quarantined,
        0::numeric,
        fr.resolved,
        case when coalesce(lr.variance, 0) = 0
                  and coalesce(lr.status, '') in ('reconciled', 'quarantined')
             then fr.total_spend else 0::numeric end,
        case when coalesce(lr.variance, 0) = 0
                  and coalesce(lr.status, '') in ('reconciled', 'quarantined')
             then 0::numeric else fr.total_spend end,
        coalesce(ar.resolved_accounts, 0),
        coalesce(ar.unknown_accounts, 0),
        0::bigint,
        0::bigint,
        case when fr.resolved = 0 then 0::numeric else 0::numeric end,
        coalesce(lr.status, case when fr.facts = 0 then 'no_data' else 'unreconciled' end),
        coalesce(lr.variance, 0),
        case
            when fr.facts = 0 then array['No canonical cloud cost data is available.']::text[]
            when fr.quarantined <> 0 then array[
                'Cloud cost data is ingested and reconciled, but account ownership is unresolved.'
            ]::text[]
            else array[]::text[]
        end
    from fact_rollup fr
    cross join import_rollup ir
    left join latest_import li on true
    left join latest_reconciliation lr on true
    cross join account_rollup ar;
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
    select f.service_code, f.service_name, f.fact_status, count(*)::bigint,
           coalesce(sum(f.unblended_cost), 0)::numeric,
           coalesce(sum(f.blended_cost), 0)::numeric,
           coalesce(max(f.currency_code), 'USD')
    from public.cloud_cost_fact f
    where f.organization_id = requested_organization_id
      and f.tenant_id = requested_organization_id
      and f.fact_status in ('active', 'quarantined')
      and (requested_period_start is null or f.billing_period_end >= requested_period_start)
      and (requested_period_end is null or f.billing_period_start <= requested_period_end)
    group by f.service_code, f.service_name, f.fact_status
    order by sum(f.unblended_cost) desc nulls last, f.service_code, f.fact_status;
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
        f.payer_account_id,
        f.member_account_id,
        case when exists (
            select 1
            from public.cloud_account_mapping m
            where m.organization_id = f.organization_id
              and m.tenant_id = f.tenant_id
              and m.payer_account_id = f.payer_account_id
              and m.account_id = f.member_account_id
              and m.status = 'active'
        ) then 'resolved' else 'unknown' end,
        count(*)::bigint,
        coalesce(sum(f.unblended_cost), 0)::numeric,
        coalesce(sum(f.blended_cost), 0)::numeric,
        min(f.usage_start_at),
        max(f.usage_end_at),
        coalesce(max(f.currency_code), 'USD')
    from public.cloud_cost_fact f
    where f.organization_id = requested_organization_id
      and f.tenant_id = requested_organization_id
      and f.fact_status in ('active', 'quarantined')
      and (requested_period_start is null or f.billing_period_end >= requested_period_start)
      and (requested_period_end is null or f.billing_period_start <= requested_period_end)
    group by f.organization_id, f.tenant_id, f.payer_account_id, f.member_account_id
    order by sum(f.unblended_cost) desc nulls last, f.payer_account_id, f.member_account_id;
end;
$$;

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
        count(f.cloud_cost_fact_id)::bigint,
        coalesce(sum(f.unblended_cost), 0)::numeric,
        coalesce(sum(f.blended_cost), 0)::numeric,
        coalesce(r.variance_amount, 0)::numeric,
        coalesce(r.status, 'pending'),
        count(distinct f.member_account_id) filter (where f.fact_status = 'quarantined')::bigint,
        count(distinct f.member_account_id) filter (where f.fact_status = 'active')::bigint,
        i.created_at,
        i.completed_at,
        case when i.duplicate_row_count > 0 then 'replayed-idempotently'
             when i.status in ('completed', 'quarantined') then 'terminal'
             else 'not-terminal' end
    from public.cloud_cost_import i
    left join public.cloud_cost_fact f
      on f.organization_id = i.organization_id
     and f.tenant_id = i.tenant_id
     and f.import_id = i.import_id
     and f.fact_status in ('active', 'quarantined')
    left join public.cloud_cost_reconciliation r
      on r.organization_id = i.organization_id
     and r.tenant_id = i.tenant_id
     and r.import_id = i.import_id
    where i.organization_id = requested_organization_id
      and i.tenant_id = requested_organization_id
    group by i.import_id, i.source_file_name, i.payer_account_id, i.status,
             i.source_row_count, i.duplicate_row_count, i.created_at,
             i.completed_at, r.variance_amount, r.status
    order by i.created_at desc, i.import_id desc;
end;
$$;

revoke all on function public.tenant_cloud_financial_posture(uuid, date, date) from public, anon;
revoke all on function public.tenant_cloud_service_spend(uuid, date, date) from public, anon;
revoke all on function public.tenant_cloud_account_posture(uuid, date, date) from public, anon;
revoke all on function public.tenant_cloud_import_history(uuid) from public, anon;

grant execute on function public.tenant_cloud_financial_posture(uuid, date, date) to authenticated, service_role;
grant execute on function public.tenant_cloud_service_spend(uuid, date, date) to authenticated, service_role;
grant execute on function public.tenant_cloud_account_posture(uuid, date, date) to authenticated, service_role;
grant execute on function public.tenant_cloud_import_history(uuid) to authenticated, service_role;

commit;
