-- ETL Job Runs Table for Latency Tracking
CREATE TABLE IF NOT EXISTS public.etl_job_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id TEXT NOT NULL,
    tenant_id TEXT,
    account_id TEXT,
    job_name TEXT NOT NULL,
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    duration_seconds NUMERIC,
    status TEXT, -- e.g., 'success', 'failed'
    error_message TEXT,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_etl_job_runs_job_time ON public.etl_job_runs (job_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_etl_job_runs_org_job ON public.etl_job_runs (org_id, job_name, started_at DESC);
