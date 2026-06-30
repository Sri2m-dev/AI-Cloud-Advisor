create table if not exists public.business_digital_twins (
    id uuid primary key,
    organization_id uuid not null,
    name text not null default 'Business Digital Twin',
    version text not null default '1.0.0',
    generated_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.business_digital_twin_nodes (
    id uuid primary key,
    twin_id uuid not null references public.business_digital_twins(id) on delete cascade,
    organization_id uuid not null,
    entity_id uuid not null,
    parent_entity_id uuid,
    display_name text not null,
    entity_type text not null,
    level text not null,
    owner_id uuid,
    cost numeric(14,2) not null default 0,
    risk_score numeric(6,2) not null default 0,
    health_score numeric(6,2) not null default 100,
    dependency_entity_ids uuid[] not null default '{}',
    technology_entity_ids uuid[] not null default '{}',
    vendor_entity_ids uuid[] not null default '{}',
    kpis jsonb not null default '{}'::jsonb,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.business_digital_twin_edges (
    id uuid primary key,
    twin_id uuid not null references public.business_digital_twins(id) on delete cascade,
    source_entity_id uuid not null,
    target_entity_id uuid not null,
    relationship_type text not null,
    strength text not null default 'Medium',
    confidence_score numeric(6,4) not null default 1,
    metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_business_digital_twins_org_generated
    on public.business_digital_twins (organization_id, generated_at desc);

create index if not exists idx_business_digital_twin_nodes_twin_level
    on public.business_digital_twin_nodes (twin_id, level);

create index if not exists idx_business_digital_twin_nodes_entity
    on public.business_digital_twin_nodes (entity_id);

create index if not exists idx_business_digital_twin_edges_twin_source
    on public.business_digital_twin_edges (twin_id, source_entity_id);

create index if not exists idx_business_digital_twin_edges_twin_target
    on public.business_digital_twin_edges (twin_id, target_entity_id);
