-- AI-Cloud-Advisor: Master Database Normalization Migration Script
-- Run this in your Supabase SQL editor or psql client.

-- 1. recommendations table (add missing columns)
ALTER TABLE IF EXISTS public.recommendations
    ADD COLUMN IF NOT EXISTS owner text,
    ADD COLUMN IF NOT EXISTS approved_at timestamptz,
    ADD COLUMN IF NOT EXISTS assigned_at timestamptz,
    ADD COLUMN IF NOT EXISTS snoozed_at timestamptz,
    ADD COLUMN IF NOT EXISTS snooze_until timestamptz,
    ADD COLUMN IF NOT EXISTS workflow_version integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_transition_at timestamptz,
    ADD COLUMN IF NOT EXISTS last_transition_by text,
    ADD COLUMN IF NOT EXISTS last_transition_key text;

CREATE INDEX IF NOT EXISTS idx_recommendations_org_status
    ON public.recommendations (org_id, status);
CREATE INDEX IF NOT EXISTS idx_recommendations_org_owner
    ON public.recommendations (org_id, owner);
CREATE INDEX IF NOT EXISTS idx_recommendations_snooze_until
    ON public.recommendations (snooze_until);

-- 2. recommendation_transition_log table
CREATE TABLE IF NOT EXISTS public.recommendation_transition_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id text NOT NULL,
    org_id text,
    from_status text,
    to_status text NOT NULL,
    actor text,
    idempotency_key text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    expected_version integer,
    resulting_version integer,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_rec_transition_log_idempotency
    ON public.recommendation_transition_log (idempotency_key);
CREATE INDEX IF NOT EXISTS idx_rec_transition_log_rec_created
    ON public.recommendation_transition_log (recommendation_id, created_at desc);

-- 3. governance_score_history table
CREATE TABLE IF NOT EXISTS public.governance_score_history (
    id uuid PRIMARY KEY,
    org_id text NOT NULL,
    tenant_id text,
    raw_score numeric NOT NULL,
    smoothed_score numeric NOT NULL,
    score_model_version text NOT NULL DEFAULT 'v2_weighted_stable',
    weights jsonb NOT NULL DEFAULT '{}'::jsonb,
    components jsonb NOT NULL DEFAULT '{}'::jsonb,
    recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_governance_score_history_org_recorded
    ON public.governance_score_history (org_id, recorded_at desc);

-- 4. alert_configs table
CREATE TABLE IF NOT EXISTS public.alert_configs (
    id uuid PRIMARY KEY,
    org_id text NOT NULL,
    tenant_id text,
    spend_spike_pct numeric NOT NULL DEFAULT 25,
    idle_vm_min_savings numeric NOT NULL DEFAULT 100,
    savings_opportunity_threshold numeric NOT NULL DEFAULT 500,
    governance_score_drop_threshold numeric NOT NULL DEFAULT 10,
    governance_score_floor numeric NOT NULL DEFAULT 70,
    cooldown_minutes integer NOT NULL DEFAULT 180,
    channels jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_by text,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_alert_configs_org ON public.alert_configs (org_id);

-- 5. alert_history table
CREATE TABLE IF NOT EXISTS public.alert_history (
    id uuid PRIMARY KEY,
    org_id text NOT NULL,
    tenant_id text,
    alert_type text NOT NULL,
    severity text,
    message text NOT NULL,
    channels jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_alert_history_org_created ON public.alert_history (org_id, created_at desc);

-- 6. report_history table
CREATE TABLE IF NOT EXISTS public.report_history (
    id uuid PRIMARY KEY,
    org_id text,
    tenant_id text,
    report_name text NOT NULL,
    requested_by text,
    delivery_channel text,
    status text,
    recipients jsonb NOT NULL DEFAULT '[]'::jsonb,
    file_name text,
    notes text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_report_history_org_created
    ON public.report_history (org_id, created_at desc);
CREATE UNIQUE INDEX IF NOT EXISTS idx_report_history_id
    ON public.report_history (id);

-- 7. report_distribution_lists table
CREATE TABLE IF NOT EXISTS public.report_distribution_lists (
    id uuid PRIMARY KEY,
    org_id text NOT NULL,
    tenant_id text,
    report_name text NOT NULL DEFAULT 'executive_pdf',
    recipients jsonb NOT NULL DEFAULT '[]'::jsonb,
    active boolean NOT NULL DEFAULT true,
    updated_by text,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_report_distribution_org_report
    ON public.report_distribution_lists (org_id, report_name);

-- 8. (Referenced) unified_cloud_costs, mart_cost_anomalies, mart_optimization_opportunities, and KPI tables
-- These are referenced by views and RLS policies. Ensure they exist and have org_id or tenant_id columns for RLS.
-- If you need DDL for these, please provide your current schema or request a template.

-- End of migration script.
