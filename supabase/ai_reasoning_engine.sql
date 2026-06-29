create table if not exists public.ai_reasoning_history (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    question text not null,
    reasoning jsonb not null default '[]'::jsonb,
    recommendation text not null,
    confidence numeric(6,2) not null default 0,
    evidence jsonb not null default '[]'::jsonb,
    policies jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.policy_rules (
    id uuid primary key default gen_random_uuid(),
    rule_name text not null,
    category text not null,
    condition text not null,
    action text not null,
    severity text not null default 'Medium',
    enabled boolean not null default true,
    created_at timestamptz not null default now()
);

create index if not exists idx_ai_reasoning_history_org_created
    on public.ai_reasoning_history (organization_id, created_at desc);

create index if not exists idx_ai_reasoning_history_org_confidence
    on public.ai_reasoning_history (organization_id, confidence desc);

create index if not exists idx_policy_rules_enabled_category
    on public.policy_rules (enabled, category);

insert into public.policy_rules (rule_name, category, condition, action, severity, enabled)
values
    (
        'CAB approval for critical revenue systems',
        'Governance',
        'risk_score >= 70 and revenue_exposure_per_day >= 1000000',
        'Require CAB approval before execution.',
        'Critical',
        true
    ),
    (
        'Reject uneconomic migrations',
        'Financial',
        'expected_savings < migration_cost',
        'Reject or redesign the recommendation because migration cost exceeds expected savings.',
        'High',
        true
    ),
    (
        'Block automation for compliance exposure',
        'Security',
        'compliance_risk >= 70',
        'Block autonomous execution and route to security and compliance review.',
        'High',
        true
    ),
    (
        'Phase production migrations',
        'Change',
        'production_applications >= 5',
        'Use phased rollout: development, QA, then production.',
        'Medium',
        true
    ),
    (
        'Finance approval for material budget impact',
        'Finance',
        'abs_budget_impact >= 100000',
        'Require Finance approval because the budget impact is material.',
        'Medium',
        true
    )
on conflict do nothing;
