"""Default orchestration policies for quality, lineage, and versioning."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from data_fabric.foundation import DefaultDeterministicSerializer
from data_fabric.lineage import LineageEvent, ProvenanceRecord
from data_fabric.quality import QualityAssessment
from data_fabric.orchestration.interfaces import (
    LineageEmissionPolicy,
    QualityGatePolicy,
    VersionCreationPolicy,
)
from data_fabric.orchestration.models import (
    CanonicalizationResult,
    EntityWriteAction,
    EntityWritePlan,
    LineageEmissionPlan,
    QualityGateDecision,
    QualityGateOutcome,
    VersionDecision,
    VersionDecisionAction,
    IngestionRequest,
)


class DefaultQualityGatePolicy(QualityGatePolicy):
    """Deterministic quality gate policy for 0-100 trust scores."""

    def __init__(self, hard_threshold: float = 60.0, warning_threshold: float = 85.0) -> None:
        self.hard_threshold = hard_threshold
        self.warning_threshold = warning_threshold

    def decide(self, assessment: QualityAssessment) -> QualityGateDecision:
        blocking = [issue for issue in assessment.issues if issue.is_blocking]
        score = assessment.trust_score.final_score
        if blocking:
            return QualityGateDecision(
                QualityGateOutcome.REJECT,
                assessment,
                tuple(f"blocking quality issue: {issue.message}" for issue in blocking),
            )
        if score < self.hard_threshold:
            return QualityGateDecision(
                QualityGateOutcome.QUARANTINE,
                assessment,
                (f"trust score {score:.2f} below hard threshold {self.hard_threshold:.2f}",),
            )
        if score < self.warning_threshold:
            return QualityGateDecision(
                QualityGateOutcome.ALLOW_WITH_WARNING,
                assessment,
                (f"trust score {score:.2f} below warning threshold {self.warning_threshold:.2f}",),
            )
        return QualityGateDecision(
            QualityGateOutcome.ALLOW,
            assessment,
            (f"trust score {score:.2f} meets threshold",),
        )


class DefaultVersionCreationPolicy(VersionCreationPolicy):
    """Deterministic version decision policy for prepared write plans."""

    def __init__(self, serializer: DefaultDeterministicSerializer | None = None) -> None:
        self._serializer = serializer or DefaultDeterministicSerializer()

    def decide(
        self,
        plan: EntityWritePlan,
        previous_hash: str | None = None,
        force: bool = False,
    ) -> VersionDecision:
        entity = plan.entity or plan.existing_entity
        subject_id = entity.id if entity is not None else ""
        new_hash = self._payload_hash(entity) if entity is not None else None
        version = getattr(entity, "version", 1) if entity is not None else 1
        if plan.action is EntityWriteAction.REJECT:
            return VersionDecision(
                VersionDecisionAction.REJECT_OUT_OF_ORDER,
                subject_id,
                previous_hash,
                new_hash,
                version,
                ("rejected write plan cannot create a version",),
            )
        if force:
            return VersionDecision(
                VersionDecisionAction.FORCE_VERSION,
                subject_id,
                previous_hash,
                new_hash,
                version,
                ("force_version requested",),
            )
        if previous_hash is None:
            return VersionDecision(
                VersionDecisionAction.CREATE_INITIAL_VERSION,
                subject_id,
                previous_hash,
                new_hash,
                version,
                ("no previous payload hash",),
            )
        if previous_hash == new_hash:
            return VersionDecision(
                VersionDecisionAction.SKIP_UNCHANGED,
                subject_id,
                previous_hash,
                new_hash,
                version,
                ("payload hash unchanged",),
            )
        return VersionDecision(
            VersionDecisionAction.CREATE_CHANGED_VERSION,
            subject_id,
            previous_hash,
            new_hash,
            version + 1,
            ("payload hash changed",),
        )

    def _payload_hash(self, value: Any) -> str:
        if is_dataclass(value):
            payload = asdict(value)
            payload.pop("created_at", None)
            payload.pop("updated_at", None)
            return self._serializer.content_hash(payload)
        if isinstance(value, Mapping):
            return self._serializer.content_hash(value)
        return self._serializer.content_hash({"value": value})


class DefaultLineageEmissionPolicy(LineageEmissionPolicy):
    """Prepare explainability emission plans without mutating trackers."""

    def plan(
        self,
        request: IngestionRequest,
        result: CanonicalizationResult | None,
    ) -> LineageEmissionPlan:
        now = datetime.now(timezone.utc)
        entity_id = None
        relationship_id = None
        if result is not None:
            entity_id = result.entity_plan.entity.id if result.entity_plan.entity is not None else None
            for relationship_plan in result.relationship_plans:
                if relationship_plan.relationship is not None:
                    relationship_id = relationship_plan.relationship.id
                    break
        base = {
            "source_system": request.source_system,
            "source_identifier": request.source_identifier,
            "organization_id": request.tenant_context.organization_id,
            "tenant_id": request.tenant_context.tenant_id,
            "entity_id": entity_id,
            "relationship_id": relationship_id,
            "occurred_at": now,
        }
        events = (
            LineageEvent(
                id=f"{request.request_id}:source",
                event_type="source",
                raw_record_id=request.source_identifier,
                metadata={"correlation_id": request.correlation_id},
                **base,
            ),
            LineageEvent(
                id=f"{request.request_id}:normalization",
                event_type="normalization",
                normalized_record_id=f"normalized:{request.source_identifier}",
                transformation_name="default_canonicalization_pipeline",
                transformation_version="p3.10b",
                metadata={"source_type": request.source_type},
                **base,
            ),
            LineageEvent(
                id=f"{request.request_id}:canonicalization",
                event_type="canonicalization",
                transformation_name="canonical_entity_plan",
                transformation_version="p3.10b",
                metadata={"quality_outcome": _quality_outcome(result)},
                **base,
            ),
        )
        provenance = (
            ProvenanceRecord(
                id=f"{request.request_id}:provenance",
                source_system=request.source_system,
                source_identifier=request.source_identifier,
                organization_id=request.tenant_context.organization_id,
                collection_method="orchestration_contract",
                tenant_id=request.tenant_context.tenant_id,
                entity_id=entity_id,
                relationship_id=relationship_id,
                connector_version=request.provider,
                normalization_rule="default_canonicalization_pipeline",
                captured_at=now,
                metadata={"correlation_id": request.correlation_id},
            ),
        )
        relationship_event = relationship_id is not None
        rejection = result is not None and result.quality_decision.outcome in {
            QualityGateOutcome.REJECT,
            QualityGateOutcome.QUARANTINE,
        }
        return LineageEmissionPlan(
            emit_source_event=True,
            emit_normalization_event=True,
            emit_semantic_mapping_event=True,
            emit_identity_resolution_event=True,
            emit_canonicalization_event=True,
            emit_quality_assessment_event=True,
            emit_version_event=True,
            emit_relationship_event=relationship_event,
            emit_rejection_or_quarantine_event=rejection,
            events=events,
            provenance_records=provenance,
            explanation=(
                "source, normalization, canonicalization, quality, version, semantic, and identity decisions are explainable",
            ),
        )


def _quality_outcome(result: CanonicalizationResult | None) -> str | None:
    if result is None:
        return None
    return result.quality_decision.outcome.value

