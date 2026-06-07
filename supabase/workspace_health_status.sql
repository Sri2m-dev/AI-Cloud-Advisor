-- Create workspace_health_status table to track platform health metrics
-- Run this migration in your Supabase SQL editor or psql client

CREATE TABLE IF NOT EXISTS public.workspace_health_status (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id TEXT NOT NULL,
    tenant_id TEXT,
    account_id TEXT,
    metric_name TEXT NOT NULL, -- e.g., 'ingestion_freshness', 'ai_freshness', 'etl_health', 'mart_refresh', 'alerting_health'
    metric_value TEXT,         -- e.g., 'OK', 'STALE', 'ERROR', or a timestamp/number
    metric_details JSONB DEFAULT '{}'::jsonb,
    -- Athena/ETL/Component Health Columns
    component TEXT,            -- e.g., 'aws_athena_ingest'
    status TEXT,               -- e.g., 'healthy', 'error', 'stale'
    last_success_at timestamptz,
    last_failure_at timestamptz,
    latency_seconds NUMERIC,
    records_processed BIGINT,
    error_message TEXT,
    updated_at timestamptz,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    updated_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_workspace_health_status_org_metric ON public.workspace_health_status (org_id, metric_name, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_workspace_health_status_component ON public.workspace_health_status (component, updated_at DESC);
