create table if not exists public.enterprise_connector_registry (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    connector_name text not null,
    category text not null,
    version text not null default '1.0',
    authentication_type text not null,
    status text not null default 'Not Configured',
    health integer not null default 0,
    certification_level text not null default 'Uncertified',
    coverage jsonb not null default '{}'::jsonb,
    enabled boolean not null default false,
    last_sync timestamptz,
    next_sync timestamptz,
    sync_schedule text not null default 'Daily',
    credential_ref text,
    records_synced integer not null default 0,
    error_count integer not null default 0,
    last_error text,
    configured_by text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (organization_id, connector_name)
);

create table if not exists public.connector_credential_vault (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    connector_name text not null,
    secret_ref text not null,
    fingerprint text not null,
    masked_keys jsonb not null default '[]'::jsonb,
    secret_payload jsonb not null default '{}'::jsonb,
    provider text not null default 'Supabase encrypted secrets',
    status text not null default 'Active',
    created_at timestamptz not null default now(),
    unique (organization_id, connector_name)
);

create table if not exists public.connector_sync_run (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    connector_name text not null,
    status text not null default 'PENDING',
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    duration_seconds numeric(12,2) not null default 0,
    records_synced integer not null default 0,
    raw_records integer not null default 0,
    normalized_records integer not null default 0,
    fabric_records integer not null default 0,
    error_message text,
    sync_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.enterprise_data_fabric (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    fabric_key text not null,
    source_system text not null,
    source_record_id text not null,
    entity_type text not null,
    display_name text not null,
    raw_payload jsonb not null default '{}'::jsonb,
    normalized_payload jsonb not null default '{}'::jsonb,
    business_context jsonb not null default '{}'::jsonb,
    relationship_hints jsonb not null default '[]'::jsonb,
    quality_score integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (organization_id, fabric_key)
);

create table if not exists public.connector_quality_event (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    connector_name text not null,
    event_type text not null,
    duplicate_records integer not null default 0,
    missing_fields integer not null default 0,
    failed_syncs integer not null default 0,
    api_throttling integer not null default 0,
    authentication_failures integer not null default 0,
    mapping_failures integer not null default 0,
    relationship_coverage numeric(6,2) not null default 0,
    sync_latency_seconds numeric(12,2) not null default 0,
    details jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.connector_schedule (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    connector_name text not null,
    schedule_name text not null default 'Daily',
    next_sync timestamptz,
    enabled boolean not null default true,
    created_at timestamptz not null default now(),
    unique (organization_id, connector_name)
);

create table if not exists public.connector_webhook (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    connector_name text not null,
    event_type text not null default 'sync',
    secret_ref text not null,
    status text not null default 'Registered',
    created_at timestamptz not null default now()
);

create table if not exists public.connector_certification (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    connector_name text not null,
    connector_version text not null,
    status text not null,
    authentication text not null,
    last_sync timestamptz,
    next_sync timestamptz,
    records_synced integer not null default 0,
    sync_duration numeric(12,2) not null default 0,
    coverage jsonb not null default '{}'::jsonb,
    health_score integer not null default 0,
    certification_level text not null default 'Uncertified',
    details jsonb not null default '{}'::jsonb,
    certified_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    unique (organization_id, connector_name, connector_version)
);

create table if not exists public.connector_discovery (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    connector_name text not null,
    discovery_type text not null,
    entity_name text not null,
    entity_id text,
    region text,
    status text not null default 'Discovered',
    payload jsonb not null default '{}'::jsonb,
    discovered_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create table if not exists public.connector_resource_summary (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    connector_name text not null,
    resource_type text not null,
    resource_count integer not null default 0,
    region text,
    health_score integer not null default 0,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (organization_id, connector_name, resource_type, region)
);

create table if not exists public.connector_api_usage (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    connector_name text not null,
    api_name text not null,
    quota_used numeric(6,2) not null default 0,
    quota_limit integer,
    calls integer not null default 0,
    throttled_calls integer not null default 0,
    measured_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create table if not exists public.connector_certification_history (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    connector_name text not null,
    connector_version text not null,
    certification_level text not null,
    health_score integer not null default 0,
    coverage jsonb not null default '{}'::jsonb,
    status text not null,
    certified_at timestamptz not null default now(),
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.connector_health_metrics (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    connector_name text not null,
    health_score integer not null default 0,
    authentication_status text,
    sync_status text,
    data_freshness text,
    records_discovered integer not null default 0,
    sync_duration numeric(12,2) not null default 0,
    error_count integer not null default 0,
    measured_at timestamptz not null default now(),
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_enterprise_connector_registry_org_status
    on public.enterprise_connector_registry (organization_id, status, health);

create index if not exists idx_connector_credential_vault_org_connector
    on public.connector_credential_vault (organization_id, connector_name);

create index if not exists idx_connector_sync_run_org_connector
    on public.connector_sync_run (organization_id, connector_name, started_at desc);

create index if not exists idx_enterprise_data_fabric_org_source
    on public.enterprise_data_fabric (organization_id, source_system, entity_type);

create index if not exists idx_connector_quality_event_org_connector
    on public.connector_quality_event (organization_id, connector_name, created_at desc);

create index if not exists idx_connector_schedule_org_next
    on public.connector_schedule (organization_id, enabled, next_sync);

create index if not exists idx_connector_webhook_org_connector
    on public.connector_webhook (organization_id, connector_name, event_type);

create index if not exists idx_connector_certification_org_level
    on public.connector_certification (organization_id, certification_level, health_score);

create index if not exists idx_connector_discovery_org_connector
    on public.connector_discovery (organization_id, connector_name, discovery_type, created_at desc);

create index if not exists idx_connector_resource_summary_org_connector
    on public.connector_resource_summary (organization_id, connector_name, resource_type);

create index if not exists idx_connector_api_usage_org_connector
    on public.connector_api_usage (organization_id, connector_name, api_name, measured_at desc);

create index if not exists idx_connector_certification_history_org_connector
    on public.connector_certification_history (organization_id, connector_name, certified_at desc);

create index if not exists idx_connector_health_metrics_org_connector
    on public.connector_health_metrics (organization_id, connector_name, measured_at desc);
