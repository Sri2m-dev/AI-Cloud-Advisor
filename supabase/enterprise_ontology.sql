create table if not exists public.enterprise_relationship_definitions (
    relationship_type text primary key,
    relationship_group text not null,
    description text not null default '',
    inverse_relationship_type text,
    direction text not null default 'Forward',
    default_strength text not null default 'Medium',
    ontology_version text not null default '1.2.1',
    is_canonical boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_enterprise_relationship_definitions_group
    on public.enterprise_relationship_definitions (relationship_group);

create table if not exists public.enterprise_relationship_rules (
    id uuid primary key default gen_random_uuid(),
    relationship_type text not null references public.enterprise_relationship_definitions(relationship_type) on delete cascade,
    source_entity_types text[] not null,
    target_entity_types text[] not null,
    cardinality text not null default 'N..N',
    max_targets_per_source integer,
    max_sources_per_target integer,
    direction text not null default 'Forward',
    default_strength text not null default 'Medium',
    ontology_version text not null default '1.2.1',
    description text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_enterprise_relationship_rules_type
    on public.enterprise_relationship_rules (relationship_type);

create table if not exists public.enterprise_relationship_validation_events (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid,
    relationship_type text not null,
    source_entity_id uuid,
    source_entity_type text not null,
    target_entity_id uuid,
    target_entity_type text not null,
    is_valid boolean not null,
    validation_message text not null default '',
    cardinality text,
    direction text,
    relationship_strength text,
    ontology_version text not null default '1.2.1',
    source_system text not null default 'manual',
    created_at timestamptz not null default now()
);

create index if not exists idx_enterprise_relationship_validation_events_type
    on public.enterprise_relationship_validation_events (relationship_type, is_valid);

alter table if exists public.enterprise_entity_relationships
    add column if not exists created_by uuid,
    add column if not exists last_verified timestamptz,
    add column if not exists verification_method text not null default 'unverified',
    add column if not exists status text not null default 'Pending',
    add column if not exists strength text not null default 'Medium',
    add column if not exists direction text not null default 'Forward',
    add column if not exists ontology_version text not null default '1.2.1';
