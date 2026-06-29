create table if not exists public.learning_outcome (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    execution_id uuid,
    workflow_id uuid,
    goal_text text,
    expected_savings numeric(14,2) not null default 0,
    actual_savings numeric(14,2) not null default 0,
    variance numeric(14,2) not null default 0,
    prediction_accuracy numeric(6,2) not null default 0,
    recommendation_quality numeric(6,2) not null default 0,
    business_impact text,
    operational_success numeric(6,2) not null default 0,
    status text not null default 'Captured',
    outcome_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.learning_insight (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    insight_type text not null default 'Outcome',
    title text not null,
    insight text not null,
    severity text not null default 'Informational',
    recommended_action text,
    created_at timestamptz not null default now()
);

create table if not exists public.recommendation_feedback (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    recommendation_id text,
    execution_id uuid,
    workflow_id uuid,
    goal_text text,
    status text not null default 'Accepted',
    successful boolean not null default false,
    expected_savings numeric(14,2) not null default 0,
    actual_savings numeric(14,2) not null default 0,
    rollback_required boolean not null default false,
    confidence_before numeric(6,2) not null default 0,
    confidence_after numeric(6,2) not null default 0,
    recommendation_quality numeric(6,2) not null default 0,
    feedback_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.workflow_feedback (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    workflow_id uuid,
    template_name text not null,
    version_before text not null default '1.0',
    version_after text not null default '1.0',
    execution_success numeric(6,2) not null default 0,
    prediction_accuracy numeric(6,2) not null default 0,
    lessons_learned jsonb not null default '[]'::jsonb,
    feedback_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.agent_feedback (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    agent_name text not null,
    execution_id uuid,
    plans_generated integer not null default 0,
    accepted boolean not null default false,
    rejected boolean not null default false,
    execution_success numeric(6,2) not null default 0,
    average_confidence numeric(6,2) not null default 0,
    learning_score numeric(6,2) not null default 0,
    feedback_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.confidence_history (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    execution_id uuid,
    metric_name text not null,
    confidence_before numeric(6,2) not null default 0,
    confidence_after numeric(6,2) not null default 0,
    confidence_delta numeric(6,2) not null default 0,
    reason text,
    created_at timestamptz not null default now()
);

create table if not exists public.template_improvement (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    template_name text not null,
    version text not null default '1.0',
    improvement_type text not null,
    lesson text not null,
    recommended_change text not null,
    source_execution_id uuid,
    status text not null default 'Recommended',
    created_at timestamptz not null default now()
);

create table if not exists public.learning_summary (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    learning_id uuid,
    summary text,
    learning_score numeric(6,2) not null default 0,
    knowledge_memory jsonb not null default '[]'::jsonb,
    summary_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.execution_metrics (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    execution_id uuid,
    metric_name text not null,
    metric_value numeric(14,2) not null default 0,
    metric_unit text,
    created_at timestamptz not null default now()
);

create index if not exists idx_learning_outcome_org_created
    on public.learning_outcome (organization_id, created_at desc);

create index if not exists idx_learning_insight_org_created
    on public.learning_insight (organization_id, created_at desc);

create index if not exists idx_recommendation_feedback_org_status
    on public.recommendation_feedback (organization_id, status, created_at desc);

create index if not exists idx_workflow_feedback_org_template
    on public.workflow_feedback (organization_id, template_name, created_at desc);

create index if not exists idx_agent_feedback_org_agent
    on public.agent_feedback (organization_id, agent_name, created_at desc);

create index if not exists idx_confidence_history_org_metric
    on public.confidence_history (organization_id, metric_name, created_at desc);

create index if not exists idx_template_improvement_org_template
    on public.template_improvement (organization_id, template_name, created_at desc);

create index if not exists idx_learning_summary_org_created
    on public.learning_summary (organization_id, created_at desc);

create index if not exists idx_execution_metrics_org_execution
    on public.execution_metrics (organization_id, execution_id, created_at desc);
