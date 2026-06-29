create table if not exists public.execution_log (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    workflow_id text not null,
    simulation_result jsonb not null default '{}'::jsonb,
    execution_result jsonb not null default '{}'::jsonb,
    start_time timestamptz,
    end_time timestamptz,
    duration integer not null default 0,
    executor text,
    provider text,
    resource text,
    before_state jsonb not null default '{}'::jsonb,
    after_state jsonb not null default '{}'::jsonb,
    rollback jsonb not null default '{}'::jsonb,
    status text not null default 'PENDING',
    projected_savings numeric(14,2) not null default 0,
    actual_savings numeric(14,2) not null default 0,
    savings_variance_percent numeric(6,2) not null default 0,
    confidence numeric(6,2) not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_execution_log_org_workflow
    on public.execution_log (organization_id, workflow_id, created_at);

create index if not exists idx_execution_log_status
    on public.execution_log (organization_id, status, provider);
