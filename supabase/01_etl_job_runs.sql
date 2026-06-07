-- Table: etl_job_runs
-- Purpose: Track every ingestion/transformation job

CREATE TABLE IF NOT EXISTS etl_job_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id text NOT NULL,
    tenant_id text NOT NULL,
    job_name text NOT NULL,
    job_type text NOT NULL,
    status text NOT NULL,
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    duration_seconds numeric,
    records_processed bigint,
    error_message text,
    metadata jsonb
);