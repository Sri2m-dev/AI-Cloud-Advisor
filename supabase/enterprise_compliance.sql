create table if not exists public.compliance_run (
    id text primary key,
    organization_id uuid not null,
    status text not null,
    score numeric(6,2) not null default 0,
    summary jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.compliance_framework (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Framework" text,
    "Score" numeric(6,2),
    "Status" text,
    "Controls" integer,
    "Evidence Coverage" text,
    created_at timestamptz not null default now()
);

create table if not exists public.compliance_control (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Control" text,
    "Framework" text,
    "Evidence Source" text,
    "Score" numeric(6,2),
    "Status" text,
    created_at timestamptz not null default now()
);

create table if not exists public.compliance_evidence (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Evidence" text,
    "Source" text,
    "Format" text,
    "Status" text,
    "Owner" text,
    "Generated At" timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists public.audit_package (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    package_id text not null,
    formats jsonb not null default '[]'::jsonb,
    evidence_count integer not null default 0,
    status text not null,
    download_ready boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists public.dr_readiness (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    score numeric(6,2) not null default 0,
    status text not null,
    kpis jsonb not null default '{}'::jsonb,
    checks jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.operational_readiness (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    score numeric(6,2) not null default 0,
    status text not null,
    kpis jsonb not null default '{}'::jsonb,
    domains jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.release_readiness (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    score numeric(6,2) not null default 0,
    status text not null,
    kpis jsonb not null default '{}'::jsonb,
    checks jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.production_readiness (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    score numeric(6,2) not null default 0,
    status text not null,
    kpis jsonb not null default '{}'::jsonb,
    domains jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.version_readiness_report (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    "Version" text,
    "Overall Readiness" numeric(6,2),
    "Release Status" text,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.readiness_recommendation (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text,
    "Priority" text,
    "Framework" text,
    "Recommendation" text,
    created_at timestamptz not null default now()
);

create index if not exists idx_compliance_run_org_created on public.compliance_run (organization_id, created_at desc);
create index if not exists idx_compliance_framework_org_run on public.compliance_framework (organization_id, run_id);
create index if not exists idx_compliance_control_org_run on public.compliance_control (organization_id, run_id);
create index if not exists idx_compliance_evidence_org_run on public.compliance_evidence (organization_id, run_id);
create index if not exists idx_audit_package_org_created on public.audit_package (organization_id, created_at desc);
create index if not exists idx_dr_readiness_org_created on public.dr_readiness (organization_id, created_at desc);
create index if not exists idx_operational_readiness_org_created on public.operational_readiness (organization_id, created_at desc);
create index if not exists idx_release_readiness_org_created on public.release_readiness (organization_id, created_at desc);
create index if not exists idx_production_readiness_org_created on public.production_readiness (organization_id, created_at desc);
create index if not exists idx_version_readiness_report_org_created on public.version_readiness_report (organization_id, created_at desc);
