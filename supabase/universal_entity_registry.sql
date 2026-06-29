create table if not exists public.enterprise_entities (
    id uuid primary key,
    organization_id uuid not null,
    entity_type text not null,
    display_name text not null,
    description text not null default '',
    owner_id uuid,
    lifecycle_state text not null default 'Active',
    source_systems jsonb not null default '[]'::jsonb,
    tags jsonb not null default '{}'::jsonb,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    created_by uuid,
    updated_by uuid
);

create index if not exists idx_enterprise_entities_org_type
    on public.enterprise_entities (organization_id, entity_type);

create index if not exists idx_enterprise_entities_display_name
    on public.enterprise_entities using gin (to_tsvector('english', display_name));

create table if not exists public.enterprise_entity_relationships (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    source_entity_id uuid not null references public.enterprise_entities(id) on delete cascade,
    relationship_type text not null,
    target_entity_id uuid not null references public.enterprise_entities(id) on delete cascade,
    confidence numeric(5,2) not null default 1.0,
    source_system text not null default 'manual',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_enterprise_entity_relationships_source
    on public.enterprise_entity_relationships (source_entity_id, relationship_type);

create index if not exists idx_enterprise_entity_relationships_target
    on public.enterprise_entity_relationships (target_entity_id, relationship_type);

create table if not exists public.enterprise_entity_source_map (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    entity_id uuid not null references public.enterprise_entities(id) on delete cascade,
    source_system text not null,
    external_id text not null,
    external_name text not null default '',
    source_url text not null default '',
    attributes jsonb not null default '{}'::jsonb,
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    unique (organization_id, source_system, external_id)
);

create index if not exists idx_enterprise_entity_source_map_entity
    on public.enterprise_entity_source_map (entity_id);

