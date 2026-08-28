CREATE TABLE IF NOT EXISTS universal_evidence_migrations (
    migration_id TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS universal_evidence_lifecycle (
    object_type TEXT NOT NULL,
    object_key TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    prospect_id TEXT NOT NULL DEFAULT '',
    analysis_id TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    payload_json TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (object_type, object_key, organization_id, tenant_id, prospect_id, analysis_id)
);

CREATE INDEX IF NOT EXISTS idx_ue_lifecycle_scope
    ON universal_evidence_lifecycle (organization_id, tenant_id, prospect_id, analysis_id);
CREATE INDEX IF NOT EXISTS idx_ue_lifecycle_fingerprint
    ON universal_evidence_lifecycle (organization_id, tenant_id, fingerprint);

CREATE TABLE IF NOT EXISTS universal_evidence_audit (
    audit_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_key TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    prospect_id TEXT NOT NULL DEFAULT '',
    analysis_id TEXT NOT NULL DEFAULT '',
    fingerprint TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ue_audit_scope
    ON universal_evidence_audit (organization_id, tenant_id, prospect_id, analysis_id, occurred_at);

INSERT OR IGNORE INTO universal_evidence_migrations (migration_id)
VALUES ('0001_create_lifecycle_state');
