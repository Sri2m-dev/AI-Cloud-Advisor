create table if not exists public.scheduler_job (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    connector text not null,
    job_type text not null default 'Connector Sync',
    schedule text not null default 'Manual',
    priority integer not null default 5,
    status text not null default 'Queued',
    dependencies jsonb not null default '[]'::jsonb,
    retry_count integer not null default 0,
    max_retries integer not null default 3,
    next_run_at timestamptz,
    last_run_at timestamptz,
    started_at timestamptz,
    records_synced integer not null default 0,
    last_duration_ms numeric(12,2) not null default 0,
    failure_reason text,
    last_error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_scheduler_job_org_status
    on public.scheduler_job (organization_id, status);

create index if not exists idx_scheduler_job_org_next_run
    on public.scheduler_job (organization_id, next_run_at);

create table if not exists public.scheduler_run (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    job_id uuid,
    connector text not null,
    status text not null,
    started_at timestamptz,
    completed_at timestamptz,
    duration_ms numeric(12,2) not null default 0,
    records_synced integer not null default 0,
    error text,
    created_at timestamptz not null default now()
);

create index if not exists idx_scheduler_run_org_connector
    on public.scheduler_run (organization_id, connector, created_at desc);

create table if not exists public.scheduler_retry (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    job_id uuid,
    connector text not null,
    retry_count integer not null,
    failure_reason text,
    last_error text,
    next_retry_at timestamptz,
    status text not null default 'Retrying',
    created_at timestamptz not null default now()
);

create index if not exists idx_scheduler_retry_org_job
    on public.scheduler_retry (organization_id, job_id, created_at desc);

create table if not exists public.scheduler_dead_letter (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    job_id uuid,
    connector text not null,
    failure_reason text,
    retry_count integer not null default 0,
    last_error text,
    recommended_action text,
    created_at timestamptz not null default now()
);

create index if not exists idx_scheduler_dead_letter_org_connector
    on public.scheduler_dead_letter (organization_id, connector, created_at desc);

create table if not exists public.scheduler_dependency (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    stage text not null,
    connectors jsonb not null default '[]'::jsonb,
    execution_order integer not null,
    updated_at timestamptz not null default now(),
    unique (organization_id, stage)
);

create table if not exists public.scheduler_rate_limit (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    connector text not null,
    limit_type text not null,
    max_concurrency integer not null default 1,
    window_seconds integer not null default 60,
    description text,
    updated_at timestamptz not null default now(),
    unique (organization_id, connector)
);

create table if not exists public.scheduler_operation_log (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    job_id uuid,
    connector text,
    operation text not null,
    status text not null,
    message text,
    created_at timestamptz not null default now()
);

create index if not exists idx_scheduler_operation_log_org_created
    on public.scheduler_operation_log (organization_id, created_at desc);
