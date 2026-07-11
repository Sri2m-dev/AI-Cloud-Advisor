-- P3 Data Fabric migration 0010
-- Purpose: create mutable ontology concept current-state table.
-- Safety: non-destructive create-if-absent migration; no credentials.
create table if not exists data_fabric.ontology_concepts (
    concept_id text not null,
    organization_id text not null,
    tenant_id text not null,
    canonical_name text not null,
    normalized_canonical_name text not null,
    display_name text not null,
    description text,
    concept_type text not null,
    parent_concept_id text,
    synonyms jsonb not null default '[]'::jsonb,
    aliases jsonb not null default '[]'::jsonb,
    attributes jsonb not null default '{}'::jsonb,
    version integer not null,
    active boolean not null default true,
    revision integer not null default 1,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    deactivated_at timestamptz,
    deactivated_by text,
    schema_version integer not null default 1,
    primary key (organization_id, tenant_id, concept_id),
    constraint ontology_concepts_name_unique unique (organization_id, tenant_id, normalized_canonical_name),
    constraint ontology_concepts_version_positive check (version > 0),
    constraint ontology_concepts_revision_positive check (revision > 0),
    constraint ontology_concepts_deactivation_consistency check (active = true or deactivated_at is not null),
    constraint ontology_concepts_parent_not_self check (parent_concept_id is null or parent_concept_id <> concept_id)
);
create index if not exists ontology_concepts_tenant_type_idx on data_fabric.ontology_concepts (organization_id, tenant_id, concept_type);
create index if not exists ontology_concepts_tenant_active_idx on data_fabric.ontology_concepts (organization_id, tenant_id, active);
alter table data_fabric.ontology_concepts enable row level security;
comment on table data_fabric.ontology_concepts is 'P3 ontology concepts current-state table. RLS enabled with no anonymous policy; parent validation remains tenant-scoped in repositories/services.';
