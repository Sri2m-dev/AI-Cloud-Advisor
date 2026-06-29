create table if not exists public.entity_metadata_catalog (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    entity_id uuid not null references public.enterprise_entities(id) on delete cascade,
    source_system text not null,
    sync_time timestamptz not null,
    steward_id uuid,
    owner_id uuid,
    confidence_score numeric(6,2) not null default 100,
    completeness_score numeric(6,2) not null default 100,
    freshness_score numeric(6,2) not null default 100,
    source_coverage numeric(6,2) not null default 0,
    owner_coverage numeric(6,2) not null default 0,
    relationship_coverage numeric(6,2) not null default 0,
    lineage_depth integer not null default 0,
    staleness_days integer not null default 0,
    freshness_status text not null default 'Current',
    provenance_id uuid,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_entity_metadata_catalog_entity
    on public.entity_metadata_catalog (entity_id, sync_time desc);

create index if not exists idx_entity_metadata_catalog_freshness
    on public.entity_metadata_catalog (organization_id, freshness_status, staleness_days desc);

create index if not exists idx_entity_metadata_catalog_confidence
    on public.entity_metadata_catalog (organization_id, confidence_score);

create table if not exists public.entity_lineage_edges (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    source_entity_id uuid not null references public.enterprise_entities(id) on delete cascade,
    target_entity_id uuid not null references public.enterprise_entities(id) on delete cascade,
    transformation text not null,
    source_system text not null default 'metadata_catalog',
    confidence_score numeric(6,2) not null default 100,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_entity_lineage_edges_source
    on public.entity_lineage_edges (source_entity_id);

create index if not exists idx_entity_lineage_edges_target
    on public.entity_lineage_edges (target_entity_id);

create table if not exists public.entity_data_quality_assessments (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    entity_id uuid not null references public.enterprise_entities(id) on delete cascade,
    completeness_score numeric(6,2) not null default 0,
    freshness_score numeric(6,2) not null default 0,
    confidence_score numeric(6,2) not null default 0,
    lineage_depth integer not null default 0,
    source_coverage numeric(6,2) not null default 0,
    owner_coverage numeric(6,2) not null default 0,
    relationship_coverage numeric(6,2) not null default 0,
    staleness_days integer not null default 0,
    freshness_status text not null default 'Unknown',
    overall_score numeric(6,2) generated always as (
        least(
            100,
            greatest(
                0,
                completeness_score * 0.25
                + freshness_score * 0.20
                + confidence_score * 0.20
                + source_coverage * 0.15
                + owner_coverage * 0.10
                + relationship_coverage * 0.10
            )
        )
    ) stored,
    issues jsonb not null default '[]'::jsonb,
    metadata jsonb not null default '{}'::jsonb,
    assessed_at timestamptz not null default now()
);

create index if not exists idx_entity_data_quality_assessments_entity
    on public.entity_data_quality_assessments (entity_id, assessed_at desc);

create table if not exists public.entity_provenance_records (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    entity_id uuid not null references public.enterprise_entities(id) on delete cascade,
    source_system text not null,
    source_record_id text not null default '',
    source_uri text not null default '',
    operation text not null,
    actor_id uuid,
    captured_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_entity_provenance_records_entity
    on public.entity_provenance_records (entity_id, captured_at desc);
