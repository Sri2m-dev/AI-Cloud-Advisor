create table if not exists public.workflow_blueprint (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    goal_id uuid,
    goal_text text not null,
    template_name text,
    status text not null default 'Blueprint Ready',
    stage_count integer not null default 0,
    task_count integer not null default 0,
    approval_count integer not null default 0,
    estimated_duration text,
    business_risk text,
    confidence numeric(6,2) not null default 0,
    execution_enabled boolean not null default false,
    executive_summary text,
    blueprint_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.workflow_stage (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    workflow_id uuid not null,
    stage_number integer not null,
    stage_name text not null,
    description text,
    owner text,
    status text not null default 'Planned',
    created_at timestamptz not null default now()
);

create table if not exists public.workflow_task (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    workflow_id uuid not null,
    stage_name text not null,
    task_number integer not null,
    task_name text not null,
    description text,
    owner text,
    estimated_duration text,
    success_criteria text,
    rollback_action text,
    status text not null default 'Planned',
    created_at timestamptz not null default now()
);

create table if not exists public.workflow_dependency (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    workflow_id uuid not null,
    task_name text not null,
    depends_on text not null,
    dependency_type text not null default 'Sequential',
    created_at timestamptz not null default now()
);

create table if not exists public.workflow_approval (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    workflow_id uuid not null,
    approver_role text not null,
    approver text,
    approval_stage text not null default 'Approval',
    required boolean not null default true,
    policy_reason text,
    status text not null default 'Pending',
    created_at timestamptz not null default now()
);

create table if not exists public.workflow_validation (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    workflow_id uuid not null,
    check_name text not null,
    metric text,
    success_criteria text,
    owner text,
    status text not null default 'Planned',
    created_at timestamptz not null default now()
);

create table if not exists public.workflow_rollback (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    workflow_id uuid not null,
    trigger_name text not null,
    rollback_task text not null,
    verification text,
    business_validation text,
    closure text,
    created_at timestamptz not null default now()
);

create table if not exists public.workflow_template (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid,
    template_name text not null,
    description text,
    category text,
    stage_pattern jsonb not null default '[]'::jsonb,
    task_pattern jsonb not null default '[]'::jsonb,
    approval_pattern jsonb not null default '[]'::jsonb,
    enabled boolean not null default true,
    created_at timestamptz not null default now()
);

create index if not exists idx_workflow_blueprint_org_created
    on public.workflow_blueprint (organization_id, created_at desc);

create index if not exists idx_workflow_stage_org_workflow
    on public.workflow_stage (organization_id, workflow_id, stage_number);

create index if not exists idx_workflow_task_org_workflow
    on public.workflow_task (organization_id, workflow_id, task_number);

create index if not exists idx_workflow_dependency_org_workflow
    on public.workflow_dependency (organization_id, workflow_id);

create index if not exists idx_workflow_approval_org_workflow
    on public.workflow_approval (organization_id, workflow_id, status);

create index if not exists idx_workflow_validation_org_workflow
    on public.workflow_validation (organization_id, workflow_id);

create index if not exists idx_workflow_rollback_org_workflow
    on public.workflow_rollback (organization_id, workflow_id);

create index if not exists idx_workflow_template_enabled
    on public.workflow_template (enabled, template_name);
