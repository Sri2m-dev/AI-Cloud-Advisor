-- Table: ai_model_registry
-- Purpose: Operationalize AI properly

CREATE TABLE IF NOT EXISTS ai_model_registry (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name text NOT NULL,
    model_version text NOT NULL,
    model_type text NOT NULL,
    status text NOT NULL,
    trained_at timestamptz,
    inference_last_run timestamptz,
    training_window text,
    accuracy_score numeric,
    metadata jsonb
);