create table if not exists public.data_quality_run (
    id text primary key,
    organization_id uuid not null,
    status text not null,
    overall_score numeric(6,2) not null default 0,
    ai_trust_score numeric(6,2) not null default 0,
    domain_scores jsonb not null default '{}'::jsonb,
    summary jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.data_quality_result (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Domain" text,
    "Score" numeric(6,2),
    "Status" text,
    "Weight" text,
    created_at timestamptz not null default now()
);

create table if not exists public.data_quality_rule (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Rule" text,
    "Domain" text,
    "Status" text,
    "Severity" text,
    "Result" text,
    created_at timestamptz not null default now()
);

create table if not exists public.data_quality_issue (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Severity" text,
    "Domain" text,
    "Issue" text,
    "Description" text,
    "Count" integer not null default 0,
    "Status" text,
    "Recommended Action" text,
    "Event Key" text,
    created_at timestamptz not null default now()
);

create table if not exists public.data_quality_recommendation (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Priority" text,
    "Domain" text,
    "Recommendation" text,
    "Expected Impact" text,
    "Owner" text,
    created_at timestamptz not null default now()
);

create table if not exists public.data_freshness (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Source" text,
    "Freshness" text,
    "Age Seconds" integer,
    "Status" text,
    created_at timestamptz not null default now()
);

create table if not exists public.ai_trust_score (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "AI Trust Score" numeric(6,2),
    "Reasoning Confidence" numeric(6,2),
    "Prediction Confidence" numeric(6,2),
    "Graph Completeness" numeric(6,2),
    "Telemetry Freshness" numeric(6,2),
    "Digital Twin Completeness" numeric(6,2),
    "Cost Confidence" numeric(6,2),
    "Decision" text,
    created_at timestamptz not null default now()
);

create table if not exists public.graph_validation (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Graph" text,
    "Integrity" numeric(6,2),
    "Broken Relationships" integer,
    "Status" text,
    created_at timestamptz not null default now()
);

create table if not exists public.telemetry_validation (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Signal" text,
    "Score" numeric(6,2),
    "Records" integer,
    "Status" text,
    created_at timestamptz not null default now()
);

create table if not exists public.cost_validation (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Check" text,
    "Score" numeric(6,2),
    "Gaps" integer,
    "Status" text,
    created_at timestamptz not null default now()
);

create index if not exists idx_data_quality_run_org_created
    on public.data_quality_run (organization_id, created_at desc);
create index if not exists idx_data_quality_result_org_run
    on public.data_quality_result (organization_id, run_id);
create index if not exists idx_data_quality_rule_org_run
    on public.data_quality_rule (organization_id, run_id);
create index if not exists idx_data_quality_issue_org_run
    on public.data_quality_issue (organization_id, run_id);
create index if not exists idx_data_quality_recommendation_org_run
    on public.data_quality_recommendation (organization_id, run_id);
create index if not exists idx_data_freshness_org_run
    on public.data_freshness (organization_id, run_id);
create index if not exists idx_ai_trust_score_org_run
    on public.ai_trust_score (organization_id, run_id);
create index if not exists idx_graph_validation_org_run
    on public.graph_validation (organization_id, run_id);
create index if not exists idx_telemetry_validation_org_run
    on public.telemetry_validation (organization_id, run_id);
create index if not exists idx_cost_validation_org_run
    on public.cost_validation (organization_id, run_id);
