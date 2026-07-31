-- PVT-003C.1 remediation: use certified import/reconciliation totals for the
-- dashboard posture and reserve fact access for indexed account cardinality.

begin;

create index if not exists cloud_cost_fact_tenant_account_idx
    on public.cloud_cost_fact (
        organization_id,
        tenant_id,
        payer_account_id,
        member_account_id
    )
    where fact_status in ('active', 'quarantined');

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
    with scoped_imports as materialized (
        select
            i.*,
            coalesce(r.normalized_cost_total, i.normalized_cost_total, i.source_cost_total, 0)
                ::numeric as certified_total,
            coalesce(r.variance_amount, 0)::numeric as variance,
            r.status as reconciliation_state
        from public.cloud_cost_import i
        left join public.cloud_cost_reconciliation r
          on r.organization_id = i.organization_id
         and r.tenant_id = i.tenant_id
         and r.import_id = i.import_id
        where i.organization_id = requested_organization_id
          and i.tenant_id = requested_organization_id
          and (requested_period_start is null or i.billing_period_end >= requested_period_start)
          and (requested_period_end is null or i.billing_period_start <= requested_period_end)
    ),
    import_rollup as (
        select
            count(*)::bigint imports,
            min(billing_period_start) min_period,
            max(billing_period_end) max_period,
            coalesce(sum(source_row_count), 0)::bigint rows,
            coalesce(sum(accepted_row_count), 0)::bigint facts,
            coalesce(sum(certified_total), 0)::numeric total_spend,
            coalesce(sum(certified_total) filter (
                where status <> 'quarantined'
            ), 0)::numeric resolved,
            coalesce(sum(certified_total) filter (
                where status = 'quarantined'
            ), 0)::numeric quarantined,
            coalesce(sum(certified_total) filter (
                where variance = 0
                  and reconciliation_state in ('reconciled', 'quarantined')
            ), 0)::numeric reconciled,
            coalesce(max(currency_code), 'USD') currency_code,
            coalesce(sum(abs(variance)), 0)::numeric total_variance
        from scoped_imports
    ),
    latest_import as (
        select i.import_id, i.status, i.reconciliation_state
        from scoped_imports i
        order by i.created_at desc, i.import_id desc
        limit 1
    ),
    scoped_accounts as materialized (
        select distinct f.payer_account_id, f.member_account_id
        from public.cloud_cost_fact f
        where f.organization_id = requested_organization_id
          and f.tenant_id = requested_organization_id
          and f.fact_status in ('active', 'quarantined')
          and (requested_period_start is null or f.billing_period_end >= requested_period_start)
          and (requested_period_end is null or f.billing_period_start <= requested_period_end)
    ),
    account_rollup as (
        select
            count(*) filter (where exists (
                select 1
                from public.cloud_account_mapping m
                where m.organization_id = requested_organization_id
                  and m.tenant_id = requested_organization_id
                  and m.payer_account_id = a.payer_account_id
                  and m.account_id = a.member_account_id
                  and m.status = 'active'
            ))::bigint resolved_accounts,
            count(*) filter (where not exists (
                select 1
                from public.cloud_account_mapping m
                where m.organization_id = requested_organization_id
                  and m.tenant_id = requested_organization_id
                  and m.payer_account_id = a.payer_account_id
                  and m.account_id = a.member_account_id
                  and m.status = 'active'
            ))::bigint unknown_accounts
        from scoped_accounts a
    )
    select
        requested_organization_id,
        ir.currency_code,
        ir.min_period,
        ir.max_period,
        statement_timestamp(),
        ir.imports,
        li.import_id,
        li.status,
        ir.rows,
        ir.facts,
        ir.total_spend,
        ir.total_spend,
        ir.resolved,
        ir.quarantined,
        0::numeric,
        ir.resolved,
        ir.reconciled,
        ir.total_spend - ir.reconciled,
        coalesce(ar.resolved_accounts, 0),
        coalesce(ar.unknown_accounts, 0),
        0::bigint,
        0::bigint,
        0::numeric,
        coalesce(
            li.reconciliation_state,
            case when ir.imports = 0 then 'no_data' else 'unreconciled' end
        ),
        ir.total_variance,
        case
            when ir.imports = 0 then array[
                'No canonical cloud cost data is available.'
            ]::text[]
            when ir.quarantined <> 0 then array[
                'Cloud cost data is ingested and reconciled, but account ownership is unresolved.'
            ]::text[]
            else array[]::text[]
        end
    from import_rollup ir
    left join latest_import li on true
    cross join account_rollup ar;
end;
$$;

commit;
