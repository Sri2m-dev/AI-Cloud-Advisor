-- SaaS Governance source tables for Supabase.
-- Apply in Supabase SQL editor or fold into your migration process.

CREATE TABLE IF NOT EXISTS saas_licenses (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    vendor TEXT NOT NULL,
    application TEXT NOT NULL,
    category TEXT,
    total_licenses INTEGER NOT NULL DEFAULT 0,
    assigned_licenses INTEGER NOT NULL DEFAULT 0,
    active_users INTEGER NOT NULL DEFAULT 0,
    monthly_cost NUMERIC(14, 2) NOT NULL DEFAULT 0,
    renewal_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS saas_users (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    vendor TEXT NOT NULL,
    application TEXT NOT NULL,
    user_email TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    last_activity_at TIMESTAMPTZ,
    monthly_cost NUMERIC(14, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS saas_tools (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    vendor TEXT NOT NULL,
    application TEXT NOT NULL,
    category TEXT NOT NULL,
    monthly_cost NUMERIC(14, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS saas_contracts (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    vendor TEXT NOT NULL,
    application TEXT NOT NULL,
    renewal_date DATE NOT NULL,
    annual_cost NUMERIC(14, 2) NOT NULL DEFAULT 0,
    owner TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS saas_cost (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    vendor TEXT NOT NULL,
    application TEXT,
    category TEXT,
    billing_month DATE NOT NULL,
    cost NUMERIC(14, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saas_licenses_org ON saas_licenses (organization_id);
CREATE INDEX IF NOT EXISTS idx_saas_users_org ON saas_users (organization_id);
CREATE INDEX IF NOT EXISTS idx_saas_tools_org ON saas_tools (organization_id);
CREATE INDEX IF NOT EXISTS idx_saas_contracts_org ON saas_contracts (organization_id);
CREATE INDEX IF NOT EXISTS idx_saas_cost_org_month ON saas_cost (organization_id, billing_month);
