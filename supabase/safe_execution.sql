create table if not exists public.execution_job (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    workflow_id uuid,
    authorization_status text not null default 'NOT AUTHORIZED',
    execution_mode text not null default 'Mock',
    adapter_name text not null default 'mock',
    status text not null default 'Queued',
    progress integer not null default 0,
    execution_report jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.execution_stage (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    job_id uuid not null,
    workflow_id uuid,
    stage_name text not null,
    status text not null,
    adapter_name text not null,
    stage_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.execution_log (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    job_id uuid,
    workflow_id uuid,
    event_type text not null,
    event_payload jsonb not null default '{}'::jsonb,
    sequence integer not null default 0,
    created_at timestamptz not null default now()
);

create table if not exists public.execution_result (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    job_id uuid not null,
    workflow_id uuid,
    status text not null,
    result_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.validation_result (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    job_id uuid not null,
    workflow_id uuid,
    check_name text not null,
    status text not null,
    metric text,
    result_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.rollback_execution (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    job_id uuid not null,
    workflow_id uuid,
    trigger_name text,
    status text not null,
    rollback_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.execution_queue (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    job_id uuid not null,
    workflow_id uuid,
    queue_status text not null default 'Queued',
    priority text not null default 'Normal',
    created_at timestamptz not null default now()
);

create table if not exists public.adapter_registry (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid,
    adapter_name text not null,
    enabled boolean not null default false,
    supported_modes jsonb not null default '[]'::jsonb,
    status text not null default 'Execution Disabled',
    created_at timestamptz not null default now()
);

create index if not exists idx_execution_job_org_status
    on public.execution_job (organization_id, status, created_at desc);

create index if not exists idx_execution_stage_org_job
    on public.execution_stage (organization_id, job_id, created_at);

create index if not exists idx_execution_log_org_job
    on public.execution_log (organization_id, job_id, sequence);

create index if not exists idx_execution_result_org_job
    on public.execution_result (organization_id, job_id, created_at desc);

create index if not exists idx_validation_result_org_job
    on public.validation_result (organization_id, job_id, status);

create index if not exists idx_rollback_execution_org_job
    on public.rollback_execution (organization_id, job_id, created_at desc);

create index if not exists idx_execution_queue_org_status
    on public.execution_queue (organization_id, queue_status, created_at desc);

create index if not exists idx_adapter_registry_name
    on public.adapter_registry (adapter_name, enabled);
