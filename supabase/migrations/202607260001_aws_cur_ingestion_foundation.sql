-- PVT-003A: tenant-owned AWS CUR persistence and security foundation.
-- This migration is additive. It creates no ingestion engine, UI, worker, or
-- financial-model behavior. Deployment requires a separate Owner authorization.

begin;

create table if not exists public.cloud_cost_import (
    import_id uuid primary key,
    organization_id uuid not null references public.organizations(id),
    tenant_id uuid not null references public.organizations(id),
    import_key text not null,
    payer_account_id text not null,
    billing_period_start date not null,
    billing_period_end date not null,
    source_file_name text not null,
    source_file_sha256 text not null check (source_file_sha256 ~ '^[0-9a-f]{64}$'),
    source_uri text,
    compression text not null check (compression in ('csv', 'gzip')),
    parser_profile text not null,
    status text not null check (status in ('received', 'validating', 'quarantined', 'processing', 'reconciling', 'completed', 'failed', 'superseded')),
    source_row_count bigint,
    accepted_row_count bigint not null default 0,
    rejected_row_count bigint not null default 0,
    duplicate_row_count bigint not null default 0,
    source_cost_total numeric(24, 10),
    normalized_cost_total numeric(24, 10),
    currency_code text,
    supersedes_import_id uuid references public.cloud_cost_import(import_id),
    created_by_user_id uuid,
    created_at timestamptz not null default now(),
    completed_at timestamptz,
    failure_code text,
    failure_detail text,
    source_evidence jsonb not null default '{}'::jsonb,
    constraint cloud_cost_import_tenant_matches_organization check (tenant_id = organization_id),
    constraint cloud_cost_import_period_valid check (billing_period_end >= billing_period_start),
    constraint cloud_cost_import_key_unique unique (organization_id, tenant_id, import_key),
    constraint cloud_cost_import_file_unique unique (organization_id, tenant_id, payer_account_id, source_file_sha256)
);

create table if not exists public.cloud_cost_import_part (
    import_part_id uuid primary key,
    organization_id uuid not null references public.organizations(id),
    tenant_id uuid not null references public.organizations(id),
    import_id uuid not null references public.cloud_cost_import(import_id) on delete restrict,
    part_key text not null,
    part_name text not null,
    part_sha256 text not null check (part_sha256 ~ '^[0-9a-f]{64}$'),
    row_start bigint not null check (row_start >= 1),
    row_end bigint check (row_end is null or row_end >= row_start),
    checkpoint_row bigint not null default 0 check (checkpoint_row >= 0),
    status text not null check (status in ('pending', 'processing', 'completed', 'failed', 'quarantined')),
    accepted_row_count bigint not null default 0,
    rejected_row_count bigint not null default 0,
    duplicate_row_count bigint not null default 0,
    retry_count integer not null default 0 check (retry_count >= 0),
    error_sample jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint cloud_cost_import_part_tenant_matches_organization check (tenant_id = organization_id),
    constraint cloud_cost_import_part_key_unique unique (organization_id, tenant_id, import_id, part_key),
    constraint cloud_cost_import_part_hash_unique unique (organization_id, tenant_id, import_id, part_sha256)
);

create table if not exists public.cloud_account_mapping (
    cloud_account_mapping_id uuid primary key,
    organization_id uuid not null references public.organizations(id),
    tenant_id uuid not null references public.organizations(id),
    provider text not null check (provider = 'aws'),
    payer_account_id text not null,
    account_id text not null,
    account_kind text not null check (account_kind in ('payer', 'member')),
    status text not null check (status in ('active', 'quarantined', 'inactive')),
    display_name text,
    effective_from date not null,
    effective_to date,
    mapping_source text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint cloud_account_mapping_tenant_matches_organization check (tenant_id = organization_id),
    constraint cloud_account_mapping_period_valid check (effective_to is null or effective_to >= effective_from),
    constraint cloud_account_mapping_unique unique (organization_id, tenant_id, provider, payer_account_id, account_id, effective_from)
);

