-- Mart Refresh History Table for SLA, Staleness, and Auditability
CREATE TABLE IF NOT EXISTS public.mart_refresh_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id TEXT NOT NULL,
    tenant_id TEXT,
    account_id TEXT,
    mart_name TEXT NOT NULL,
    refresh_started_at timestamptz NOT NULL,
    refresh_completed_at timestamptz,
    status TEXT, -- e.g., 'success', 'failed', 'in_progress'
    row_count BIGINT,
    refresh_duration_seconds NUMERIC,
    error_message TEXT,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mart_refresh_history_mart_time ON public.mart_refresh_history (mart_name, refresh_started_at DESC);
CREATE INDEX IF NOT EXISTS idx_mart_refresh_history_org_mart ON public.mart_refresh_history (org_id, mart_name, refresh_started_at DESC);
