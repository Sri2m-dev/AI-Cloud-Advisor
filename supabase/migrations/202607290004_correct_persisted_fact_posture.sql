-- PVT-003C.1: persisted facts include active and quarantined facts.

begin;

alter function public.tenant_cloud_financial_posture(uuid, date, date)
    rename to tenant_cloud_financial_posture_v1;

revoke all on function public.tenant_cloud_financial_posture_v1(uuid, date, date)
from public, anon, authenticated;

create function public.tenant_cloud_financial_posture(
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
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
    select
        p.organization_id,
        p.currency,
        p.period_start,
        p.period_end,
        p.generated_at,
        p.import_count,
        p.latest_import_id,
        p.latest_import_status,
        p.source_rows,
        coalesce((
            select sum(fr.persisted_facts)::bigint
            from public.tenant_cloud_import_fact_rollup fr
            join public.cloud_cost_import i
              on i.organization_id = fr.organization_id
             and i.tenant_id = fr.tenant_id
             and i.import_id = fr.import_id
            where fr.organization_id = requested_organization_id
              and fr.tenant_id = requested_organization_id
              and (
                  requested_period_start is null
                  or i.billing_period_end >= requested_period_start
              )
              and (
                  requested_period_end is null
                  or i.billing_period_start <= requested_period_end
              )
        ), 0)::bigint,
        p.total_ingested_spend,
        p.cloud_spend,
        p.resolved_spend,
        p.quarantined_spend,
        p.allocated_spend,
        p.unallocated_resolved_spend,
        p.reconciled_spend,
        p.unreconciled_spend,
        p.resolved_account_count,
        p.unknown_account_count,
        p.foreign_account_count,
        p.ambiguous_account_count,
        p.allocation_coverage_percentage,
        p.reconciliation_status,
        p.reconciliation_variance,
        p.warnings
    from public.tenant_cloud_financial_posture_v1(
        requested_organization_id,
        requested_period_start,
        requested_period_end
    ) p;
$$;

revoke all on function public.tenant_cloud_financial_posture(uuid, date, date)
from public, anon;
grant execute on function public.tenant_cloud_financial_posture(uuid, date, date)
to authenticated, service_role;

commit;
