-- SQLite control metadata extending CMP-P4 source_instances, no cloud-specific fact store.
CREATE TABLE IF NOT EXISTS connector_source_config (
  organization_id TEXT NOT NULL, tenant_id TEXT NOT NULL, source_id TEXT NOT NULL,
  provider TEXT NOT NULL CHECK(provider IN ('aws','azure')),
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
CREATE TABLE IF NOT EXISTS connector_executions (
  execution_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
  source_id TEXT NOT NULL, request_key TEXT NOT NULL, trigger_type TEXT NOT NULL,
  requested_by TEXT NOT NULL, status TEXT NOT NULL
    CHECK(status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')),
  queued_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
  records_discovered INTEGER NOT NULL DEFAULT 0,
  records_ingested INTEGER NOT NULL DEFAULT 0,
  records_rejected INTEGER NOT NULL DEFAULT 0,
  error_category TEXT, safe_error_summary TEXT, evidence_reference TEXT,
  UNIQUE(organization_id,tenant_id,source_id,request_key),
  FOREIGN KEY(organization_id,tenant_id,source_id)
    REFERENCES source_instances(organization_id,tenant_id,source_instance_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS connector_one_running_source
  ON connector_executions(organization_id,tenant_id,source_id)
  WHERE status IN ('QUEUED','RUNNING');
CREATE TABLE IF NOT EXISTS connector_control_audit (
  event_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
  source_id TEXT NOT NULL, actor_id TEXT NOT NULL, action TEXT NOT NULL,
  occurred_at TEXT NOT NULL
);
