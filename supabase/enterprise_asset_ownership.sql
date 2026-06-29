create table if not exists public.enterprise_asset_ownership (
    id uuid primary key default gen_random_uuid(),
    organization_id text not null,
    enterprise_asset_id text not null,
    application text,
    business_service text,
    business_capability text,
    department text,
    team text,
    technical_owner text,
    business_owner text,
    executive_owner text,
    cost_center text,
    environment text,
    criticality text,
    lifecycle text,
    source text,
    confidence numeric not null default 0,
    ownership_score numeric not null default 0,
    reviewed boolean not null default false,
    reviewed_by text,
    reviewed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists idx_enterprise_asset_ownership_asset
    on public.enterprise_asset_ownership (enterprise_asset_id);

create index if not exists idx_enterprise_asset_ownership_org
    on public.enterprise_asset_ownership (organization_id);

create index if not exists idx_enterprise_asset_ownership_department
    on public.enterprise_asset_ownership (organization_id, department);

create index if not exists idx_enterprise_asset_ownership_owner
    on public.enterprise_asset_ownership (organization_id, technical_owner);

create index if not exists idx_enterprise_asset_ownership_reviewed
    on public.enterprise_asset_ownership (organization_id, reviewed);
