-- P3 Data Fabric migration 0005
-- Purpose: create append-only entity version snapshot table.
-- Safety: non-destructive create-if-absent migration; no credentials.

create table if not exists data_fabric.entity_versions (
    snapshot_id uuid primary key,
    entity_id uuid not null,
    canonical_id text not null,
    organization_id text not null,
    tenant_id text not null,
    version integer not null,
    source_system text,
    source_identifier text,
    recorded_at timestamptz not null,
    effective_from timestamptz,
    effective_to timestamptz,
    payload jsonb not null,
    payload_hash text not null,
    lineage_references jsonb not null default '[]'::jsonb,
    provenance_references jsonb not null default '[]'::jsonb,
    schema_version integer not null default 1,
    constraint entity_versions_tenant_entity_version_unique unique (organization_id, tenant_id, entity_id, version),
    constraint entity_versions_payload_hash_required check (length(payload_hash) > 0),
    constraint entity_versions_version_positive check (version > 0),
    constraint entity_versions_effective_range check (effective_to is null or effective_from is null or effective_to > effective_from)
);

create index if not exists entity_versions_tenant_entity_idx
    on data_fabric.entity_versions (organization_id, tenant_id, entity_id);

create index if not exists entity_versions_tenant_canonical_idx
    on data_fabric.entity_versions (organization_id, tenant_id, canonical_id);

create index if not exists entity_versions_recorded_at_idx
    on data_fabric.entity_versions (recorded_at);

create index if not exists entity_versions_effective_from_idx
    on data_fabric.entity_versions (effective_from);

create index if not exists entity_versions_payload_hash_idx
    on data_fabric.entity_versions (payload_hash);

create or replace function data_fabric.prevent_entity_versions_mutation()
returns trigger
language plpgsql
as $$
begin
    raise exception 'entity_versions is append-only';
end;
$$;

do $$
begin
    if not exists (select 1 from pg_trigger where tgname = 'prevent_entity_versions_update') then
        create trigger prevent_entity_versions_update
        before update on data_fabric.entity_versions
        for each row execute function data_fabric.prevent_entity_versions_mutation();
    end if;
    if not exists (select 1 from pg_trigger where tgname = 'prevent_entity_versions_delete') then
        create trigger prevent_entity_versions_delete
        before delete on data_fabric.entity_versions
        for each row execute function data_fabric.prevent_entity_versions_mutation();
    end if;
end $$;

alter table data_fabric.entity_versions enable row level security;

comment on table data_fabric.entity_versions is 'P3 append-only entity version table. RLS is enabled with no anonymous policy. No repository update or physical delete path is exposed.';
