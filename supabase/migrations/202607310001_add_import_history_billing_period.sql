-- P4.0: expose non-sensitive billing-period metadata in tenant import history.

begin;

drop function public.tenant_cloud_import_history(uuid);

create function public.tenant_cloud_import_history(
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
    billing_period_start date,
    billing_period_end date,
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
        i.billing_period_start,
        i.billing_period_end,
        i.created_at,
        i.completed_at,
        case
            when i.duplicate_row_count > 0 then 'replayed-idempotently'
            when i.status in ('completed', 'quarantined') then 'terminal'
            else 'not-terminal'
        end
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

revoke all on function public.tenant_cloud_import_history(uuid)
from public, anon;
grant execute on function public.tenant_cloud_import_history(uuid)
to authenticated, service_role;

commit;
