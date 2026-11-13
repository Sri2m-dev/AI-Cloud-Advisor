CREATE TABLE IF NOT EXISTS customer_workflow_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'WORKSPACE_CREATED',
            'EVIDENCE_ADMITTED',
            'ASK_ANSWERED',
            'DECISION_CREATED',
            'APPROVAL_REQUESTED',
            'APPROVAL_TRANSITIONED',
            'EVIDENCE_EXPORT_CREATED'
        )
    ),
    organization_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    payload_fingerprint TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    UNIQUE (organization_id, tenant_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_customer_workflow_scope
    ON customer_workflow_events (
        organization_id, tenant_id, workspace_id, occurred_at, event_id
    );

CREATE TRIGGER IF NOT EXISTS customer_workflow_events_no_update
BEFORE UPDATE ON customer_workflow_events
BEGIN
    SELECT RAISE(ABORT, 'customer workflow events are append-only');
END;

CREATE TRIGGER IF NOT EXISTS customer_workflow_events_no_delete
BEFORE DELETE ON customer_workflow_events
BEGIN
    SELECT RAISE(ABORT, 'customer workflow events are append-only');
END;

INSERT OR IGNORE INTO universal_evidence_migrations (migration_id)
VALUES ('0002_create_customer_workflow_events');
