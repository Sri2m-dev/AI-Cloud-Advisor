create table if not exists public.enterprise_connector_certifications (
    id uuid primary key default gen_random_uuid(),
    connector_id uuid not null references public.enterprise_connectors(id) on delete cascade,
    suite_name text not null default 'Enterprise Connector Certification',
    status text not null,
    score numeric(6,2) not null default 0,
    summary text not null default '',
    checks jsonb not null default '[]'::jsonb,
    metadata jsonb not null default '{}'::jsonb,
    certified_at timestamptz not null default now()
);

create index if not exists idx_enterprise_connector_certifications_connector
    on public.enterprise_connector_certifications (connector_id, certified_at desc);

create table if not exists public.enterprise_connector_health_policies (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    healthy_score numeric(6,2) not null default 90,
    degraded_score numeric(6,2) not null default 70,
    max_error_count integer not null default 3,
    max_latency_ms integer not null default 5000,
    stale_after_hours integer not null default 24,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.enterprise_connector_health_assessments (
    id uuid primary key default gen_random_uuid(),
    connector_id uuid not null references public.enterprise_connectors(id) on delete cascade,
    policy_name text not null,
    grade text not null,
    score numeric(6,2) not null default 0,
    findings jsonb not null default '[]'::jsonb,
    metadata jsonb not null default '{}'::jsonb,
    assessed_at timestamptz not null default now()
);

create index if not exists idx_enterprise_connector_health_assessments_connector
    on public.enterprise_connector_health_assessments (connector_id, assessed_at desc);
