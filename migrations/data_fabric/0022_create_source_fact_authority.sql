-- CMP-P4 cohesive multi-source authority persistence.
create table if not exists data_fabric.source_instances (
    source_instance_id text not null,
    organization_id text not null,
    tenant_id text not null,
    source_type text not null,
    source_system text not null,
    connector_type text not null,
    connector_version text not null,
    configuration_reference text not null,
    credential_reference text,
    enabled boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (organization_id, tenant_id, source_instance_id)
);

create table if not exists data_fabric.source_facts (
    source_fact_id text primary key,
    observation_key text not null,
    fact_version integer not null check (fact_version > 0),
    organization_id text not null,
    tenant_id text not null,
    source_instance_id text not null,
    source_type text not null,
    source_system text not null,
    connector_version text not null,
    ingestion_run_id text not null,
    source_record_id text not null,
    fact_type text not null,
    subject_reference text not null,
    predicate text not null,
    value jsonb,
    object_reference text,
    observed_at timestamptz not null,
    effective_from timestamptz,
    effective_to timestamptz,
    source_schema_version text not null,
    quality numeric not null check (quality >= 0 and quality <= 1),
    freshness text not null check (freshness in ('fresh','aging','stale','unknown')),
    evidence_reference text not null,
    lineage jsonb not null default '{}'::jsonb,
    provenance jsonb not null default '{}'::jsonb,
    lifecycle text not null,
    fingerprint text not null,
    created_at timestamptz not null default now(),
    unique (organization_id, tenant_id, observation_key, fact_version),
    check (effective_to is null or effective_from is null or effective_to > effective_from)
);

create table if not exists data_fabric.source_runtime (
    runtime_record_id text primary key,
    organization_id text not null,
    tenant_id text not null,
    source_instance_id text not null,
    record_type text not null check (record_type in ('sync_run','source_state','schema_event')),
    status text not null,
    payload jsonb not null default '{}'::jsonb,
    fingerprint text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists data_fabric.source_authority (
    authority_record_id text primary key,
    organization_id text not null,
    tenant_id text not null,
    record_type text not null check (record_type in ('policy','reconciliation','human_decision','lifecycle')),
    fact_type text,
    subject_reference text,
    predicate text,
    version integer not null check (version > 0),
    effective_from timestamptz not null,
    effective_to timestamptz,
    payload jsonb not null default '{}'::jsonb,
    fingerprint text not null,
    created_at timestamptz not null default now(),
    check (effective_to is null or effective_to > effective_from)
);

create index if not exists source_facts_current_idx
    on data_fabric.source_facts (organization_id, tenant_id, observation_key, fact_version desc);
create index if not exists source_facts_reconciliation_idx
    on data_fabric.source_facts (organization_id, tenant_id, fact_type, subject_reference, predicate);
create index if not exists source_runtime_instance_idx
    on data_fabric.source_runtime (organization_id, tenant_id, source_instance_id, record_type);
create index if not exists source_authority_lookup_idx
    on data_fabric.source_authority (organization_id, tenant_id, fact_type, subject_reference, predicate);

alter table data_fabric.source_instances enable row level security;
alter table data_fabric.source_facts enable row level security;
alter table data_fabric.source_runtime enable row level security;
alter table data_fabric.source_authority enable row level security;

create or replace function data_fabric.prevent_source_fact_mutation()
returns trigger language plpgsql as $$
begin
    raise exception 'source facts are append-only';
end;
$$;

do $$
begin
    if not exists (
        select 1 from pg_trigger
        where tgname = 'source_facts_immutable'
          and tgrelid = 'data_fabric.source_facts'::regclass
    ) then
        create trigger source_facts_immutable before update or delete
        on data_fabric.source_facts for each row
        execute function data_fabric.prevent_source_fact_mutation();
    end if;
end;
$$;
