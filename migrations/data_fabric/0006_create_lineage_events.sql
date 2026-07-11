-- P3 Data Fabric migration 0006
-- Purpose: create append-only lineage event table.
-- Safety: non-destructive create-if-absent migration; no credentials.

create table if not exists data_fabric.lineage_events (
    event_id uuid primary key,
    entity_id uuid,
    relationship_id uuid,
    organization_id text not null,
    tenant_id text not null,
    event_type text not null,
    source_system text,
    source_identifier text,
    occurred_at timestamptz not null,
    correlation_id text,
    payload jsonb not null default '{}'::jsonb,
    metadata jsonb not null default '{}'::jsonb,
    schema_version integer not null default 1,
    constraint lineage_events_subject_required check (entity_id is not null or relationship_id is not null)
);

create index if not exists lineage_events_tenant_entity_idx
    on data_fabric.lineage_events (organization_id, tenant_id, entity_id);

create index if not exists lineage_events_tenant_relationship_idx
    on data_fabric.lineage_events (organization_id, tenant_id, relationship_id);

create index if not exists lineage_events_tenant_correlation_idx
    on data_fabric.lineage_events (organization_id, tenant_id, correlation_id);

create index if not exists lineage_events_occurred_at_idx
    on data_fabric.lineage_events (occurred_at);

create or replace function data_fabric.prevent_lineage_events_mutation()
returns trigger
language plpgsql
as $$
begin
    raise exception 'lineage_events is append-only';
end;
$$;

do $$
begin
    if not exists (select 1 from pg_trigger where tgname = 'prevent_lineage_events_update') then
        create trigger prevent_lineage_events_update
        before update on data_fabric.lineage_events
        for each row execute function data_fabric.prevent_lineage_events_mutation();
    end if;
    if not exists (select 1 from pg_trigger where tgname = 'prevent_lineage_events_delete') then
        create trigger prevent_lineage_events_delete
        before delete on data_fabric.lineage_events
        for each row execute function data_fabric.prevent_lineage_events_mutation();
    end if;
end $$;

alter table data_fabric.lineage_events enable row level security;

comment on table data_fabric.lineage_events is 'P3 append-only lineage event table. RLS is enabled with no anonymous policy. Repository methods apply tenant filters and expose no update/delete path.';
