create table if not exists public.performance_run (
    id text primary key,
    organization_id uuid not null,
    status text not null,
    performance_score numeric(6,2) not null default 0,
    summary jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.performance_metric (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Metric Key" text,
    "Metric" text,
    "Value" numeric,
    "Unit" text,
    "Target" text,
    "Status" text,
    "Component" text,
    created_at timestamptz not null default now()
);

create table if not exists public.performance_benchmark (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    "Benchmark" text,
    "Duration Ms" numeric(10,2),
    "Target Ms" numeric(10,2),
    "Status" text,
    "Records" integer,
    "Error" text,
    created_at timestamptz not null default now()
);

create table if not exists public.performance_bottleneck (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Component" text,
    "Metric" text,
    "Observed" text,
    "Target" text,
    "Severity" text,
    "Status" text,
    created_at timestamptz not null default now()
);

create table if not exists public.performance_recommendation (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Priority" text,
    "Component" text,
    "Recommendation" text,
    "Expected Impact" text,
    created_at timestamptz not null default now()
);

create table if not exists public.cache_metric (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Cache" text,
    cache_hits integer not null default 0,
    cache_misses integer not null default 0,
    cache_hit_ratio numeric(6,2) not null default 0,
    cache_ttl integer not null default 0,
    stale_cache_count integer not null default 0,
    "Status" text,
    created_at timestamptz not null default now()
);

create table if not exists public.load_test_result (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Scale Check" text,
    "Synthetic Load" text,
    "Result" text,
    "Status" text,
    created_at timestamptz not null default now()
);

create table if not exists public.slow_query_log (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Query" text,
    "Duration Ms" numeric(10,2),
    "Threshold Ms" numeric(10,2),
    "Status" text,
    created_at timestamptz not null default now()
);

create table if not exists public.throughput_metric (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    run_id text not null,
    "Stream" text,
    "Throughput" numeric,
    "Unit" text,
    "Success Rate" numeric(6,2),
    "Status" text,
    created_at timestamptz not null default now()
);

create index if not exists idx_performance_run_org_created
    on public.performance_run (organization_id, created_at desc);
create index if not exists idx_performance_metric_org_run
    on public.performance_metric (organization_id, run_id);
create index if not exists idx_performance_benchmark_org_created
    on public.performance_benchmark (organization_id, created_at desc);
create index if not exists idx_performance_bottleneck_org_run
    on public.performance_bottleneck (organization_id, run_id);
create index if not exists idx_performance_recommendation_org_run
    on public.performance_recommendation (organization_id, run_id);
create index if not exists idx_cache_metric_org_run
    on public.cache_metric (organization_id, run_id);
create index if not exists idx_load_test_result_org_run
    on public.load_test_result (organization_id, run_id);
create index if not exists idx_slow_query_log_org_run
    on public.slow_query_log (organization_id, run_id);
create index if not exists idx_throughput_metric_org_run
    on public.throughput_metric (organization_id, run_id);
