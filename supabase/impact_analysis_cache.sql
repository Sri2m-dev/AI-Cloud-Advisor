create table if not exists public.impact_analysis_cache (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    asset_id text not null,
    asset_type text not null,
    impact_score numeric(6,2) not null default 0,
    risk_score numeric(6,2) not null default 0,
    business_services integer not null default 0,
    applications integer not null default 0,
    departments integer not null default 0,
    owners integer not null default 0,
    annual_cost numeric(14,2) not null default 0,
    revenue_risk numeric(14,2) not null default 0,
    analysis_payload jsonb not null default '{}'::jsonb,
    generated_at timestamptz not null default now(),
    unique (organization_id, asset_id, asset_type)
);

create index if not exists idx_impact_analysis_cache_org_asset
    on public.impact_analysis_cache (organization_id, asset_type, asset_id);

create index if not exists idx_impact_analysis_cache_org_score
    on public.impact_analysis_cache (organization_id, impact_score desc, risk_score desc);
