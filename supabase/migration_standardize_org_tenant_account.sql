-- Standardize org_id, tenant_id, account_id across all marts and workflows
-- Run this migration in your Supabase SQL editor or psql client

-- Example for key marts/workflow tables (repeat for all relevant tables)

ALTER TABLE IF EXISTS public.kpi_total_cloud_spend
    ADD COLUMN IF NOT EXISTS org_id TEXT,
    ADD COLUMN IF NOT EXISTS tenant_id TEXT,
    ADD COLUMN IF NOT EXISTS account_id TEXT;
CREATE INDEX IF NOT EXISTS idx_kpi_total_cloud_spend_org_id ON public.kpi_total_cloud_spend (org_id);
CREATE INDEX IF NOT EXISTS idx_kpi_total_cloud_spend_tenant_id ON public.kpi_total_cloud_spend (tenant_id);
CREATE INDEX IF NOT EXISTS idx_kpi_total_cloud_spend_account_id ON public.kpi_total_cloud_spend (account_id);

ALTER TABLE IF EXISTS public.kpi_spend_by_cloud
    ADD COLUMN IF NOT EXISTS org_id TEXT,
    ADD COLUMN IF NOT EXISTS tenant_id TEXT,
    ADD COLUMN IF NOT EXISTS account_id TEXT;
CREATE INDEX IF NOT EXISTS idx_kpi_spend_by_cloud_org_id ON public.kpi_spend_by_cloud (org_id);
CREATE INDEX IF NOT EXISTS idx_kpi_spend_by_cloud_tenant_id ON public.kpi_spend_by_cloud (tenant_id);
CREATE INDEX IF NOT EXISTS idx_kpi_spend_by_cloud_account_id ON public.kpi_spend_by_cloud (account_id);

ALTER TABLE IF EXISTS public.kpi_top_services
    ADD COLUMN IF NOT EXISTS org_id TEXT,
    ADD COLUMN IF NOT EXISTS tenant_id TEXT,
    ADD COLUMN IF NOT EXISTS account_id TEXT;
CREATE INDEX IF NOT EXISTS idx_kpi_top_services_org_id ON public.kpi_top_services (org_id);
CREATE INDEX IF NOT EXISTS idx_kpi_top_services_tenant_id ON public.kpi_top_services (tenant_id);
CREATE INDEX IF NOT EXISTS idx_kpi_top_services_account_id ON public.kpi_top_services (account_id);

ALTER TABLE IF EXISTS public.mart_cost_anomalies
    ADD COLUMN IF NOT EXISTS org_id TEXT,
    ADD COLUMN IF NOT EXISTS tenant_id TEXT,
    ADD COLUMN IF NOT EXISTS account_id TEXT;
CREATE INDEX IF NOT EXISTS idx_mart_cost_anomalies_org_id ON public.mart_cost_anomalies (org_id);
CREATE INDEX IF NOT EXISTS idx_mart_cost_anomalies_tenant_id ON public.mart_cost_anomalies (tenant_id);
CREATE INDEX IF NOT EXISTS idx_mart_cost_anomalies_account_id ON public.mart_cost_anomalies (account_id);

ALTER TABLE IF EXISTS public.mart_optimization_opportunities
    ADD COLUMN IF NOT EXISTS org_id TEXT,
    ADD COLUMN IF NOT EXISTS tenant_id TEXT,
    ADD COLUMN IF NOT EXISTS account_id TEXT;
CREATE INDEX IF NOT EXISTS idx_mart_optimization_opportunities_org_id ON public.mart_optimization_opportunities (org_id);
CREATE INDEX IF NOT EXISTS idx_mart_optimization_opportunities_tenant_id ON public.mart_optimization_opportunities (tenant_id);
CREATE INDEX IF NOT EXISTS idx_mart_optimization_opportunities_account_id ON public.mart_optimization_opportunities (account_id);

-- Repeat for all other marts, workflow, and reporting tables as needed
-- Ensure all ETL and data access code is updated to read/write these columns