create table if not exists public.cloud_cost_fact (
    cloud_cost_fact_id uuid primary key,
    organization_id uuid not null references public.organizations(id),
    tenant_id uuid not null references public.organizations(id),
    import_id uuid not null references public.cloud_cost_import(import_id) on delete restrict,
    import_part_id uuid not null references public.cloud_cost_import_part(import_part_id) on delete restrict,
    source_row_key text not null,
    source_row_hash text not null check (source_row_hash ~ '^[0-9a-f]{64}$'),
    supersedes_fact_id uuid references public.cloud_cost_fact(cloud_cost_fact_id),
    fact_status text not null check (fact_status in ('active', 'superseded', 'quarantined', 'rejected')),
    payer_account_id text not null,
    member_account_id text not null,
    billing_period_start date not null,
    billing_period_end date not null,
    usage_start_at timestamptz,
    usage_end_at timestamptz,
    service_code text,
    service_name text,
    product_code text,
    region text,
    availability_zone text,
    resource_id text,
    usage_type text,
    operation text,
    usage_quantity numeric(24, 10),
    usage_unit text,
    line_item_type text not null,
    currency_code text not null,
    unblended_cost numeric(24, 10),
    blended_cost numeric(24, 10),
    amortized_cost numeric(24, 10),
    effective_cost numeric(24, 10),
    discount_amount numeric(24, 10),
    credit_amount numeric(24, 10),
    refund_amount numeric(24, 10),
    tax_amount numeric(24, 10),
    reservation_arn text,
    reservation_effective_cost numeric(24, 10),
    savings_plan_arn text,
    savings_plan_effective_cost numeric(24, 10),
    tags jsonb not null default '{}'::jsonb,
    raw_fields jsonb not null default '{}'::jsonb,
    source_evidence jsonb not null default '{}'::jsonb,
    ingested_at timestamptz not null default now(),
    constraint cloud_cost_fact_tenant_matches_organization check (tenant_id = organization_id),
    constraint cloud_cost_fact_period_valid check (billing_period_end >= billing_period_start),
    constraint cloud_cost_fact_source_unique unique (organization_id, tenant_id, source_row_key),
    constraint cloud_cost_fact_hash_unique unique (organization_id, tenant_id, import_id, source_row_hash)
);

create table if not exists public.cloud_cost_reconciliation (
    cloud_cost_reconciliation_id uuid primary key,
    organization_id uuid not null references public.organizations(id),
    tenant_id uuid not null references public.organizations(id),
    import_id uuid not null references public.cloud_cost_import(import_id) on delete restrict,
    billing_period_start date not null,
    billing_period_end date not null,
    payer_account_id text not null,
    source_row_count bigint not null,
    normalized_row_count bigint not null,
    rejected_row_count bigint not null,
    duplicate_row_count bigint not null,
    source_cost_total numeric(24, 10),
    normalized_cost_total numeric(24, 10),
    variance_amount numeric(24, 10),
    currency_code text,
    status text not null check (status in ('pending', 'reconciled', 'variance_detected', 'quarantined', 'failed')),
    evidence jsonb not null default '{}'::jsonb,
    reconciled_at timestamptz,
    created_at timestamptz not null default now(),
    constraint cloud_cost_reconciliation_tenant_matches_organization check (tenant_id = organization_id),
    constraint cloud_cost_reconciliation_period_valid check (billing_period_end >= billing_period_start),
    constraint cloud_cost_reconciliation_import_unique unique (organization_id, tenant_id, import_id)
);

create index if not exists cloud_cost_import_tenant_period_idx
    on public.cloud_cost_import (organization_id, tenant_id, billing_period_start desc, payer_account_id);
create index if not exists cloud_cost_import_part_resume_idx
    on public.cloud_cost_import_part (organization_id, tenant_id, import_id, status, checkpoint_row);
create index if not exists cloud_account_mapping_lookup_idx
    on public.cloud_account_mapping (organization_id, tenant_id, provider, payer_account_id, account_id, status);
