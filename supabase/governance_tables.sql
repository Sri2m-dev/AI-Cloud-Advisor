create table if not exists public.governance_score_history (
    id uuid primary key,
    org_id text not null,
    tenant_id text,
    raw_score numeric not null,
    smoothed_score numeric not null,
    score_model_version text not null default 'v2_weighted_stable',
    weights jsonb not null default '{}'::jsonb,
    components jsonb not null default '{}'::jsonb,
    recorded_at timestamptz not null default now()
);

create index if not exists idx_governance_score_history_org_recorded
    on public.governance_score_history (org_id, recorded_at desc);
