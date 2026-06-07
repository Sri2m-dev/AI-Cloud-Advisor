-- Add advanced anomaly fields required by anomaly_detection_engine.py
-- Run this in Supabase SQL Editor.

ALTER TABLE public.anomalies
ADD COLUMN IF NOT EXISTS cloud_provider text,
ADD COLUMN IF NOT EXISTS current_cost numeric,
ADD COLUMN IF NOT EXISTS reason text,
ADD COLUMN IF NOT EXISTS score numeric;

-- Optional: speed up dashboard aggregations and sorting.
CREATE INDEX IF NOT EXISTS idx_anomalies_cloud_provider ON public.anomalies (cloud_provider);
CREATE INDEX IF NOT EXISTS idx_anomalies_score_desc ON public.anomalies (score DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_created_at_desc ON public.anomalies (created_at DESC);
