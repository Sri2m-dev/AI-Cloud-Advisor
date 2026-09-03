# ruff: noqa: E501
"""Cohesive SQLite persistence for CMP-P4 source authority."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from data_fabric.source_facts.models import (
    AuthorityPolicy,
    FactType,
    Freshness,
    LifecycleState,
    ReconciliationResult,
    SourceFact,
    SourceInstance,
)


class SQLiteSourceFactRepository:
    """Tenant-scoped durable store; facts and decisions are append-only."""

    def __init__(self, database: str | Path):
        self.database = str(database)
        self._migrate()

    @contextmanager
    def transaction(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def save_instance(self, instance: SourceInstance) -> None:
        with self.transaction() as db:
            db.execute(
                "INSERT OR REPLACE INTO source_instances VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    instance.source_instance_id,
                    instance.organization_id,
                    instance.tenant_id,
                    instance.source_type,
                    instance.source_system,
                    instance.connector_type,
                    instance.connector_version,
                    instance.configuration_reference,
                    instance.credential_reference,
                    int(instance.enabled),
                    instance.updated_at.isoformat(),
                ),
            )

    def instance_enabled(self, organization_id, tenant_id, source_instance_id):
        with sqlite3.connect(self.database) as db:
            row = db.execute(
                "SELECT enabled FROM source_instances WHERE organization_id=? AND tenant_id=? AND source_instance_id=?",
                (organization_id, tenant_id, source_instance_id),
            ).fetchone()
            return bool(row[0]) if row else False

    def current_fact(self, organization_id, tenant_id, observation_key, db=None):
        owns = db is None
        db = db or sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        try:
            row = db.execute(
                "SELECT * FROM source_facts WHERE organization_id=? AND tenant_id=? AND observation_key=? ORDER BY fact_version DESC LIMIT 1",
                (organization_id, tenant_id, observation_key),
            ).fetchone()
            return _fact(row) if row else None
        finally:
            if owns:
                db.close()

    def list_current_facts(self, organization_id, tenant_id):
        with sqlite3.connect(self.database) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT f.* FROM source_facts f JOIN (SELECT observation_key, MAX(fact_version) v FROM source_facts WHERE organization_id=? AND tenant_id=? GROUP BY observation_key) c ON c.observation_key=f.observation_key AND c.v=f.fact_version WHERE f.organization_id=? AND f.tenant_id=?",
                (organization_id, tenant_id, organization_id, tenant_id),
            ).fetchall()
            return tuple(_fact(row) for row in rows)

    def append_policy(self, policy: AuthorityPolicy) -> None:
        with self.transaction() as db:
            db.execute(
                "INSERT INTO authority_policies VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    policy.policy_id,
                    policy.organization_id,
                    policy.tenant_id,
                    policy.fact_type.value,
                    policy.policy_version,
                    _json(policy.source_priorities),
                    _json(policy.permitted_sources),
                    int(policy.confirmation_required),
                    policy.fresh_for_seconds,
                    policy.effective_from.isoformat(),
                    _iso(policy.effective_to),
                ),
            )

    def effective_policy(self, organization_id, tenant_id, fact_type, at):
        with sqlite3.connect(self.database) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM authority_policies WHERE organization_id=? AND tenant_id=? AND fact_type=? AND effective_from<=? AND (effective_to IS NULL OR effective_to>?) ORDER BY policy_version DESC LIMIT 1",
                (
                    organization_id,
                    tenant_id,
                    FactType(fact_type).value,
                    at.isoformat(),
                    at.isoformat(),
                ),
            ).fetchone()
            return _policy(row) if row else None

    def append_reconciliation(self, result: ReconciliationResult) -> None:
        with self.transaction() as db:
            db.execute(
                "INSERT INTO reconciliations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    result.reconciliation_id,
                    result.organization_id,
                    result.tenant_id,
                    result.subject_reference,
                    result.predicate,
                    _json(result.contributing_fact_ids),
                    result.policy_id,
                    result.policy_version,
                    result.outcome.value,
                    result.selected_fact_id,
                    result.reason,
                    result.decided_at.isoformat(),
                    result.actor,
                    result.actor_role,
                    result.supersedes,
                ),
            )

    def purge_source(self, organization_id, tenant_id, source_instance_id):
        with self.transaction() as db:
            db.execute(
                "UPDATE source_instances SET enabled=0 WHERE organization_id=? AND tenant_id=? AND source_instance_id=?",
                (organization_id, tenant_id, source_instance_id),
            )
            return db.execute(
                "SELECT COUNT(*) FROM source_facts WHERE organization_id=? AND tenant_id=? AND source_instance_id=?",
                (organization_id, tenant_id, source_instance_id),
            ).fetchone()[0]

    def run_counts(self, organization_id, tenant_id, source_instance_id):
        with sqlite3.connect(self.database) as db:
            rows = db.execute(
                "SELECT status, COUNT(*) FROM ingestion_runs WHERE organization_id=? AND tenant_id=? AND source_instance_id=? GROUP BY status",
                (organization_id, tenant_id, source_instance_id),
            ).fetchall()
            return dict(rows)

    def _migrate(self):
        with sqlite3.connect(self.database) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS source_instances (
                  source_instance_id TEXT, organization_id TEXT, tenant_id TEXT, source_type TEXT,
                  source_system TEXT, connector_type TEXT, connector_version TEXT,
                  configuration_reference TEXT, credential_reference TEXT, enabled INTEGER,
                  updated_at TEXT, PRIMARY KEY(organization_id,tenant_id,source_instance_id));
                CREATE TABLE IF NOT EXISTS source_facts (
                  source_fact_id TEXT PRIMARY KEY, observation_key TEXT, fact_version INTEGER,
                  organization_id TEXT, tenant_id TEXT, source_instance_id TEXT, source_type TEXT,
                  source_system TEXT, connector_version TEXT, ingestion_run_id TEXT,
                  source_record_id TEXT, fact_type TEXT, subject_reference TEXT, predicate TEXT,
                  value_json TEXT, object_reference TEXT, observed_at TEXT, effective_from TEXT,
                  effective_to TEXT, source_schema_version TEXT, quality REAL, freshness TEXT,
                  evidence_reference TEXT, lineage_json TEXT, provenance_json TEXT,
                  lifecycle TEXT, fingerprint TEXT,
                  UNIQUE(organization_id,tenant_id,observation_key,fact_version));
                CREATE TABLE IF NOT EXISTS ingestion_runs (
                  run_id TEXT, organization_id TEXT, tenant_id TEXT,
                  source_instance_id TEXT, mode TEXT, status TEXT, started_at TEXT,
                  completed_at TEXT, records_seen INTEGER, facts_published INTEGER,
                  facts_unchanged INTEGER, facts_quarantined INTEGER, errors_json TEXT,
                  checkpoint_before TEXT, checkpoint_after TEXT, schema_fingerprint TEXT,
                  correlation_id TEXT, PRIMARY KEY(organization_id,tenant_id,run_id));
                CREATE TABLE IF NOT EXISTS source_state (
                  organization_id TEXT, tenant_id TEXT, source_instance_id TEXT,
                  checkpoint TEXT, schema_json TEXT, schema_fingerprint TEXT,
                  last_attempt TEXT, last_success TEXT, status TEXT, correlation_id TEXT,
                  partial_failure_count INTEGER DEFAULT 0,
                  PRIMARY KEY(organization_id,tenant_id,source_instance_id));
                CREATE TABLE IF NOT EXISTS authority_policies (
                  policy_id TEXT, organization_id TEXT, tenant_id TEXT, fact_type TEXT,
                  policy_version INTEGER, priorities_json TEXT, permitted_json TEXT,
                  confirmation_required INTEGER, fresh_for_seconds INTEGER,
                  effective_from TEXT, effective_to TEXT,
                  PRIMARY KEY(organization_id,tenant_id,policy_id));
                CREATE TABLE IF NOT EXISTS reconciliations (
                  reconciliation_id TEXT, organization_id TEXT, tenant_id TEXT,
                  subject_reference TEXT, predicate TEXT, fact_ids_json TEXT, policy_id TEXT,
                  policy_version INTEGER, outcome TEXT, selected_fact_id TEXT, reason TEXT,
                  decided_at TEXT, actor TEXT, actor_role TEXT, supersedes TEXT,
                  PRIMARY KEY(organization_id,tenant_id,reconciliation_id));
                """
            )


