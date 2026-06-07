-- AI Model Registry Table for Model Freshness and Health
CREATE TABLE IF NOT EXISTS public.ai_model_registry (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id TEXT NOT NULL,
    tenant_id TEXT,
    account_id TEXT,
    model_name TEXT NOT NULL,
    model_version TEXT,
    trained_at timestamptz,
    inference_last_run timestamptz,
    status TEXT, -- e.g., 'active', 'stale', 'training', 'error'
    training_dataset_window TEXT,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_model_registry_model ON public.ai_model_registry (model_name, model_version, trained_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_model_registry_org_model ON public.ai_model_registry (org_id, model_name, trained_at DESC);
