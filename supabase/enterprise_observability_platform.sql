create table if not exists public.telemetry_fabric (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    source_system text not null,
    signal_type text not null,
    entity text,
    service text,
    business_service text,
    metric_name text,
    metric_value text,
    severity text not null default 'Info',
    observed_at timestamptz not null default now(),
    payload jsonb not null default '{}'::jsonb,
    quality_score numeric(6,2) not null default 0,
    created_at timestamptz not null default now()
);

create index if not exists idx_telemetry_fabric_org_signal
    on public.telemetry_fabric (organization_id, signal_type, observed_at desc);

create index if not exists idx_telemetry_fabric_org_service
    on public.telemetry_fabric (organization_id, business_service, observed_at desc);

create table if not exists public.enterprise_event_bus (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    source_system text not null,
    event_type text not null,
    entity text,
    business_service text,
    severity text not null default 'Info',
    payload jsonb not null default '{}'::jsonb,
    published_at timestamptz not null default now(),
    consumed_by jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_enterprise_event_bus_org_type
    on public.enterprise_event_bus (organization_id, event_type, published_at desc);

create table if not exists public.telemetry_correlation (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    asset text not null,
    business_service text,
    correlation_type text not null,
    confidence numeric(6,2) not null default 0,
    revenue_risk numeric(14,2) not null default 0,
    recommendation text,
    evidence jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_telemetry_correlation_org_asset
    on public.telemetry_correlation (organization_id, asset, created_at desc);
