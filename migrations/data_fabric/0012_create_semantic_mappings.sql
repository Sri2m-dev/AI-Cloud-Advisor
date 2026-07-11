-- P3 Data Fabric migration 0012
-- Purpose: create mutable semantic mapping current-state table.
-- Safety: non-destructive create-if-absent migration; no credentials.
create table if not exists data_fabric.semantic_mappings (
    mapping_id uuid primary key,
    organization_id text not null,
    tenant_id text not null,
    source_system text not null,
    source_term text not null,
    source_type text,
    source_identifier text,
    provider text,
    entity_type text,
    concept_id text not null,
    confidence_score numeric not null,
    mapping_strategy text not null,
    explanation jsonb not null default '{}'::jsonb,
    attributes jsonb not null default '{}'::jsonb,
    active boolean not null default true,
    revision integer not null default 1,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    deactivated_at timestamptz,
    schema_version integer not null default 1,
    constraint semantic_mappings_confidence_range check (confidence_score >= 0 and confidence_score <= 100),
    constraint semantic_mappings_revision_positive check (revision > 0),
    constraint semantic_mappings_deactivation_consistency check (active = true or deactivated_at is not null)
);
create unique index if not exists semantic_mappings_active_explicit_unique_idx on data_fabric.semantic_mappings (organization_id, tenant_id, source_system, source_term, coalesce(source_type,''), coalesce(source_identifier,''), coalesce(provider,''), coalesce(entity_type,''), concept_id, mapping_strategy) where active = true;
create index if not exists semantic_mappings_concept_idx on data_fabric.semantic_mappings (organization_id, tenant_id, concept_id);
create index if not exists semantic_mappings_source_idx on data_fabric.semantic_mappings (organization_id, tenant_id, source_system);
alter table data_fabric.semantic_mappings enable row level security;
comment on table data_fabric.semantic_mappings is 'P3 semantic mappings current-state table. RLS enabled with no anonymous policy; concept existence remains tenant-scoped in repositories/services.';
