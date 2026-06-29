create table if not exists public.digital_twin_quality_history (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    snapshot_date date not null,
    overall_quality numeric(6,2) not null default 0,
    digital_twin_health numeric(6,2) not null default 0,
    relationship_quality numeric(6,2) not null default 0,
    ownership_quality numeric(6,2) not null default 0,
    cost_quality numeric(6,2) not null default 0,
    mapping_quality numeric(6,2) not null default 0,
    capability_quality numeric(6,2) not null default 0,
    freshness_quality numeric(6,2) not null default 0,
    created_at timestamptz not null default now(),
    unique (organization_id, snapshot_date)
);

create index if not exists idx_digital_twin_quality_history_org_date
    on public.digital_twin_quality_history (organization_id, snapshot_date);
