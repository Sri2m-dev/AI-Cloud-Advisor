-- Table: workspace_activity_log
-- Purpose: Track platform usage and governance activity

CREATE TABLE IF NOT EXISTS workspace_activity_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_email text NOT NULL,
    role text NOT NULL,
    workspace text NOT NULL,
    action text NOT NULL,
    org_id text NOT NULL,
    tenant_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb
);