create index if not exists cloud_cost_fact_tenant_period_idx
    on public.cloud_cost_fact (organization_id, tenant_id, billing_period_start, payer_account_id, member_account_id);
create index if not exists cloud_cost_fact_rollup_idx
    on public.cloud_cost_fact (organization_id, tenant_id, usage_start_at, service_code, region);
create index if not exists cloud_cost_reconciliation_tenant_period_idx
    on public.cloud_cost_reconciliation (organization_id, tenant_id, billing_period_start desc, status);

revoke all on public.cloud_cost_import, public.cloud_cost_import_part,
    public.cloud_account_mapping, public.cloud_cost_fact,
    public.cloud_cost_reconciliation from anon, authenticated;

grant select on public.cloud_cost_import, public.cloud_cost_import_part,
    public.cloud_account_mapping, public.cloud_cost_reconciliation to authenticated;

alter table public.cloud_cost_import enable row level security;
alter table public.cloud_cost_import_part enable row level security;
alter table public.cloud_account_mapping enable row level security;
alter table public.cloud_cost_fact enable row level security;
alter table public.cloud_cost_reconciliation enable row level security;

drop policy if exists cloud_cost_import_select_own_org on public.cloud_cost_import;
create policy cloud_cost_import_select_own_org on public.cloud_cost_import
for select to authenticated using (
    organization_id = (select u.org_id from public.users u where lower(u.email) = lower(auth.jwt() ->> 'email') limit 1)
    and tenant_id = (select u.org_id from public.users u where lower(u.email) = lower(auth.jwt() ->> 'email') limit 1)
);

drop policy if exists cloud_cost_import_part_select_own_org on public.cloud_cost_import_part;
create policy cloud_cost_import_part_select_own_org on public.cloud_cost_import_part
for select to authenticated using (
    organization_id = (select u.org_id from public.users u where lower(u.email) = lower(auth.jwt() ->> 'email') limit 1)
    and tenant_id = (select u.org_id from public.users u where lower(u.email) = lower(auth.jwt() ->> 'email') limit 1)
);

drop policy if exists cloud_account_mapping_select_own_org on public.cloud_account_mapping;
create policy cloud_account_mapping_select_own_org on public.cloud_account_mapping
for select to authenticated using (
    organization_id = (select u.org_id from public.users u where lower(u.email) = lower(auth.jwt() ->> 'email') limit 1)
    and tenant_id = (select u.org_id from public.users u where lower(u.email) = lower(auth.jwt() ->> 'email') limit 1)
);

drop policy if exists cloud_cost_reconciliation_select_own_org on public.cloud_cost_reconciliation;
create policy cloud_cost_reconciliation_select_own_org on public.cloud_cost_reconciliation
for select to authenticated using (
    organization_id = (select u.org_id from public.users u where lower(u.email) = lower(auth.jwt() ->> 'email') limit 1)
    and tenant_id = (select u.org_id from public.users u where lower(u.email) = lower(auth.jwt() ->> 'email') limit 1)
);

-- No authenticated write policy is created. Import writes are backend/service
-- workflows in PVT-003B and must validate TenantContext plus account ownership.

do $$
declare unsafe_policy record;
begin
    for unsafe_policy in
        select schemaname, tablename, policyname
        from pg_catalog.pg_policies
        where schemaname = 'public'
          and tablename in ('cloud_cost_import', 'cloud_cost_import_part', 'cloud_account_mapping', 'cloud_cost_fact', 'cloud_cost_reconciliation')
          and (roles && array['public', 'anon']::name[]
               or coalesce(qual, '') ~ '^\\s*\\(?true\\)?\\s*$'
               or coalesce(with_check, '') ~ '^\\s*\\(?true\\)?\\s*$')
    loop
        raise exception 'Unsafe CUR policy remains: %.% policy %', unsafe_policy.schemaname, unsafe_policy.tablename, unsafe_policy.policyname;
    end loop;
end
$$;

commit;
