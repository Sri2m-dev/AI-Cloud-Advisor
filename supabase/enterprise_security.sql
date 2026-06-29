create table if not exists public.security_validation_run (
    id text primary key,
    organization_id uuid not null,
    status text not null,
    security_score numeric(6,2) not null default 0,
    critical_findings integer not null default 0,
    warnings integer not null default 0,
    summary jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.security_validation_result (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Domain" text,
    "Score" numeric(6,2),
    "Status" text,
    "Findings" integer,
    created_at timestamptz not null default now()
);

create table if not exists public.credential_inventory (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Connector" text,
    "Credential Type" text,
    "State" text,
    "Unused" boolean not null default false,
    "Last Validation" timestamptz,
    "Rotation Age Days" integer,
    created_at timestamptz not null default now()
);

create table if not exists public.credential_rotation (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Connector" text,
    "Secret Age" integer,
    "Rotation Status" text,
    "Rotation Due" text,
    "Manual Rotation Required" text,
    "Last Rotation" date,
    created_at timestamptz not null default now()
);

create table if not exists public.token_expiry (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Connector" text,
    "Expires In Days" integer,
    "Expired" boolean not null default false,
    "Expiring" boolean not null default false,
    "Status" text,
    created_at timestamptz not null default now()
);

create table if not exists public.rbac_validation (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.tenant_validation (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.execution_security (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.security_event (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    event_type text not null,
    severity text not null,
    source text not null,
    message text not null,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.security_recommendation (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Priority" text,
    "Domain" text,
    "Recommendation" text,
    "Owner" text,
    created_at timestamptz not null default now()
);

create index if not exists idx_security_validation_run_org_created
    on public.security_validation_run (organization_id, created_at desc);
create index if not exists idx_security_validation_result_org_run
    on public.security_validation_result (organization_id, run_id);
create index if not exists idx_credential_inventory_org_run
    on public.credential_inventory (organization_id, run_id);
create index if not exists idx_credential_rotation_org_run
    on public.credential_rotation (organization_id, run_id);
create index if not exists idx_token_expiry_org_run
    on public.token_expiry (organization_id, run_id);
create index if not exists idx_rbac_validation_org_run
    on public.rbac_validation (organization_id, run_id);
create index if not exists idx_tenant_validation_org_run
    on public.tenant_validation (organization_id, run_id);
create index if not exists idx_execution_security_org_run
    on public.execution_security (organization_id, run_id);
create index if not exists idx_security_event_org_created
    on public.security_event (organization_id, created_at desc);
create index if not exists idx_security_recommendation_org_run
    on public.security_recommendation (organization_id, run_id);
