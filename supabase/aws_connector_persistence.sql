create table if not exists public.connector_registry (
    id uuid primary key default gen_random_uuid(),
    connector_name text not null,
    connector_type text not null,
    provider text not null,
    status text not null default 'NOT_CONFIGURED',
    last_sync_at timestamptz,
    last_success_at timestamptz,
    last_failure_at timestamptz,
    objects_synced integer not null default 0,
    sync_frequency text not null default 'DAILY',
    enabled boolean not null default true,
    last_error text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_connector_registry_status
    on public.connector_registry (status);

alter table if exists public.connector_registry
    add column if not exists connector_name text,
    add column if not exists connector_type text,
    add column if not exists provider text,
    add column if not exists status text default 'NOT_CONFIGURED',
    add column if not exists last_sync_at timestamptz,
    add column if not exists last_success_at timestamptz,
    add column if not exists last_failure_at timestamptz,
    add column if not exists objects_synced integer default 0,
    add column if not exists sync_frequency text default 'DAILY',
    add column if not exists enabled boolean default true,
    add column if not exists last_error text,
    add column if not exists metadata jsonb default '{}'::jsonb,
    add column if not exists updated_at timestamptz default now();

create table if not exists public.connector_sync_history (
    id uuid primary key default gen_random_uuid(),
    connector_name text not null,
    sync_status text not null,
    started_at timestamptz not null,
    completed_at timestamptz,
    duration_seconds numeric,
    accounts_synced integer not null default 0,
    costs_synced integer not null default 0,
    resources_synced integer not null default 0,
    recommendations_synced integer not null default 0,
    assets_discovered integer not null default 0,
    error_message text,
    created_at timestamptz not null default now()
);

create index if not exists idx_connector_sync_history_connector_started
    on public.connector_sync_history (connector_name, started_at desc);

alter table if exists public.connector_sync_history
    add column if not exists connector_name text,
    add column if not exists sync_status text,
    add column if not exists started_at timestamptz,
    add column if not exists completed_at timestamptz,
    add column if not exists duration_seconds numeric,
    add column if not exists accounts_synced integer default 0,
    add column if not exists costs_synced integer default 0,
    add column if not exists resources_synced integer default 0,
    add column if not exists recommendations_synced integer default 0,
    add column if not exists assets_discovered integer default 0,
    add column if not exists error_message text;

create table if not exists public.discovered_assets (
    id uuid primary key default gen_random_uuid(),
    connector_name text not null,
    provider text not null,
    asset_type text,
    asset_id text not null,
    asset_name text,
    region text,
    account_id text,
    status text,
    source_system text,
    raw_payload jsonb not null default '{}'::jsonb,
    last_seen_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists idx_discovered_assets_unique_asset
    on public.discovered_assets (connector_name, provider, asset_id);

create index if not exists idx_discovered_assets_provider_type
    on public.discovered_assets (provider, asset_type);

alter table if exists public.cloud_accounts
    add column if not exists account_id text,
    add column if not exists cloud text,
    add column if not exists status text,
    add column if not exists updated_at timestamptz default now();

create unique index if not exists idx_cloud_accounts_account_id
    on public.cloud_accounts (account_id)
    where account_id is not null;
