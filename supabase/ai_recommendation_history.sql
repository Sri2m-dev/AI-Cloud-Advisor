create table if not exists public.ai_recommendation_history (
    recommendation_id text primary key,
    organization_id uuid not null,
    category text not null,
    priority text not null,
    severity text not null,
    title text not null,
    description text,
    recommendation text not null,
    business_impact text,
    technical_impact text,
    estimated_savings numeric(14,2) not null default 0,
    estimated_risk_reduction numeric(6,2) not null default 0,
    owner text,
    confidence integer not null default 0,
    overall_score numeric(6,2) not null default 0,
    source text not null default 'AI Recommendation Engine',
    evidence jsonb not null default '{}'::jsonb,
    related_assets jsonb not null default '[]'::jsonb,
    related_applications jsonb not null default '[]'::jsonb,
    related_capabilities jsonb not null default '[]'::jsonb,
    status text not null default 'Open',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_ai_recommendation_history_org_priority
    on public.ai_recommendation_history (organization_id, priority, status);

create index if not exists idx_ai_recommendation_history_org_created
    on public.ai_recommendation_history (organization_id, created_at desc);
