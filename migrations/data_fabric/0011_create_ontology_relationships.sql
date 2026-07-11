-- P3 Data Fabric migration 0011
-- Purpose: create mutable ontology relationship current-state table.
-- Safety: non-destructive create-if-absent migration; no credentials.
create table if not exists data_fabric.ontology_relationships (
    relationship_id uuid primary key,
    source_concept_id text not null,
    target_concept_id text not null,
    relationship_type text not null,
    organization_id text not null,
    tenant_id text not null,
    attributes jsonb not null default '{}'::jsonb,
    active boolean not null default true,
    revision integer not null default 1,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    deactivated_at timestamptz,
    schema_version integer not null default 1,
    constraint ontology_relationships_distinct check (source_concept_id <> target_concept_id),
    constraint ontology_relationships_revision_positive check (revision > 0),
    constraint ontology_relationships_deactivation_consistency check (active = true or deactivated_at is not null)
);
create unique index if not exists ontology_relationships_active_unique_idx on data_fabric.ontology_relationships (organization_id, tenant_id, source_concept_id, target_concept_id, relationship_type) where active = true;
create index if not exists ontology_relationships_source_idx on data_fabric.ontology_relationships (organization_id, tenant_id, source_concept_id);
create index if not exists ontology_relationships_target_idx on data_fabric.ontology_relationships (organization_id, tenant_id, target_concept_id);
alter table data_fabric.ontology_relationships enable row level security;
comment on table data_fabric.ontology_relationships is 'P3 ontology relationships table. RLS enabled with no anonymous policy. No cascade delete of semantic mappings or history is configured.';
