-- Enterprise approval workflow fields and audit trail.

alter table if exists public.approval_queue
    add column if not exists status text default 'PENDING',
    add column if not exists approver_comments text,
    add column if not exists approved_at timestamptz,
    add column if not exists approved_by text,
    add column if not exists rejected_at timestamptz,
    add column if not exists rejected_by text,
    add column if not exists rejection_reason text,
    add column if not exists completed_at timestamptz,
    add column if not exists completed_by text,
    add column if not exists rolled_back_at timestamptz,
    add column if not exists rolled_back_by text,
    add column if not exists rollback_reason text,
    add column if not exists rollback_to_status text,
    add column if not exists assigned_to text,
    add column if not exists updated_at timestamptz,
    add column if not exists updated_by text;

create table if not exists public.approval_audit (
    id bigserial primary key,
    approval_id text not null,
    org_id text,
    actor text not null,
    action text not null,
    previous_status text,
    new_status text,
    comments text,
    created_at timestamptz not null default now()
);

create index if not exists idx_approval_audit_approval_created
    on public.approval_audit (approval_id, created_at desc);

create index if not exists idx_approval_queue_org_status
    on public.approval_queue (org_id, status);
