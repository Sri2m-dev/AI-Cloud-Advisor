-- SQLite control metadata extending connector_source_config to support M365 / Entra ID.
-- Drop and recreate connector_source_config with 'm365' provider support.
CREATE TABLE IF NOT EXISTS connector_source_config_new (
  organization_id TEXT NOT NULL, tenant_id TEXT NOT NULL, source_id TEXT NOT NULL,
  provider TEXT NOT NULL CHECK(provider IN ('aws','azure','m365')),
  account_id TEXT NOT NULL, display_name TEXT NOT NULL, config_json TEXT NOT NULL,
  credential_ciphertext TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('DRAFT','VALIDATING','READY','ACTIVE','ERROR','DISABLED')),
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  last_success_at TEXT, last_error_category TEXT, safe_error_summary TEXT,
  schedule_enabled INTEGER NOT NULL DEFAULT 0 CHECK(schedule_enabled IN (0,1)),
  cadence_seconds INTEGER NOT NULL DEFAULT 86400 CHECK(cadence_seconds >= 3600),
  next_run_at TEXT,
  PRIMARY KEY(organization_id,tenant_id,source_id),
  UNIQUE(organization_id,tenant_id,provider,account_id),
  FOREIGN KEY(organization_id,tenant_id,source_id)
    REFERENCES source_instances(organization_id,tenant_id,source_instance_id)
);

INSERT OR IGNORE INTO connector_source_config_new
  SELECT organization_id, tenant_id, source_id, provider, account_id, display_name,
         config_json, credential_ciphertext, status, created_by, created_at, updated_at,
         last_success_at, last_error_category, safe_error_summary, schedule_enabled,
         cadence_seconds, next_run_at
  FROM connector_source_config;

DROP TABLE IF EXISTS connector_source_config;
ALTER TABLE connector_source_config_new RENAME TO connector_source_config;
