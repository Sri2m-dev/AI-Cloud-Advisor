-- P3 Data Fabric migration 0002
-- Purpose: create canonical enterprise entity current-state table.
-- Safety: non-destructive create-if-absent migration; no credentials.

create table if not exists data_fabric.enterprise_entities (
    id text primary key,
    canonical_id text not null,
    entity_type text not null,
    name text not null,
    source_system text not null,
    source_identifier text not null,
    organization_id text not null,
    tenant_id text not null,
    version integer not null,
    confidence_score numeric,
    quality_score numeric,
    tags jsonb not null default '[]'::jsonb,
    metadata jsonb not null default '{}'::jsonb,
    active boolean not null default true,
    revision integer not null default 1,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    deactivated_at timestamptz,
    deactivated_by text,
    created_by text,
    updated_by text,
    schema_version integer not null default 1,
    constraint enterprise_entities_tenant_canonical_unique unique (organization_id, tenant_id, canonical_id),
    constraint enterprise_entities_tenant_source_unique unique (organization_id, tenant_id, source_system, source_identifier),
    constraint enterprise_entities_confidence_score_range check (confidence_score is null or (confidence_score >= 0 and confidence_score <= 100)),
    constraint enterprise_entities_quality_score_range check (quality_score is null or (quality_score >= 0 and quality_score <= 100)),
    constraint enterprise_entities_version_positive check (version > 0),
    constraint enterprise_entities_revision_positive check (revision > 0),
    constraint enterprise_entities_timestamp_order check (updated_at >= created_at),
    constraint enterprise_entities_deactivation_consistency check (active = true or deactivated_at is not null)
);

create index if not exists enterprise_entities_tenant_idx
    on data_fabric.enterprise_entities (organization_id, tenant_id);

create index if not exists enterprise_entities_tenant_type_idx
    on data_fabric.enterprise_entities (organization_id, tenant_id, entity_type);

create index if not exists enterprise_entities_tenant_active_idx
    on data_fabric.enterprise_entities (organization_id, tenant_id, active);

create index if not exists enterprise_entities_tenant_source_idx
    on data_fabric.enterprise_entities (organization_id, tenant_id, source_system, source_identifier);

create index if not exists enterprise_entities_tenant_canonical_idx
    on data_fabric.enterprise_entities (organization_id, tenant_id, canonical_id);

create index if not exists enterprise_entities_updated_at_idx
    on data_fabric.enterprise_entities (updated_at);

alter table data_fabric.enterprise_entities enable row level security;

comment on table data_fabric.enterprise_entities is 'P3 Data Fabric canonical entity current-state table. RLS must deny anonymous and cross-tenant access; service-role bypass is server-side only and repositories must still apply tenant filters.';
