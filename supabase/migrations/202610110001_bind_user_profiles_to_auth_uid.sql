-- Bind application profiles to immutable Supabase Auth identities.
-- Existing profiles intentionally remain unbound until an approved identity
-- reconciliation is performed; email matching is not a backfill mechanism.
begin;

alter table public.users
    add column if not exists auth_user_id uuid
    references auth.users(id) on delete cascade;

create unique index if not exists users_auth_user_id_uidx
    on public.users (auth_user_id)
    where auth_user_id is not null;

drop policy if exists users_select_self on public.users;
create policy users_select_self
on public.users
for select
to authenticated
using (auth_user_id = (select auth.uid()));

drop policy if exists organizations_select_own on public.organizations;
create policy organizations_select_own
on public.organizations
for select
to authenticated
using (
    id = (
        select u.org_id
        from public.users u
        where u.auth_user_id = (select auth.uid())
        limit 1
    )
);

drop policy if exists clients_select_own_org on public.clients;
create policy clients_select_own_org
on public.clients
for select
to authenticated
using (
    org_id = (
        select u.org_id
        from public.users u
        where u.auth_user_id = (select auth.uid())
        limit 1
    )
);

drop policy if exists recommendations_select_own_org on public.recommendations;
create policy recommendations_select_own_org
on public.recommendations
for select
to authenticated
using (
    org_id = (
        select u.org_id
        from public.users u
        where u.auth_user_id = (select auth.uid())
        limit 1
    )
);

drop policy if exists recommendations_insert_own_org on public.recommendations;
create policy recommendations_insert_own_org
on public.recommendations
for insert
to authenticated
with check (
    org_id = (
        select u.org_id
        from public.users u
        where u.auth_user_id = (select auth.uid())
        limit 1
    )
);

drop policy if exists report_history_select_own_org on public.report_history;
create policy report_history_select_own_org
on public.report_history
for select
to authenticated
using (
    org_id is not null
    and tenant_id is not null
    and org_id = (
        select u.org_id::text
        from public.users u
        where u.auth_user_id = (select auth.uid())
        limit 1
    )
    and tenant_id = (
        select u.org_id::text
        from public.users u
        where u.auth_user_id = (select auth.uid())
        limit 1
    )
);

drop policy if exists report_history_insert_own_org on public.report_history;
create policy report_history_insert_own_org
on public.report_history
for insert
to authenticated
with check (
    org_id is not null
    and tenant_id is not null
    and org_id = (
        select u.org_id::text
        from public.users u
        where u.auth_user_id = (select auth.uid())
        limit 1
    )
    and tenant_id = (
        select u.org_id::text
        from public.users u
        where u.auth_user_id = (select auth.uid())
        limit 1
    )
);

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
                where u.auth_user_id = (select auth.uid())
                  and u.org_id = requested_organization_id
            )
        );
$$;

drop policy if exists cloud_cost_import_select_own_org on public.cloud_cost_import;
create policy cloud_cost_import_select_own_org on public.cloud_cost_import
for select to authenticated using (
    organization_id = (
        select u.org_id from public.users u where u.auth_user_id = (select auth.uid()) limit 1
    )
    and tenant_id = (
        select u.org_id from public.users u where u.auth_user_id = (select auth.uid()) limit 1
    )
);

drop policy if exists cloud_cost_import_part_select_own_org on public.cloud_cost_import_part;
create policy cloud_cost_import_part_select_own_org on public.cloud_cost_import_part
for select to authenticated using (
    organization_id = (
        select u.org_id from public.users u where u.auth_user_id = (select auth.uid()) limit 1
    )
    and tenant_id = (
        select u.org_id from public.users u where u.auth_user_id = (select auth.uid()) limit 1
    )
);

drop policy if exists cloud_account_mapping_select_own_org on public.cloud_account_mapping;
create policy cloud_account_mapping_select_own_org on public.cloud_account_mapping
for select to authenticated using (
    organization_id = (
        select u.org_id from public.users u where u.auth_user_id = (select auth.uid()) limit 1
    )
    and tenant_id = (
        select u.org_id from public.users u where u.auth_user_id = (select auth.uid()) limit 1
    )
);

