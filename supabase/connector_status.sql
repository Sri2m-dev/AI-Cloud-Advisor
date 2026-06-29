create table if not exists public.connector_status (
    id uuid primary key default gen_random_uuid(),
    connector_name text not null,
    status text not null default 'NOT_CONFIGURED',
    last_sync timestamptz,
    objects_synced integer not null default 0,
    sync_frequency text not null default 'DAILY',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists idx_connector_status_name
    on public.connector_status (connector_name);

insert into public.connector_status (
    connector_name,
    status,
    last_sync,
    objects_synced,
    sync_frequency,
    metadata
)
values
    ('AWS', 'CONNECTED', now() - interval '5 minutes', 1245, 'DAILY', '{"tables":["unified_cloud_costs","technology_inventory","technology_relationships","recommendations"]}'::jsonb),
    ('Azure', 'CONNECTED', now() - interval '10 minutes', 456, 'DAILY', '{"tables":["unified_cloud_costs","technology_inventory","recommendations"]}'::jsonb),
    ('GitHub', 'CONNECTED', now() - interval '1 hour', 180, 'DAILY', '{"tables":["technology_inventory","license_cost"]}'::jsonb),
    ('Microsoft 365', 'CONNECTED', now() - interval '15 minutes', 890, 'DAILY', '{"tables":["vw_inactive_saas_users","license_cost","technology_inventory"]}'::jsonb)
on conflict (connector_name) do update set
    status = excluded.status,
    last_sync = excluded.last_sync,
    objects_synced = excluded.objects_synced,
    sync_frequency = excluded.sync_frequency,
    metadata = excluded.metadata,
    updated_at = now();

