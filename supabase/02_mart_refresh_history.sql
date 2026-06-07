-- Table: mart_refresh_history
-- Purpose: Track KPI/materialized mart freshness

CREATE TABLE IF NOT EXISTS mart_refresh_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    mart_name text NOT NULL,
    org_id text NOT NULL,
    tenant_id text NOT NULL,
    refresh_started_at timestamptz NOT NULL,
    refresh_completed_at timestamptz,
    status text NOT NULL,
    row_count bigint,
    refresh_duration_seconds numeric
);