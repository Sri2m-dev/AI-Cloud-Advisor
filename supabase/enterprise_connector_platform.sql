create table if not exists public.enterprise_connectors (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    name text not null,
    provider text not null,
    connector_type text not null,
    enabled boolean not null default true,
    auth_type text not null default 'api_key',
    status text not null default 'Registered',
    capabilities jsonb not null default '[]'::jsonb,
    settings jsonb not null default '{}'::jsonb,
    sync_interval_minutes integer not null default 60,
    last_discovered_at timestamptz,
    last_synced_at timestamptz,
    last_health_status text not null default 'Unknown',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (organization_id, provider, name)
);

create index if not exists idx_enterprise_connectors_org_provider
    on public.enterprise_connectors (organization_id, provider, status);

create table if not exists public.enterprise_connector_runs (
    id uuid primary key default gen_random_uuid(),
    connector_id uuid not null references public.enterprise_connectors(id) on delete cascade,
    operation text not null,
    status text not null,
    message text not null default '',
    entities_synced integer not null default 0,
    relationships_synced integer not null default 0,
    metadata_records integer not null default 0,
    events_published integer not null default 0,
    errors jsonb not null default '[]'::jsonb,
    data jsonb not null default '{}'::jsonb,
    started_at timestamptz not null default now(),
    completed_at timestamptz not null default now()
);

create index if not exists idx_enterprise_connector_runs_connector
    on public.enterprise_connector_runs (connector_id, completed_at desc);

create table if not exists public.enterprise_connector_health (
    id uuid primary key default gen_random_uuid(),
    connector_id uuid not null references public.enterprise_connectors(id) on delete cascade,
    status text not null default 'Unknown',
    score numeric(6,2) not null default 0,
    message text not null default '',
    last_success_at timestamptz,
    last_error_at timestamptz,
    error_count integer not null default 0,
    latency_ms integer not null default 0,
    checked_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_enterprise_connector_health_connector
    on public.enterprise_connector_health (connector_id, checked_at desc);

create table if not exists public.enterprise_connector_schedules (
    id uuid primary key default gen_random_uuid(),
    connector_id uuid not null references public.enterprise_connectors(id) on delete cascade,
    operation text not null,
    interval_minutes integer not null,
    status text not null default 'Enabled',
    next_run_at timestamptz,
    last_run_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (connector_id, operation)
);

create index if not exists idx_enterprise_connector_schedules_due
    on public.enterprise_connector_schedules (status, next_run_at);
