create table if not exists public.simulation_runs (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    simulation_name text not null,
    asset_id text not null,
    asset_type text not null,
    scenario text not null,
    status text not null default 'Draft',
    created_by text,
    created_at timestamptz not null default now(),
    simulation_results jsonb not null default '{}'::jsonb
);

create table if not exists public.simulation_results (
    simulation_id uuid primary key references public.simulation_runs(id) on delete cascade,
    organization_id uuid not null,
    impact_score numeric(6,2) not null default 0,
    financial_score numeric(6,2) not null default 0,
    risk_score numeric(6,2) not null default 0,
    ai_summary text,
    confidence numeric(6,2) not null default 0,
    approvals jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_simulation_runs_org_created
    on public.simulation_runs (organization_id, created_at desc);

create index if not exists idx_simulation_runs_org_status
    on public.simulation_runs (organization_id, status);

create index if not exists idx_simulation_results_org_risk
    on public.simulation_results (organization_id, risk_score desc);
