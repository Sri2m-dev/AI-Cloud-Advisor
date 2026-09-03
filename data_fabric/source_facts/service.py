# ruff: noqa: E501
"""Publication, reconciliation, explanation, and health services for CMP-P4."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from data_fabric.foundation import TenantContext
from data_fabric.source_facts.models import (
    AuthorityPolicy,
    Freshness,
    LifecycleState,
    ReconciliationOutcome,
    ReconciliationResult,
    RunMode,
    RunStatus,
    SchemaChange,
    SourceFact,
    SourceFactInput,
    SourceHealth,
    SourceInstance,
)


@dataclass(frozen=True, slots=True)
class PublicationResult:
    run_id: str
    status: RunStatus
    facts: tuple[SourceFact, ...]
    unchanged: int
    quarantined: int
    schema_change: SchemaChange
    checkpoint_after: str | None


class SourceFactService:
    def __init__(self, context: TenantContext, repository):
        self.context, self.repository = context, repository

    def register(self, instance: SourceInstance):
        self.context.assert_record_matches(instance, "source instance")
        if instance.credential_reference and any(
            marker in instance.credential_reference.casefold()
            for marker in ("password=", "secret=", "bearer ", "sk-")
        ):
            raise ValueError("credential_reference must be an opaque reference, not a secret")
        self.repository.save_instance(instance)

    def publish(
        self,
        instance: SourceInstance,
        records: tuple[SourceFactInput, ...],
        *,
        run_id: str,
        mode: RunMode = RunMode.FULL,
        checkpoint_before: str | None = None,
        checkpoint_after: str | None = None,
        status: RunStatus = RunStatus.SUCCESS,
        schema: dict[str, str] | None = None,
        required_fields: tuple[str, ...] = (),
        correlation_id: str | None = None,
        error: str | None = None,
    ) -> PublicationResult:
        mode = RunMode(mode)
        status = RunStatus(status)
        self.context.assert_record_matches(instance, "source instance")
        if not instance.enabled or not self.repository.instance_enabled(
            self.context.organization_id,
            self.context.tenant_id,
            instance.source_instance_id,
        ):
            raise ValueError("source instance is disabled")
        schema = schema or {}
        schema_fp = _hash(schema)
        started = datetime.now(timezone.utc)
        with self.repository.transaction() as db:
            state = db.execute(
                "SELECT * FROM source_state WHERE organization_id=? AND tenant_id=? AND source_instance_id=?",
                (self.context.organization_id, self.context.tenant_id, instance.source_instance_id),
            ).fetchone()
            change = _schema_change(state, schema, required_fields)
            quarantine = change in {
                SchemaChange.INCOMPATIBLE,
                SchemaChange.MAPPING_REQUIRED,
                SchemaChange.UNKNOWN,
            }
            facts, unchanged = [], 0
            if not quarantine:
                for record in records:
                    fact = self._fact(instance, record, run_id, db)
                    if fact is None:
                        unchanged += 1
                    else:
                        _insert_fact(db, fact)
                        facts.append(fact)
            effective_status = RunStatus.QUARANTINED if quarantine else status
            safe_checkpoint = (
                checkpoint_after if effective_status is RunStatus.SUCCESS else checkpoint_before
            )
            completed = datetime.now(timezone.utc)
            safe_error = _redact(error)
            db.execute(
                "INSERT INTO ingestion_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    self.context.organization_id,
                    self.context.tenant_id,
                    instance.source_instance_id,
                    mode.value,
                    effective_status.value,
                    started.isoformat(),
                    completed.isoformat(),
                    len(records),
                    len(facts),
                    unchanged,
                    len(records) if quarantine else 0,
                    json.dumps([safe_error] if safe_error else []),
                    checkpoint_before,
                    safe_checkpoint,
                    schema_fp,
                    correlation_id,
                ),
            )
            db.execute(
                "INSERT OR REPLACE INTO source_state VALUES (?,?,?,?,?,?,?,?,?,?,COALESCE((SELECT partial_failure_count FROM source_state WHERE organization_id=? AND tenant_id=? AND source_instance_id=?),0)+?)",
                (
                    self.context.organization_id,
                    self.context.tenant_id,
                    instance.source_instance_id,
                    safe_checkpoint,
                    json.dumps(schema, sort_keys=True),
                    schema_fp,
                    completed.isoformat(),
                    completed.isoformat()
                    if effective_status is RunStatus.SUCCESS
                    else (state["last_success"] if state else None),
                    effective_status.value,
                    correlation_id,
                    self.context.organization_id,
                    self.context.tenant_id,
                    instance.source_instance_id,
                    1 if effective_status in {RunStatus.PARTIAL, RunStatus.FAILED} else 0,
                ),
            )
        return PublicationResult(
            run_id,
            effective_status,
            tuple(facts),
            unchanged,
            len(records) if quarantine else 0,
            change,
            safe_checkpoint,
        )

    def _fact(self, instance, record, run_id, db):
        if not record.source_record_id or not record.subject_reference or not record.predicate:
            raise ValueError("source record, subject, and predicate are required")
        if (
            record.effective_to
            and record.effective_from
            and record.effective_to <= record.effective_from
        ):
            raise ValueError("effective_to must be after effective_from")
        observation = _hash(
            (
                self.context.organization_id,
                self.context.tenant_id,
                instance.source_instance_id,
                record.source_record_id,
                record.predicate,
                _iso(record.effective_from),
            )
        )
        content = {
            "fact_type": record.fact_type.value,
            "subject": record.subject_reference,
            "predicate": record.predicate,
            "value": record.value,
            "object": record.object_reference,
            "effective_from": _iso(record.effective_from),
            "effective_to": _iso(record.effective_to),
            "lifecycle": record.lifecycle.value,
            "schema": record.source_schema_version,
        }
        fingerprint = _hash(content)
        current = self.repository.current_fact(
            self.context.organization_id, self.context.tenant_id, observation, db
        )
        if current and current.fingerprint == fingerprint:
            return None
        version = (current.fact_version + 1) if current else 1
        return SourceFact(
            f"sf:{observation[:20]}:{version}",
            observation,
            version,
            self.context.organization_id,
            self.context.tenant_id,
            instance.source_instance_id,
            instance.source_type,
            instance.source_system,
            instance.connector_version,
            run_id,
            record.source_record_id,
            record.fact_type,
            record.subject_reference,
            record.predicate,
            record.value,
            record.object_reference,
            record.observed_at,
            record.effective_from,
            record.effective_to,
            record.source_schema_version,
            record.quality,
            record.freshness,
            record.evidence_reference,
            dict(record.lineage),
            dict(record.provenance),
            record.lifecycle,
            fingerprint,
        )

    def reconcile(
        self,
        facts: tuple[SourceFact, ...],
        *,
        policy: AuthorityPolicy | None = None,
        actor: str | None = None,
        actor_role: str | None = None,
        selected_fact_id: str | None = None,
        reason: str | None = None,
    ):
        if not facts:
            raise ValueError("facts are required")
        for fact in facts:
            self.context.assert_record_matches(fact, "source fact")
        keys = {(fact.subject_reference, fact.predicate, fact.fact_type) for fact in facts}
        if len(keys) != 1:
            raise ValueError("only facts for one subject/predicate/type may be reconciled")
        active = tuple(fact for fact in facts if fact.lifecycle is LifecycleState.ACTIVE)
        values = {_hash((fact.value, fact.object_reference)) for fact in active}
        selected = None
        if selected_fact_id:
            if not actor or not actor_role or not reason:
                raise ValueError("human decisions require actor, role, and reason")
            selected = next(
                (fact for fact in active if fact.source_fact_id == selected_fact_id), None
            )
            if selected is None:
                raise ValueError("selected fact is not a contributor")
            outcome = ReconciliationOutcome.SOURCE_PRIORITY_RESOLVED
            why = reason
        elif not active:
            outcome, why = ReconciliationOutcome.UNRESOLVED, "no active source facts"
        elif len(values) == 1:
            selected, outcome, why = active[0], ReconciliationOutcome.CONSISTENT, "sources agree"
        elif policy:
            permitted = (
                active
                if not policy.permitted_sources
                else tuple(
                    fact for fact in active if fact.source_system in policy.permitted_sources
                )
            )
            selected = next(
                (
                    fact
                    for source in policy.source_priorities
                    for fact in permitted
                    if fact.source_system == source
                ),
                None,
            )
            if selected and not policy.confirmation_required:
                outcome, why = (
                    ReconciliationOutcome.SOURCE_PRIORITY_RESOLVED,
                    "fact-specific authority policy",
                )
            else:
                selected, outcome, why = (
                    None,
                    ReconciliationOutcome.HUMAN_REVIEW_REQUIRED,
                    "conflicting evidence requires governance",
                )
        elif any(fact.freshness is Freshness.STALE for fact in active):
            outcome, why = (
                ReconciliationOutcome.STALE_SOURCE,
                "conflict includes stale source evidence",
            )
        else:
            outcome, why = (
                ReconciliationOutcome.CANDIDATE_CONFLICT,
                "equal-authority sources disagree",
            )
        subject, predicate, _ = next(iter(keys))
        now = datetime.now(timezone.utc)
        result = ReconciliationResult(
            "rec:"
            + _hash(
                (
                    self.context.organization_id,
                    self.context.tenant_id,
                    subject,
                    predicate,
                    tuple(sorted(f.source_fact_id for f in facts)),
                    policy.policy_id if policy else None,
                    selected_fact_id,
                )
            )[:24],
            self.context.organization_id,
            self.context.tenant_id,
            subject,
            predicate,
            tuple(sorted(f.source_fact_id for f in facts)),
            policy.policy_id if policy else None,
            policy.policy_version if policy else None,
            outcome,
            selected.source_fact_id if selected else None,
            why,
            now,
            actor,
            actor_role,
        )
        self.repository.append_reconciliation(result)
        return result

    @staticmethod
    def explain(result: ReconciliationResult, facts: tuple[SourceFact, ...], policy=None):
        by_id = {fact.source_fact_id: fact for fact in facts}
        return {
            "canonical_decision": result.outcome.value,
            "selected_fact_id": result.selected_fact_id,
            "reason": result.reason,
            "policy": {"id": result.policy_id, "version": result.policy_version},
            "sources": tuple(
                {
                    "fact_id": fact_id,
                    "source_instance": by_id[fact_id].source_instance_id,
                    "source_system": by_id[fact_id].source_system,
                    "fact_version": by_id[fact_id].fact_version,
                    "freshness": by_id[fact_id].freshness.value,
                    "evidence": by_id[fact_id].evidence_reference,
                    "fingerprint": by_id[fact_id].fingerprint,
                }
                for fact_id in result.contributing_fact_ids
            ),
            "human_decision": {"actor": result.actor, "role": result.actor_role}
            if result.actor
            else None,
        }

    def health(self, instance: SourceInstance):
        with self.repository.transaction() as db:
            state = db.execute(
                "SELECT * FROM source_state WHERE organization_id=? AND tenant_id=? AND source_instance_id=?",
                (self.context.organization_id, self.context.tenant_id, instance.source_instance_id),
            ).fetchone()
            facts = [
                fact
                for fact in self.repository.list_current_facts(
                    self.context.organization_id, self.context.tenant_id
                )
                if fact.source_instance_id == instance.source_instance_id
            ]
            counts = self.repository.run_counts(
                self.context.organization_id,
                self.context.tenant_id,
                instance.source_instance_id,
            )
        return SourceHealth(
            instance.source_instance_id,
            _dt(state["last_attempt"]) if state else None,
            _dt(state["last_success"]) if state else None,
            RunStatus(state["status"]) if state else None,
            state["checkpoint"] if state else None,
            instance.connector_version,
            state["schema_fingerprint"] if state else None,
            sum(f.freshness is Freshness.FRESH for f in facts),
            sum(f.freshness is Freshness.STALE for f in facts),
            counts.get(RunStatus.QUARANTINED.value, 0),
            (counts.get(RunStatus.PARTIAL.value, 0) + counts.get(RunStatus.FAILED.value, 0)),
            state["correlation_id"] if state else None,
        )


def _insert_fact(db, fact):
    values = asdict(fact)
    db.execute(
        "INSERT INTO source_facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            fact.source_fact_id,
            fact.observation_key,
            fact.fact_version,
            fact.organization_id,
            fact.tenant_id,
            fact.source_instance_id,
            fact.source_type,
            fact.source_system,
            fact.connector_version,
            fact.ingestion_run_id,
            fact.source_record_id,
            fact.fact_type.value,
            fact.subject_reference,
            fact.predicate,
            json.dumps(fact.value, sort_keys=True, default=str),
            fact.object_reference,
            fact.observed_at.isoformat(),
            _iso(fact.effective_from),
            _iso(fact.effective_to),
            fact.source_schema_version,
            fact.quality,
            fact.freshness.value,
            fact.evidence_reference,
            json.dumps(values["lineage"], default=str),
            json.dumps(values["provenance"], default=str),
            fact.lifecycle.value,
            fact.fingerprint,
        ),
    )


def _schema_change(state, schema, required):
    if not state:
        return SchemaChange.COMPATIBLE
    old = json.loads(state["schema_json"] or "{}")
    if old == schema:
        return SchemaChange.COMPATIBLE
    missing = [field for field in required if field not in schema]
    if missing:
        return SchemaChange.INCOMPATIBLE
    changed = [field for field in old if field in schema and old[field] != schema[field]]
    if changed:
        return SchemaChange.MAPPING_REQUIRED
    if set(schema) > set(old):
        return SchemaChange.COMPATIBLE_ADDITIVE
    return SchemaChange.UNKNOWN


def _hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _iso(value):
    return value.isoformat() if value else None


def _dt(value):
    return datetime.fromisoformat(value) if value else None


def _redact(value):
    if not value:
        return None
    text = str(value)
    for marker in ("password", "secret", "token", "credential"):
        if marker in text.casefold():
            return "[REDACTED_ERROR]"
    return text[:500]
