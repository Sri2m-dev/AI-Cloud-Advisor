-- Table: data_quality_checks
-- Purpose: Enterprise-grade data validation

CREATE TABLE IF NOT EXISTS data_quality_checks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name text NOT NULL,
    check_name text NOT NULL,
    status text NOT NULL,
    failed_rows bigint,
    checked_at timestamptz NOT NULL,
    details jsonb
);