create table if not exists public.ai_workflow_actions (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    action_id text not null unique,
    decision_id text not null,
    recommendation_id text,
    action_type text not null,
    title text not null,
    description text,
    owner text,
    approval_required boolean not null default true,
    approval_status text not null default 'Pending',
    execution_status text not null default 'Not Started',
    automation_eligible boolean not null default false,
    risk_level text not null default 'Medium',
    confidence integer not null default 0,
    expected_savings numeric(14,2) not null default 0,
    expected_risk_reduction numeric(6,2) not null default 0,
    payload jsonb not null default '{}'::jsonb,
    audit_trail jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_ai_workflow_actions_org_status
    on public.ai_workflow_actions (organization_id, approval_status, execution_status);

create index if not exists idx_ai_workflow_actions_org_action
    on public.ai_workflow_actions (organization_id, action_id);

alter table public.ai_workflow_actions
    add column if not exists assigned_to text,
    add column if not exists assigned_team text,
    add column if not exists assigned_role text,
    add column if not exists execution_started_at timestamptz,
    add column if not exists execution_completed_at timestamptz,
    add column if not exists validated_by text,
    add column if not exists validated_at timestamptz,
    add column if not exists evidence_url text,
    add column if not exists implementation_notes text,
    add column if not exists rollback_notes text,
    add column if not exists actual_savings numeric(14,2) not null default 0,
    add column if not exists actual_risk_reduction numeric(6,2) not null default 0,
    add column if not exists execution_duration_minutes integer not null default 0,
    add column if not exists last_status_change timestamptz,
    add column if not exists execution_progress integer not null default 0,
    add column if not exists automation_readiness text not null default 'Manual';

create table if not exists public.workflow_execution_history (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    action_id text not null,
    from_status text,
    to_status text not null,
    event_type text not null,
    actor text,
    message text,
    evidence_url text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_workflow_execution_history_org_action
    on public.workflow_execution_history (organization_id, action_id, created_at);

create index if not exists idx_ai_workflow_actions_lifecycle
    on public.ai_workflow_actions (organization_id, execution_status, assigned_team);
