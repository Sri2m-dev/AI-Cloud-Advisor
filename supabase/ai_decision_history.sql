create table if not exists public.ai_decision_history (
    decision_id text primary key,
    recommendation_id text not null,
    organization_id uuid not null,
    decision text not null,
    priority text not null,
    confidence integer not null default 0,
    automation_eligible boolean not null default false,
    approval_required text not null default 'None',
    owner text,
    risk_score numeric(6,2) not null default 0,
    business_score numeric(6,2) not null default 0,
    technical_score numeric(6,2) not null default 0,
    financial_score numeric(6,2) not null default 0,
    operational_score numeric(6,2) not null default 0,
    security_score numeric(6,2) not null default 0,
    compliance_score numeric(6,2) not null default 0,
    governance_score numeric(6,2) not null default 0,
    customer_score numeric(6,2) not null default 0,
    complexity_score numeric(6,2) not null default 0,
    urgency_score numeric(6,2) not null default 0,
    overall_score numeric(6,2) not null default 0,
    expected_savings numeric(14,2) not null default 0,
    expected_risk_reduction numeric(6,2) not null default 0,
    expected_success numeric(6,2) not null default 0,
    rollback_available boolean not null default true,
    status text not null default 'Pending Execution',
    explanation jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_ai_decision_history_org_priority
    on public.ai_decision_history (organization_id, priority, status);

create index if not exists idx_ai_decision_history_org_created
    on public.ai_decision_history (organization_id, created_at desc);