drop policy if exists cloud_cost_reconciliation_select_own_org on public.cloud_cost_reconciliation;
create policy cloud_cost_reconciliation_select_own_org on public.cloud_cost_reconciliation
for select to authenticated using (
    organization_id = (
        select u.org_id from public.users u where u.auth_user_id = (select auth.uid()) limit 1
    )
    and tenant_id = (
        select u.org_id from public.users u where u.auth_user_id = (select auth.uid()) limit 1
    )
);

create or replace function public.fg002_resolve_cloud_account(
    requested_organization_id uuid,
    requested_payer_account_id text,
    requested_account_id text,
    requested_mapping jsonb,
    requested_reason text,
    requested_confirmed boolean,
    requested_expected_state text default 'DISCOVERED'
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    actor_email text;
    actor_id text := auth.uid()::text;
    actor_role text;
    existing_registry public.cloud_account_registry%rowtype;
    registry_row public.cloud_account_registry%rowtype;
    before_posture jsonb;
    after_posture jsonb;
    evidence jsonb;
    next_version integer;
    complete boolean;
    target_state text;
    effective_on date;
begin
    if not requested_confirmed then
        raise exception 'explicit confirmation required' using errcode = '22023';
    end if;
    if nullif(btrim(requested_reason), '') is null then
        raise exception 'resolution reason required' using errcode = '22023';
    end if;
    if not public.pvt003c1_can_read_organization(requested_organization_id) then
        raise insufficient_privilege using message = 'organization membership required';
    end if;

    select lower(coalesce(u.email, '')), lower(coalesce(u.role, ''))
    into actor_email, actor_role
    from public.users u
    where u.auth_user_id = (select auth.uid())
      and u.org_id = requested_organization_id
    limit 1;
    if coalesce(actor_role, '') not in (
        'super_admin', 'global_admin', 'client_admin', 'organization_admin', 'finance', 'operations'
    ) then
        raise insufficient_privilege using message = 'account resolution permission required';
    end if;
    if requested_account_id is null or requested_payer_account_id is null then
        raise exception 'discovered identity required';
    end if;

    perform pg_advisory_xact_lock(
        hashtextextended(
            requested_organization_id::text || ':' || requested_payer_account_id || ':' || requested_account_id,
            0
        )
    );
    perform 1
    from public.tenant_cloud_account_fact_rollup a
    where a.organization_id = requested_organization_id
      and a.tenant_id = requested_organization_id
      and a.payer_account_id = requested_payer_account_id
      and a.account_id = requested_account_id;
    if not found then
        raise exception 'unresolved discovered account not found';
    end if;
    if requested_expected_state = 'DISCOVERED' and exists (
        select 1
        from public.cloud_account_mapping m
        where m.organization_id = requested_organization_id
          and m.tenant_id = requested_organization_id
          and m.payer_account_id = requested_payer_account_id
          and m.account_id = requested_account_id
          and m.status = 'active'
    ) then
        raise exception 'account is already resolved';
    end if;

    select to_jsonb(p)
    into before_posture
    from public.tenant_cloud_financial_posture(requested_organization_id, null, null) p;
    select *
    into existing_registry
    from public.cloud_account_registry r
    where r.organization_id = requested_organization_id
      and r.tenant_id = requested_organization_id
      and r.provider = 'aws'
      and r.account_id = requested_account_id
    for update;
    if found and existing_registry.resolution_status <> requested_expected_state then
        raise exception 'stale account resolution state';
    end if;
    effective_on := coalesce(nullif(requested_mapping->>'effective_date', '')::date, current_date);
    select greatest(effective_on, coalesce(max(m.effective_from) + 1, effective_on))
    into effective_on
    from public.cloud_account_mapping m
    where m.organization_id = requested_organization_id
      and m.tenant_id = requested_organization_id
      and m.provider = 'aws'
      and m.payer_account_id = requested_payer_account_id
      and m.account_id = requested_account_id;
    complete := (
        nullif(btrim(requested_mapping->>'business_unit'), '') is not null
        or nullif(btrim(requested_mapping->>'department'), '') is not null
    )
    and nullif(btrim(requested_mapping->>'cost_center'), '') is not null
    and nullif(btrim(requested_mapping->>'environment'), '') is not null
    and upper(coalesce(requested_mapping->>'resolution_status', '')) in ('APPROVED', 'ACTIVE');
    target_state := case
        when complete then 'ACTIVE'
        when upper(coalesce(requested_mapping->>'resolution_status', '')) in ('REJECTED', 'SUSPENDED')
            then upper(requested_mapping->>'resolution_status')
        when upper(coalesce(requested_mapping->>'resolution_status', '')) = 'READY_FOR_APPROVAL'
            then 'READY_FOR_APPROVAL'
        when not complete then 'PARTIALLY_MAPPED'
        else 'PENDING_REVIEW'
    end;
    evidence := jsonb_build_object(
        'original_provider', 'aws',
        'provider_account_id', requested_account_id,
        'payer_account_id', requested_payer_account_id,
        'source_import_id', requested_mapping->>'source_import_id',
        'first_seen_at', requested_mapping->>'first_seen_at',
        'last_seen_at', requested_mapping->>'last_seen_at',
        'billing_period', requested_mapping->>'billing_period',
        'quarantined_spend', requested_mapping->>'quarantined_spend',
        'currency', requested_mapping->>'currency',
        'source_state', 'DISCOVERED'
    );
    next_version := coalesce(existing_registry.version, 0) + 1;

    insert into public.cloud_account_registry(
        organization_id, tenant_id, provider, account_id, account_name, alias, environment,
        business_unit, department, application, business_service, owner, technical_owner,
        finance_owner, cost_center, project, criticality, status, resolution_status,
        resolution_reason, effective_date, version, source_evidence
    )
    values (
        requested_organization_id, requested_organization_id, 'aws', requested_account_id,
        coalesce(requested_mapping->>'account_name', requested_account_id),
        requested_mapping->>'alias', requested_mapping->>'environment',
        requested_mapping->>'business_unit', requested_mapping->>'department',
        requested_mapping->>'application', requested_mapping->>'business_service',
        requested_mapping->>'owner', requested_mapping->>'technical_owner',
        requested_mapping->>'finance_owner', requested_mapping->>'cost_center',
        requested_mapping->>'project_code', requested_mapping->>'criticality',
        lower(target_state), target_state, requested_reason, effective_on, next_version, evidence
    )
    on conflict (organization_id, tenant_id, provider, account_id) do update set
        account_name = excluded.account_name,
        alias = excluded.alias,
        environment = excluded.environment,
        business_unit = excluded.business_unit,
        department = excluded.department,
        application = excluded.application,
        business_service = excluded.business_service,
        owner = excluded.owner,
        technical_owner = excluded.technical_owner,
        finance_owner = excluded.finance_owner,
        cost_center = excluded.cost_center,
        project = excluded.project,
        criticality = excluded.criticality,
        status = excluded.status,
        resolution_status = excluded.resolution_status,
        resolution_reason = excluded.resolution_reason,
        effective_date = excluded.effective_date,
        version = excluded.version,
        source_evidence = public.cloud_account_registry.source_evidence,
        updated_at = now()
    returning * into registry_row;

    update public.cloud_account_mapping
    set effective_to = effective_on - 1, status = 'inactive', updated_at = now()
    where organization_id = requested_organization_id
      and tenant_id = requested_organization_id
      and provider = 'aws'
      and payer_account_id = requested_payer_account_id
      and account_id = requested_account_id
      and effective_to is null;
    insert into public.cloud_account_mapping(
        cloud_account_mapping_id, organization_id, tenant_id, provider, payer_account_id,
        account_id, account_kind, status, display_name, effective_from, mapping_source
    )
    values (
        gen_random_uuid(), requested_organization_id, requested_organization_id, 'aws',
        requested_payer_account_id, requested_account_id,
        case when requested_payer_account_id = requested_account_id then 'payer' else 'member' end,
        case when complete then 'active' else 'quarantined' end,
        registry_row.account_name, effective_on, 'fg002_governed_resolution'
    );
    select to_jsonb(p)
    into after_posture
    from public.tenant_cloud_financial_posture(requested_organization_id, null, null) p;
    if (before_posture->>'total_ingested_spend')::numeric
        <> (after_posture->>'total_ingested_spend')::numeric
        or coalesce((after_posture->>'reconciliation_variance')::numeric, 0) <> 0 then
        raise exception 'financial reconciliation invariant failed';
    end if;

    insert into public.cloud_account_registry_audit(
        registry_id, organization_id, tenant_id, actor_id, actor_email,
        action, old_value, new_value, reason
    )
    values (
        registry_row.id, requested_organization_id, requested_organization_id,
        actor_id, actor_email, 'resolve', to_jsonb(existing_registry),
        to_jsonb(registry_row), requested_reason
    );
    insert into public.cloud_account_registry_version(
        registry_id, organization_id, tenant_id, version, previous_state, new_state,
        previous_values, new_values, actor_id, actor_email, actor_role, reason,
        approval_identity, source_import_id, financial_before, financial_after
    )
    values (
        registry_row.id, requested_organization_id, requested_organization_id, next_version,
        existing_registry.resolution_status, target_state, coalesce(to_jsonb(existing_registry), '{}'),
        to_jsonb(registry_row), actor_id, actor_email, actor_role, requested_reason,
        case when complete then actor_email end, requested_mapping->>'source_import_id',
        before_posture, after_posture
    );
    return jsonb_build_object(
        'registry', to_jsonb(registry_row),
        'financial_before', before_posture,
        'financial_after', after_posture,
        'allocation_ready', complete,
        'version', next_version
    );
end;
$$;

revoke all on function public.fg002_resolve_cloud_account(
    uuid, text, text, jsonb, text, boolean, text
) from public, anon;
grant execute on function public.fg002_resolve_cloud_account(
    uuid, text, text, jsonb, text, boolean, text
) to authenticated, service_role;

create or replace function public.fg002_bulk_resolve_cloud_accounts(
    requested_organization_id uuid,
    requested_accounts jsonb,
    requested_mapping jsonb,
    requested_reason text,
    requested_confirmed boolean
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    item jsonb;
    result jsonb;
    results jsonb := '[]'::jsonb;
    actor_email text;
    actor_id text := coalesce(auth.uid()::text, 'service-role');
begin
    if not requested_confirmed then
        raise exception 'explicit bulk confirmation required' using errcode = '22023';
    end if;
    if nullif(btrim(requested_reason), '') is null then
        raise exception 'bulk resolution reason required' using errcode = '22023';
    end if;
    if jsonb_typeof(requested_accounts) <> 'array'
        or jsonb_array_length(requested_accounts) = 0 then
        raise exception 'bulk accounts required';
    end if;

    select lower(coalesce(u.email, ''))
    into actor_email
    from public.users u
    where u.auth_user_id = (select auth.uid())
      and u.org_id = requested_organization_id
    limit 1;
    if actor_email is null or actor_email = '' then
        raise insufficient_privilege using message = 'organization membership required';
    end if;

    for item in select value from jsonb_array_elements(requested_accounts) loop
        result := public.fg002_resolve_cloud_account(
            requested_organization_id,
            item->>'payer_account_id',
            item->>'account_id',
            requested_mapping || item,
            requested_reason,
            true,
            coalesce(item->>'expected_state', 'DISCOVERED')
        );
        results := results || jsonb_build_array(result);
    end loop;
    insert into public.cloud_account_resolution_bulk_audit(
        organization_id, tenant_id, actor_id, actor_email, reason,
        account_count, requested_changes, results
    )
    values (
        requested_organization_id, requested_organization_id, actor_id, actor_email,
        requested_reason, jsonb_array_length(requested_accounts), requested_mapping, results
    );
    return jsonb_build_object('count', jsonb_array_length(results), 'results', results);
end;
$$;

revoke all on function public.fg002_bulk_resolve_cloud_accounts(
    uuid, jsonb, jsonb, text, boolean
) from public, anon;
grant execute on function public.fg002_bulk_resolve_cloud_accounts(
    uuid, jsonb, jsonb, text, boolean
) to authenticated, service_role;

commit;
