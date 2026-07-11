-- P3 Data Fabric migration 0007
-- Purpose: create append-only provenance record table.
-- Safety: non-destructive create-if-absent migration; no credentials.

create table if not exists data_fabric.provenance_records (
    provenance_id uuid primary key,
    entity_id uuid,
    relationship_id uuid,
    organization_id text not null,
    tenant_id text not null,
    source_system text not null,
    source_identifier text not null,
    captured_at timestamptz not null,
    payload_hash text,
    evidence jsonb not null default '{}'::jsonb,
    metadata jsonb not null default '{}'::jsonb,
    schema_version integer not null default 1,
    constraint provenance_records_subject_required check (entity_id is not null or relationship_id is not null)
);

create index if not exists provenance_records_tenant_entity_idx
    on data_fabric.provenance_records (organization_id, tenant_id, entity_id);

create index if not exists provenance_records_tenant_relationship_idx
    on data_fabric.provenance_records (organization_id, tenant_id, relationship_id);

create index if not exists provenance_records_tenant_source_idx
    on data_fabric.provenance_records (organization_id, tenant_id, source_system, source_identifier);

create index if not exists provenance_records_captured_at_idx
    on data_fabric.provenance_records (captured_at);

create or replace function data_fabric.prevent_provenance_records_mutation()
returns trigger
language plpgsql
as $$
begin
    raise exception 'provenance_records is append-only';
end;
$$;

do $$
begin
    if not exists (select 1 from pg_trigger where tgname = 'prevent_provenance_records_update') then
        create trigger prevent_provenance_records_update
        before update on data_fabric.provenance_records
        for each row execute function data_fabric.prevent_provenance_records_mutation();
    end if;
    if not exists (select 1 from pg_trigger where tgname = 'prevent_provenance_records_delete') then
        create trigger prevent_provenance_records_delete
        before delete on data_fabric.provenance_records
        for each row execute function data_fabric.prevent_provenance_records_mutation();
    end if;
end $$;

alter table data_fabric.provenance_records enable row level security;

comment on table data_fabric.provenance_records is 'P3 append-only provenance table. RLS is enabled with no anonymous policy. Repository methods apply tenant filters and expose no update/delete path.';
