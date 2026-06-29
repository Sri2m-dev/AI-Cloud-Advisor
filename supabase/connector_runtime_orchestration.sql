create table if not exists public.enterprise_connector_execution_runs (
    id uuid primary key default gen_random_uuid(),
    connector_id uuid not null references public.enterprise_connectors(id) on delete cascade,
    operation text not null,
    trigger_type text not null default 'Scheduled',
    status text not null default 'Queued',
    attempt integer not null default 1,
    max_attempts integer not null default 1,
    checkpoint_id uuid,
    result_id uuid,
    health_id uuid,
    started_at timestamptz,
    completed_at timestamptz,
    message text not null default '',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_enterprise_connector_execution_runs_connector
    on public.enterprise_connector_execution_runs (connector_id, created_at desc);

create index if not exists idx_enterprise_connector_execution_runs_status
    on public.enterprise_connector_execution_runs (status, created_at desc);

create table if not exists public.enterprise_connector_run_logs (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null references public.enterprise_connector_execution_runs(id) on delete cascade,
    connector_id uuid not null references public.enterprise_connectors(id) on delete cascade,
    operation text not null default '',
    level text not null default 'Info',
    message text not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_enterprise_connector_run_logs_run
    on public.enterprise_connector_run_logs (run_id, created_at);

create table if not exists public.enterprise_connector_sync_checkpoints (
    id uuid primary key default gen_random_uuid(),
    connector_id uuid not null references public.enterprise_connectors(id) on delete cascade,
    operation text not null,
    cursor text not null default '',
    high_watermark text not null default '',
    records_processed integer not null default 0,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (connector_id, operation)
);

create table if not exists public.enterprise_connector_retry_policies (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    max_attempts integer not null default 3,
    initial_delay_seconds integer not null default 30,
    backoff_strategy text not null default 'Exponential',
    retry_on_statuses text[] not null default array['Failed']::text[],
    metadata jsonb not null default '{}'::jsonb
);
