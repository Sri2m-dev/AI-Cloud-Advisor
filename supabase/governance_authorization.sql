create table if not exists public.governance_review (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    workflow_id uuid,
    goal_text text,
    governance_score numeric(6,2) not null default 0,
    cab_readiness numeric(6,2) not null default 0,
    execution_status text not null default 'NOT AUTHORIZED',
    review_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.approval_request (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    review_id uuid,
    workflow_id uuid,
    approver_role text not null,
    approver text,
    status text not null default 'Pending',
    policy_reason text,
    due_date date,
    created_at timestamptz not null default now()
);

create table if not exists public.approval_decision (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    approval_request_id uuid,
    review_id uuid,
    decision text not null,
    decision_by text not null,
    comments text,
    conditions jsonb not null default '[]'::jsonb,
    evidence jsonb not null default '[]'::jsonb,
    blueprint_revision text not null default '1.0',
    created_at timestamptz not null default now()
);

create table if not exists public.execution_authorization (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    review_id uuid,
    workflow_id uuid,
    authorization_status text not null default 'NOT AUTHORIZED',
    authorized boolean not null default false,
    authorized_by text,
    authorization_reason text,
    authorization_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.cab_review (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    review_id uuid,
    workflow_id uuid,
    readiness_score numeric(6,2) not null default 0,
    cab_ready boolean not null default false,
    missing_items jsonb not null default '[]'::jsonb,
    checklist jsonb not null default '[]'::jsonb,
    status text not null default 'Needs Remediation',
    created_at timestamptz not null default now()
);

create table if not exists public.policy_validation (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    review_id uuid,
    policy_name text not null,
    policy_category text not null,
    status text not null,
    evidence text,
    severity text not null default 'Info',
    created_at timestamptz not null default now()
);

create table if not exists public.digital_signature (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    approval_decision_id uuid,
    signed_by text not null,
    signature_hash text not null,
    signature_payload jsonb not null default '{}'::jsonb,
    blueprint_revision text not null default '1.0',
    signed_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create table if not exists public.approval_comments (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    approval_request_id uuid,
    review_id uuid,
    comment_by text not null,
    comment_text text not null,
    evidence jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.execution_lock (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    review_id uuid,
    workflow_id uuid,
    lock_state text not null default 'LOCKED',
    reason text,
    unlock_conditions jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_governance_review_org_status
    on public.governance_review (organization_id, execution_status, created_at desc);

create index if not exists idx_approval_request_org_status
    on public.approval_request (organization_id, status, due_date);

create index if not exists idx_approval_decision_org_review
    on public.approval_decision (organization_id, review_id, created_at desc);

create index if not exists idx_execution_authorization_org_review
    on public.execution_authorization (organization_id, review_id, created_at desc);

create index if not exists idx_cab_review_org_review
    on public.cab_review (organization_id, review_id, created_at desc);

create index if not exists idx_policy_validation_org_review
    on public.policy_validation (organization_id, review_id, status);

create index if not exists idx_digital_signature_org_decision
    on public.digital_signature (organization_id, approval_decision_id, signed_at desc);

create index if not exists idx_approval_comments_org_request
    on public.approval_comments (organization_id, approval_request_id, created_at desc);

create index if not exists idx_execution_lock_org_review
    on public.execution_lock (organization_id, review_id, lock_state);
