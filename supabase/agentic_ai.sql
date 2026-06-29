create table if not exists public.agent_registry (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    agent_name text not null,
    description text,
    version text not null default '1.0',
    status text not null default 'Experimental',
    capabilities jsonb not null default '[]'::jsonb,
    owner text not null default 'Enterprise AI',
    enabled boolean not null default true,
    created_at timestamptz not null default now(),
    unique (organization_id, agent_name)
);

create table if not exists public.goal_registry (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    goal_text text not null,
    classification text not null,
    target_asset text,
    status text not null default 'PLAN_READY',
    confidence numeric(6,2) not null default 0,
    created_by text not null default 'system',
    created_at timestamptz not null default now()
);

create table if not exists public.goal_execution_plan (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    goal_id uuid not null,
    plan_payload jsonb not null default '{}'::jsonb,
    estimated_savings numeric(16,2) not null default 0,
    risk text not null default 'Medium',
    approvals jsonb not null default '[]'::jsonb,
    status text not null default 'Review Ready',
    created_at timestamptz not null default now()
);

create table if not exists public.goal_task (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    goal_id uuid not null,
    task_number integer not null,
    task_name text not null,
    agent_name text not null,
    description text,
    status text not null default 'Planned',
    created_at timestamptz not null default now()
);

create table if not exists public.goal_history (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    goal_id uuid not null,
    event_type text not null,
    event_payload jsonb not null default '{}'::jsonb,
    created_by text not null default 'system',
    created_at timestamptz not null default now()
);

create table if not exists public.goal_status (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    goal_id uuid not null,
    status text not null,
    reason text,
    created_by text not null default 'system',
    created_at timestamptz not null default now()
);

create table if not exists public.agent_session (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    goal_id uuid,
    session_status text not null default 'Planning',
    started_by text not null default 'system',
    started_at timestamptz not null default now(),
    ended_at timestamptz
);

create table if not exists public.agent_plan (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    goal_id uuid not null,
    agents jsonb not null default '[]'::jsonb,
    tasks jsonb not null default '[]'::jsonb,
    status text not null default 'PLAN_READY',
    created_at timestamptz not null default now()
);

create table if not exists public.agent_execution_log (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    goal_id uuid,
    agent_name text not null,
    event_type text not null,
    event_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.agent_collaboration_session (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    goal_id uuid,
    goal_text text not null,
    status text not null default 'Collaboration Started',
    participating_agents jsonb not null default '[]'::jsonb,
    shared_context_summary jsonb not null default '{}'::jsonb,
    created_by text not null default 'system',
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists public.agent_messages (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    goal_id uuid,
    sender text not null,
    recipient text not null,
    request text not null,
    priority text not null default 'Normal',
    status text not null default 'Pending',
    message_payload jsonb not null default '{}'::jsonb,
    response_payload jsonb not null default '{}'::jsonb,
    sequence integer not null default 0,
    completed_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists public.agent_decisions (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    goal_id uuid,
    agent_name text not null,
    recommendation text not null,
    confidence numeric(6,2) not null default 0,
    risk text,
    evidence jsonb not null default '[]'::jsonb,
    blocking_issues jsonb not null default '[]'::jsonb,
    decision_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.agent_consensus (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    goal_id uuid,
    consensus_state text not null,
    enterprise_recommendation text not null,
    confidence numeric(6,2) not null default 0,
    reason text,
    agreements integer not null default 0,
    disagreements integer not null default 0,
    blocking_issues jsonb not null default '[]'::jsonb,
    consensus_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.agent_votes (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    goal_id uuid,
    agent_name text not null,
    vote text not null,
    confidence numeric(6,2) not null default 0,
    reason text,
    created_at timestamptz not null default now()
);

create table if not exists public.collaboration_history (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    goal_id uuid,
    event_type text not null,
    event_payload jsonb not null default '{}'::jsonb,
    created_by text not null default 'system',
    created_at timestamptz not null default now()
);

create table if not exists public.agent_scorecard (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    goal_id uuid,
    agent_name text not null,
    recommendation_acceptance_rate numeric(6,2) not null default 0,
    prediction_accuracy numeric(6,2) not null default 0,
    average_confidence numeric(6,2) not null default 0,
    average_execution_time text,
    contribution_frequency integer not null default 0,
    historical_success_rate numeric(6,2) not null default 0,
    created_at timestamptz not null default now()
);

create index if not exists idx_agent_registry_org_enabled
    on public.agent_registry (organization_id, enabled, status);

create index if not exists idx_goal_registry_org_status
    on public.goal_registry (organization_id, status, created_at desc);

create index if not exists idx_goal_execution_plan_org_goal
    on public.goal_execution_plan (organization_id, goal_id, created_at desc);

create index if not exists idx_goal_task_org_goal
    on public.goal_task (organization_id, goal_id, task_number);

create index if not exists idx_goal_history_org_goal
    on public.goal_history (organization_id, goal_id, created_at desc);

create index if not exists idx_goal_status_org_goal
    on public.goal_status (organization_id, goal_id, created_at desc);

create index if not exists idx_agent_session_org_goal
    on public.agent_session (organization_id, goal_id, started_at desc);

create index if not exists idx_agent_plan_org_goal
    on public.agent_plan (organization_id, goal_id, created_at desc);

create index if not exists idx_agent_execution_log_org_goal
    on public.agent_execution_log (organization_id, goal_id, created_at desc);

create index if not exists idx_agent_collaboration_session_org_status
    on public.agent_collaboration_session (organization_id, status, created_at desc);

create index if not exists idx_agent_messages_org_goal
    on public.agent_messages (organization_id, goal_id, sequence);

create index if not exists idx_agent_decisions_org_goal
    on public.agent_decisions (organization_id, goal_id, agent_name);

create index if not exists idx_agent_consensus_org_goal
    on public.agent_consensus (organization_id, goal_id, created_at desc);

create index if not exists idx_agent_votes_org_goal
    on public.agent_votes (organization_id, goal_id, agent_name);

create index if not exists idx_collaboration_history_org_goal
    on public.collaboration_history (organization_id, goal_id, created_at desc);

create index if not exists idx_agent_scorecard_org_agent
    on public.agent_scorecard (organization_id, agent_name, created_at desc);
