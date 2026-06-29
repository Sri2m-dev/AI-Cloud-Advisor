create table if not exists public.technology_relationships (
    id uuid primary key default gen_random_uuid(),
    source_type text not null,
    source_name text not null,
    relationship_type text not null,
    target_type text not null,
    target_name text not null,
    organization_id text,
    source_system text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table if exists public.technology_relationships
    add column if not exists source_type text,
    add column if not exists source_name text,
    add column if not exists relationship_type text,
    add column if not exists target_type text,
    add column if not exists target_name text,
    add column if not exists organization_id text,
    add column if not exists source_system text,
    add column if not exists metadata jsonb default '{}'::jsonb,
    add column if not exists updated_at timestamptz default now();

drop index if exists public.idx_technology_relationships_unique_edge;

create unique index if not exists idx_technology_relationships_org_unique_edge
    on public.technology_relationships (
        organization_id,
        source_type,
        source_name,
        relationship_type,
        target_type,
        target_name
    );

create index if not exists idx_technology_relationships_source
    on public.technology_relationships (source_type, source_name);

create index if not exists idx_technology_relationships_target
    on public.technology_relationships (target_type, target_name);
