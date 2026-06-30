create table if not exists public.technology_digital_twins (
    id uuid primary key,
    organization_id uuid not null,
    name text not null default 'Technology Digital Twin',
    version text not null default '1.0.0',
    generated_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.technology_twin_nodes (
    id uuid primary key,
    twin_id uuid not null references public.technology_digital_twins(id) on delete cascade,
    organization_id uuid not null,
    technology_id uuid not null,
    name text not null,
    technology_type text not null,
    vendor text not null default '',
    cloud_provider text not null default '',
    environment text not null default '',
    region text not null default '',
    owner_id uuid,
    business_service_ids uuid[] not null default '{}',
    application_ids uuid[] not null default '{}',
    status text not null default 'Unknown',
    risk numeric(6,2) not null default 0,
    cost numeric(14,2) not null default 0,
    monthly_cost numeric(14,2) not null default 0,
    annual_cost numeric(14,2) not null default 0,
    tags jsonb not null default '{}'::jsonb,
    lifecycle text not null default 'Active',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.technology_twin_health (
    id uuid primary key,
    twin_id uuid not null references public.technology_digital_twins(id) on delete cascade,
    technology_id uuid not null,
    availability numeric(6,2) not null default 100,
    performance numeric(6,2) not null default 100,
    capacity numeric(6,2) not null default 100,
    utilization numeric(6,2) not null default 100,
    reliability numeric(6,2) not null default 100,
    operational_score numeric(6,2) not null default 100,
    health_score numeric(6,2) not null default 100,
    assessed_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.technology_twin_state (
    id uuid primary key,
    twin_id uuid not null references public.technology_digital_twins(id) on delete cascade,
    technology_id uuid not null,
    status text not null default 'Unknown',
    health_score numeric(6,2) not null default 100,
    risk_score numeric(6,2) not null default 0,
    cost_score numeric(6,2) not null default 0,
    security_score numeric(6,2) not null default 100,
    operations_score numeric(6,2) not null default 100,
    business_impact_score numeric(6,2) not null default 0,
    last_refreshed_at timestamptz,
    metadata jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

create table if not exists public.technology_twin_relationships (
    id uuid primary key,
    twin_id uuid not null references public.technology_digital_twins(id) on delete cascade,
    source_entity_id uuid not null,
    target_entity_id uuid not null,
    relationship_type text not null,
    strength text not null default 'Medium',
    confidence_score numeric(6,4) not null default 1,
    source_system text not null default 'manual',
    metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.technology_infrastructure_resources (
    id uuid primary key,
    twin_id uuid not null references public.technology_digital_twins(id) on delete cascade,
    technology_id uuid not null,
    organization_id uuid,
    entity_id uuid,
    name text not null,
    resource_type text not null,
    provider text not null default '',
    region text not null default '',
    environment text not null default '',
    resource_id text not null default '',
    account_id text not null default '',
    owner_id uuid,
    tags jsonb not null default '{}'::jsonb,
    lifecycle_state text not null default 'Active',
    cost numeric(14,2) not null default 0,
    health numeric(6,2) not null default 100,
    risk numeric(6,2) not null default 0,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.technology_infrastructure_mappings (
    id uuid primary key,
    twin_id uuid not null references public.technology_digital_twins(id) on delete cascade,
    technology_id uuid not null,
    resource_id uuid not null,
    relationship_type text not null default 'RUNS_ON',
    confidence_score numeric(6,4) not null default 1,
    source_system text not null default 'technology_twin',
    created_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_technology_digital_twins_org_generated
    on public.technology_digital_twins (organization_id, generated_at desc);

create index if not exists idx_technology_twin_nodes_twin_type
    on public.technology_twin_nodes (twin_id, technology_type);

create index if not exists idx_technology_twin_nodes_technology
    on public.technology_twin_nodes (technology_id);

create index if not exists idx_technology_twin_state_twin_status
    on public.technology_twin_state (twin_id, status);

create index if not exists idx_technology_twin_relationships_source
    on public.technology_twin_relationships (twin_id, source_entity_id);

create index if not exists idx_technology_twin_relationships_target
    on public.technology_twin_relationships (twin_id, target_entity_id);

create index if not exists idx_technology_infrastructure_resources_technology
    on public.technology_infrastructure_resources (twin_id, technology_id);

create index if not exists idx_technology_infrastructure_resources_type
    on public.technology_infrastructure_resources (twin_id, resource_type);

create index if not exists idx_technology_infrastructure_mappings_technology
    on public.technology_infrastructure_mappings (twin_id, technology_id);
