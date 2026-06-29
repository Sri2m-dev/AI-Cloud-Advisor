create table if not exists public.enterprise_correlation_events (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    event_type text not null,
    title text not null,
    description text not null default '',
    source_system text not null,
    external_id text not null default '',
    severity text not null default 'Medium',
    confidence_score numeric(6,2) not null default 100,
    occurred_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_enterprise_correlation_events_org_type
    on public.enterprise_correlation_events (organization_id, event_type, occurred_at desc);

create index if not exists idx_enterprise_correlation_events_source
    on public.enterprise_correlation_events (organization_id, source_system, external_id);

create table if not exists public.enterprise_correlation_event_entities (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    event_id uuid not null references public.enterprise_correlation_events(id) on delete cascade,
    entity_id uuid not null references public.enterprise_entities(id) on delete cascade,
    created_at timestamptz not null default now(),
    unique (event_id, entity_id)
);

create index if not exists idx_enterprise_correlation_event_entities_entity
    on public.enterprise_correlation_event_entities (entity_id, created_at desc);

create table if not exists public.enterprise_correlation_rules (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid,
    name text not null,
    pattern_type text not null,
    description text not null default '',
    event_types text[] not null default array[]::text[],
    minimum_events integer not null default 2,
    lookback_hours integer not null default 72,
    confidence_weight numeric(6,2) not null default 1,
    conditions jsonb not null default '[]'::jsonb,
    active boolean not null default true,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_enterprise_correlation_rules_active
    on public.enterprise_correlation_rules (active, pattern_type);

create table if not exists public.enterprise_correlation_results (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    pattern_type text not null,
    summary text not null,
    confidence_score numeric(6,2) not null default 0,
    severity text not null default 'Medium',
    evidence jsonb not null default '[]'::jsonb,
    recommended_actions jsonb not null default '[]'::jsonb,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_enterprise_correlation_results_org_pattern
    on public.enterprise_correlation_results (organization_id, pattern_type, created_at desc);

create table if not exists public.enterprise_correlation_result_events (
    id uuid primary key default gen_random_uuid(),
    result_id uuid not null references public.enterprise_correlation_results(id) on delete cascade,
    event_id uuid not null references public.enterprise_correlation_events(id) on delete cascade,
    created_at timestamptz not null default now(),
    unique (result_id, event_id)
);

create table if not exists public.enterprise_correlation_result_entities (
    id uuid primary key default gen_random_uuid(),
    result_id uuid not null references public.enterprise_correlation_results(id) on delete cascade,
    entity_id uuid not null references public.enterprise_entities(id) on delete cascade,
    created_at timestamptz not null default now(),
    unique (result_id, entity_id)
);

create index if not exists idx_enterprise_correlation_result_entities_entity
    on public.enterprise_correlation_result_entities (entity_id, created_at desc);