def _fact(row):
    values = dict(row)
    return SourceFact(
        **{
            **{key: values[key] for key in SourceFact.__dataclass_fields__ if key in values},
            "fact_type": FactType(values["fact_type"]),
            "value": json.loads(values["value_json"]),
            "observed_at": datetime.fromisoformat(values["observed_at"]),
            "effective_from": _dt(values["effective_from"]),
            "effective_to": _dt(values["effective_to"]),
            "freshness": Freshness(values["freshness"]),
            "lineage": json.loads(values["lineage_json"]),
            "provenance": json.loads(values["provenance_json"]),
            "lifecycle": LifecycleState(values["lifecycle"]),
        }
    )


def _policy(row):
    value = dict(row)
    return AuthorityPolicy(
        value["policy_id"],
        value["organization_id"],
        value["tenant_id"],
        FactType(value["fact_type"]),
        value["policy_version"],
        tuple(json.loads(value["priorities_json"])),
        tuple(json.loads(value["permitted_json"])),
        bool(value["confirmation_required"]),
        value["fresh_for_seconds"],
        datetime.fromisoformat(value["effective_from"]),
        _dt(value["effective_to"]),
    )


def _json(value):
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _iso(value):
    return value.isoformat() if value else None


def _dt(value):
    return datetime.fromisoformat(value) if value else None
