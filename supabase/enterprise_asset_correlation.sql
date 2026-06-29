create table if not exists public.enterprise_asset_correlation (
    enterprise_asset_id text primary key,
    organization_id text not null,
    application text,
    business_service text,
    business_capability text,
    department text,
    team text,
    owner text,
    environment text,
    cost_center text,
    cloud_account text,
    vendor text,
    ai_services jsonb not null default '[]'::jsonb,
    confidence numeric not null default 0,
    correlation_source text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_enterprise_asset_correlation_org
    on public.enterprise_asset_correlation (organization_id);

create index if not exists idx_enterprise_asset_correlation_application
    on public.enterprise_asset_correlation (organization_id, application);

create index if not exists idx_enterprise_asset_correlation_business_service
    on public.enterprise_asset_correlation (organization_id, business_service);

create index if not exists idx_enterprise_asset_correlation_confidence
    on public.enterprise_asset_correlation (organization_id, confidence);
