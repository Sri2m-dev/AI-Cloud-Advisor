create table if not exists public.forecast_history (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    metric_name text not null,
    current_value numeric(16,2) not null default 0,
    forecast_value numeric(16,2) not null default 0,
    forecast_horizon_days integer not null,
    confidence numeric(6,2) not null default 0,
    model_name text not null default 'deterministic_trend_v1',
    created_at timestamptz not null default now()
);

create table if not exists public.forecast_models (
    id uuid primary key default gen_random_uuid(),
    model_name text not null unique,
    model_type text not null,
    target_metric text not null,
    version text not null default '1.0',
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists public.prediction_results (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    prediction_type text not null,
    entity_name text not null,
    probability numeric(6,2) not null default 0,
    recommendation text,
    confidence numeric(6,2) not null default 0,
    prediction_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.prediction_accuracy (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    model_name text not null,
    metric_name text not null,
    forecast_value numeric(16,2) not null default 0,
    actual_value numeric(16,2) not null default 0,
    accuracy numeric(6,2) not null default 0,
    measured_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create table if not exists public.forecast_actuals (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    metric_name text not null,
    actual_value numeric(16,2) not null default 0,
    actual_date date not null default current_date,
    source text not null default 'manual',
    created_at timestamptz not null default now()
);

create table if not exists public.model_registry (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    model_name text not null,
    model_type text not null default 'forecast',
    target_metric text not null default 'enterprise',
    training_date date,
    data_sources jsonb not null default '[]'::jsonb,
    accuracy numeric(6,2) not null default 0,
    owner text not null default 'Enterprise Intelligence',
    status text not null default 'Experimental',
    created_at timestamptz not null default now(),
    unique (organization_id, model_name)
);

create table if not exists public.model_versions (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    model_name text not null,
    version text not null,
    training_date date,
    data_sources jsonb not null default '[]'::jsonb,
    accuracy numeric(6,2) not null default 0,
    status text not null default 'Experimental',
    created_at timestamptz not null default now(),
    unique (organization_id, model_name, version)
);

create table if not exists public.forecast_drift (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    metric_name text not null,
    forecast_value numeric(16,2) not null default 0,
    actual_value numeric(16,2) not null default 0,
    variance_percent numeric(8,2) not null default 0,
    severity text not null default 'Medium',
    possible_reasons jsonb not null default '[]'::jsonb,
    recommended_action text,
    detected_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create table if not exists public.prediction_confidence_history (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    metric_name text not null,
    confidence numeric(6,2) not null default 0,
    reason text,
    measured_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create table if not exists public.capacity_forecast (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    domain text not null,
    current_utilization numeric(6,2) not null default 0,
    days_to_threshold numeric(8,2) not null default 0,
    recommendation text,
    confidence numeric(6,2) not null default 0,
    created_at timestamptz not null default now()
);

create table if not exists public.budget_forecast (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    entity_name text not null,
    budget numeric(16,2) not null default 0,
    forecast_spend numeric(16,2) not null default 0,
    breach_probability numeric(6,2) not null default 0,
    created_at timestamptz not null default now()
);

create table if not exists public.risk_forecast (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    entity_name text not null,
    risk_category text not null,
    probability numeric(6,2) not null default 0,
    recommendation text,
    confidence numeric(6,2) not null default 0,
    created_at timestamptz not null default now()
);

create table if not exists public.renewal_forecast (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null,
    vendor_name text not null,
    renewal_date date,
    renewal_risk numeric(6,2) not null default 0,
    recommendation text,
    confidence numeric(6,2) not null default 0,
    created_at timestamptz not null default now()
);

create index if not exists idx_forecast_history_org_metric
    on public.forecast_history (organization_id, metric_name, created_at desc);

create index if not exists idx_forecast_actuals_org_metric
    on public.forecast_actuals (organization_id, metric_name, actual_date desc);

create index if not exists idx_model_registry_org_status
    on public.model_registry (organization_id, status);

create index if not exists idx_model_versions_org_model
    on public.model_versions (organization_id, model_name, created_at desc);

create index if not exists idx_forecast_drift_org_severity
    on public.forecast_drift (organization_id, severity, detected_at desc);

create index if not exists idx_prediction_confidence_history_org_metric
    on public.prediction_confidence_history (organization_id, metric_name, measured_at desc);

create index if not exists idx_prediction_results_org_probability
    on public.prediction_results (organization_id, probability desc);

create index if not exists idx_capacity_forecast_org_threshold
    on public.capacity_forecast (organization_id, days_to_threshold);

create index if not exists idx_budget_forecast_org_probability
    on public.budget_forecast (organization_id, breach_probability desc);

create index if not exists idx_risk_forecast_org_probability
    on public.risk_forecast (organization_id, probability desc);

create index if not exists idx_renewal_forecast_org_risk
    on public.renewal_forecast (organization_id, renewal_risk desc);
