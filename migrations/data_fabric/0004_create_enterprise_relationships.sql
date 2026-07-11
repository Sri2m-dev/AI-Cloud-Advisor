-- P3 Data Fabric migration 0004
-- Purpose: create canonical enterprise relationship current-state table.
-- Safety: non-destructive create-if-absent migration; no credentials.

create table if not exists data_fabric.enterprise_relationships (
    id uuid primary key,
    source_entity_id uuid not null,
    target_entity_id uuid not null,
    relationship_type text not null,
    organization_id text not null,
    tenant_id text not null,
    source_system text,
    source_identifier text,
    confidence_score numeric,
    quality_score numeric,
    metadata jsonb not null default '{}'::jsonb,
    active boolean not null default true,
    revision integer not null default 1,
    version integer not null default 1,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    deactivated_at timestamptz,
    deactivated_by text,
    created_by text,
    updated_by text,
    schema_version integer not null default 1,
    constraint enterprise_relationships_distinct_endpoints check (source_entity_id <> target_entity_id),
    constraint enterprise_relationships_confidence_score_range check (confidence_score is null or (confidence_score >= 0 and confidence_score <= 100)),
    constraint enterprise_relationships_quality_score_range check (quality_score is null or (quality_score >= 0 and quality_score <= 100)),
    constraint enterprise_relationships_revision_positive check (revision > 0),
    constraint enterprise_relationships_version_positive check (version > 0),
    constraint enterprise_relationships_timestamp_order check (updated_at >= created_at),
    constraint enterprise_relationships_deactivation_consistency check (active = true or deactivated_at is not null)
);

create unique index if not exists enterprise_relationships_active_unique_idx
    on data_fabric.enterprise_relationships (organization_id, tenant_id, source_entity_id, target_entity_id, relationship_type)
    where active = true;

create index if not exists enterprise_relationships_tenant_idx
    on data_fabric.enterprise_relationships (organization_id, tenant_id);

create index if not exists enterprise_relationships_tenant_source_idx
    on data_fabric.enterprise_relationships (organization_id, tenant_id, source_entity_id);

create index if not exists enterprise_relationships_tenant_target_idx
    on data_fabric.enterprise_relationships (organization_id, tenant_id, target_entity_id);

create index if not exists enterprise_relationships_tenant_type_idx
    on data_fabric.enterprise_relationships (organization_id, tenant_id, relationship_type);

create index if not exists enterprise_relationships_tenant_active_idx
    on data_fabric.enterprise_relationships (organization_id, tenant_id, active);

create index if not exists enterprise_relationships_updated_at_idx
    on data_fabric.enterprise_relationships (updated_at);

alter table data_fabric.enterprise_relationships enable row level security;

comment on table data_fabric.enterprise_relationships is 'P3 Data Fabric canonical relationship current-state table. RLS is enabled with no anonymous policy; server-side service-role use is confined to reviewed adapters and repositories still apply tenant filters.';
comment on column data_fabric.enterprise_relationships.source_entity_id is 'No foreign key is declared in P3.14 because the P3.13 entity table stores text IDs while this relationship schema is UUID based. Cascade delete is intentionally not used.';
