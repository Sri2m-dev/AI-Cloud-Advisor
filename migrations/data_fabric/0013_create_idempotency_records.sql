-- P3 Data Fabric migration 0013
-- Purpose: create idempotency state table.
-- Safety: non-destructive create-if-absent migration; no credentials.
create table if not exists data_fabric.idempotency_records (
    record_id uuid primary key default gen_random_uuid(),
    organization_id text not null,
    tenant_id text not null,
    idempotency_key text not null,
    payload_hash text not null,
    status text not null,
    result_payload jsonb,
    failure_reason text,
    reserved_at timestamptz not null,
    completed_at timestamptz,
    failed_at timestamptz,
    expires_at timestamptz,
    correlation_id text,
    revision integer not null default 1,
    metadata jsonb not null default '{}'::jsonb,
    schema_version integer not null default 1,
    constraint idempotency_records_key_unique unique (organization_id, tenant_id, idempotency_key),
    constraint idempotency_records_status check (status in ('in_progress','completed','failed','expired')),
    constraint idempotency_records_completed_consistency check (status <> 'completed' or completed_at is not null),
    constraint idempotency_records_failed_consistency check (status <> 'failed' or (failed_at is not null and failure_reason is not null)),
    constraint idempotency_records_expired_consistency check (status <> 'expired' or expires_at is not null),
    constraint idempotency_records_revision_positive check (revision > 0)
);
create index if not exists idempotency_records_status_idx on data_fabric.idempotency_records (organization_id, tenant_id, status);
create index if not exists idempotency_records_expires_idx on data_fabric.idempotency_records (expires_at);
alter table data_fabric.idempotency_records enable row level security;
comment on table data_fabric.idempotency_records is 'P3 idempotency state table. RLS enabled with no anonymous policy. Expiry is explicit; no scheduler is introduced.';
