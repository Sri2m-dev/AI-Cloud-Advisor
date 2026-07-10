"""In-memory orchestration coordinator and canonicalization pipeline."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from data_fabric.contracts import EnterpriseEntity
from data_fabric.foundation import DefaultDeterministicSerializer, TenantContext
from data_fabric.identity import MatchCandidate
from data_fabric.orchestration.exceptions import OrchestrationValidationError
from data_fabric.orchestration.idempotency import InMemoryIdempotencyStore
from data_fabric.orchestration.interfaces import CanonicalizationPipeline, IngestionCoordinator
from data_fabric.orchestration.models import (
    BatchIngestionRequest,
    BatchIngestionResult,
    CanonicalizationContext,
    CanonicalizationResult,
    EntityWriteAction,
    EntityWritePlan,
    IdempotencyState,
    IngestionRequest,
    LineageEmissionPlan,
    ProcessingIssue,
    QualityGateDecision,
    QualityGateOutcome,
    RecordProcessingResult,
    RelationshipWritePlan,
    TransactionResult,
    TransactionStatus,
    VersionDecision,
    VersionDecisionAction,
)
from data_fabric.orchestration.policies import (
    DefaultLineageEmissionPolicy,
    DefaultQualityGatePolicy,
    DefaultVersionCreationPolicy,
)
from data_fabric.orchestration.unit_of_work import InMemoryTransactionBoundary
from data_fabric.quality import (
    QUALITY_DIMENSIONS,
    QualityAssessment,
    QualityDimensionScore,
    QualityIssue,
    QualityIssueSeverity,
    TrustScore,
)


class DefaultCanonicalizationPipeline(CanonicalizationPipeline):
    """Reference pipeline that produces plans before any write boundary."""

    STAGES: tuple[str, ...] = (
        "validate tenant context",
        "validate source record",
        "check idempotency",
        "perform semantic mapping",
        "perform identity resolution",
        "construct or update canonical entity plan",
        "evaluate data quality",
        "apply quality gate",
        "determine version creation",
        "prepare lineage/provenance emission",
        "prepare relationship writes",
        "execute within unit-of-work boundary",
        "record idempotency completion",
        "return explainable result",
    )

    def __init__(
        self,
        *,
        idempotency_store: InMemoryIdempotencyStore | None = None,
        transaction_boundary: InMemoryTransactionBoundary | None = None,
        quality_gate_policy: DefaultQualityGatePolicy | None = None,
        lineage_policy: DefaultLineageEmissionPolicy | None = None,
        version_policy: DefaultVersionCreationPolicy | None = None,
        serializer: DefaultDeterministicSerializer | None = None,
        semantic_mapper: Any | None = None,
        identity_resolver: Any | None = None,
    ) -> None:
        self.idempotency_store = idempotency_store or InMemoryIdempotencyStore()
        self.transaction_boundary = transaction_boundary or InMemoryTransactionBoundary()
        self.quality_gate_policy = quality_gate_policy or DefaultQualityGatePolicy()
        self.lineage_policy = lineage_policy or DefaultLineageEmissionPolicy()
        self.version_policy = version_policy or DefaultVersionCreationPolicy()
        self.serializer = serializer or DefaultDeterministicSerializer()
        self.semantic_mapper = semantic_mapper
        self.identity_resolver = identity_resolver
        self._subject_hashes: dict[tuple[str, str, str], str] = {}

    def process(self, request: IngestionRequest) -> CanonicalizationResult:
        context = CanonicalizationContext(
            request_id=request.request_id,
            tenant_context=request.tenant_context,
            correlation_id=request.correlation_id,
        )
        request.tenant_context.assert_matches(context.tenant_context, "canonicalization context")
        source_record = request.source_record
        payload_hash = self.serializer.content_hash(source_record.payload)
        idem_record = self.idempotency_store.begin(request.idempotency_key, payload_hash)
        if idem_record.state is IdempotencyState.COMPLETED and idem_record.result is not None:
            return replace(idem_record.result, idempotent_replay=True)

        try:
            semantic_result = self._semantic_mapping(request)
            identity_result = self._identity_resolution(request)
            entity_plan = self._entity_write_plan(request, identity_result)
            assessment = self._quality_assessment(request, entity_plan)
            quality_decision = self.quality_gate_policy.decide(assessment)
            previous_hash = self._subject_hashes.get(self._subject_key(request.tenant_context, entity_plan))
            version_decision = self.version_policy.decide(entity_plan, previous_hash=previous_hash)
            relationship_plans: tuple[RelationshipWritePlan, ...] = ()
            placeholder = CanonicalizationResult(
                request_id=request.request_id,
                tenant_context=request.tenant_context,
                source_record=source_record,
                entity_plan=entity_plan,
                relationship_plans=relationship_plans,
                quality_decision=quality_decision,
                version_decision=version_decision,
                lineage_plan=LineageEmissionPlan(False, False, False, False, False, False, False, False, False),
                transaction_result=None,
                semantic_mapping=semantic_result,
                explanation=self.STAGES,
            )
            lineage_plan = self.lineage_policy.plan(request, placeholder)
            transaction_result: TransactionResult | None = None
            issues: tuple[ProcessingIssue, ...] = ()
            if quality_decision.outcome in {QualityGateOutcome.REJECT, QualityGateOutcome.QUARANTINE}:
                issues = (
                    ProcessingIssue(
                        f"quality_gate_{quality_decision.outcome.value}",
                        "; ".join(quality_decision.explanation),
                    ),
                )
            else:
                transaction_result = self.transaction_boundary.execute(
                    tenant_context=request.tenant_context,
                    entity_plan=entity_plan,
                    relationship_plans=relationship_plans,
                    lineage_plan=lineage_plan,
                )
                if transaction_result.status is TransactionStatus.COMMITTED:
                    if version_decision.new_hash is not None:
                        self._subject_hashes[self._subject_key(request.tenant_context, entity_plan)] = version_decision.new_hash
            result = CanonicalizationResult(
                request_id=request.request_id,
                tenant_context=request.tenant_context,
                source_record=source_record,
                entity_plan=entity_plan,
                relationship_plans=relationship_plans,
                quality_decision=quality_decision,
                version_decision=version_decision,
                lineage_plan=lineage_plan,
                transaction_result=transaction_result,
                semantic_mapping=semantic_result,
                issues=issues,
                explanation=self.STAGES,
            )
            if transaction_result is not None and transaction_result.status is TransactionStatus.COMMITTED:
                self.idempotency_store.complete(request.idempotency_key, result)
            elif issues:
                self.idempotency_store.fail(request.idempotency_key, issues[0].message)
            return result
        except Exception as exc:
            self.idempotency_store.fail(request.idempotency_key, str(exc))
            raise

    def _semantic_mapping(self, request: IngestionRequest) -> Any | None:
        if self.semantic_mapper is None:
            return None
        return self.semantic_mapper.map_source_term(
            source_system=request.source_system,
            source_term=str(request.payload.get("name", request.source_identifier)),
            organization_id=request.tenant_context.organization_id,
            tenant_id=request.tenant_context.tenant_id,
            source_type=request.source_type,
            source_identifier=request.source_identifier,
            provider=request.provider,
            entity_type=str(request.payload.get("entity_type", "cloud_resource")),
            attributes=request.payload,
        )

    def _identity_resolution(self, request: IngestionRequest) -> Any | None:
        if self.identity_resolver is None:
            return None
        candidate = MatchCandidate(
            source_system=request.source_system,
            source_identifier=request.source_identifier,
            name=str(request.payload.get("name", request.source_identifier)),
            organization_id=request.tenant_context.organization_id,
            canonical_id=request.payload.get("canonical_id"),
            tenant_id=request.tenant_context.tenant_id,
            aliases=tuple(request.payload.get("aliases", ())),
            metadata=dict(request.payload.get("metadata", {})),
        )
        return self.identity_resolver.resolve(candidate)

    def _entity_write_plan(self, request: IngestionRequest, identity_result: Any | None) -> EntityWritePlan:
        payload = request.payload
        name = str(payload.get("name") or request.source_identifier)
        entity_id = str(payload.get("id") or f"{request.source_system}:{request.source_identifier}")
        canonical_id = str(payload.get("canonical_id") or entity_id)
        entity_type = str(payload.get("entity_type") or "cloud_resource")
        existing = getattr(identity_result, "matched_entity", None) if identity_result is not None else None
        action = EntityWriteAction.UPDATE if existing is not None else EntityWriteAction.CREATE
        entity = EnterpriseEntity(
            id=entity_id,
            canonical_id=canonical_id,
            entity_type=entity_type,
            name=name,
            source_system=request.source_system,
            source_identifier=request.source_identifier,
            organization_id=request.tenant_context.organization_id,
            tenant_id=request.tenant_context.tenant_id,
            confidence_score=float(payload.get("confidence_score", 1.0)),
            quality_score=float(payload.get("quality_score", 1.0)),
            tags=list(payload.get("tags", ())),
            metadata={
                "source_type": request.source_type,
                "provider": request.provider,
                "payload_hash": self.serializer.content_hash(payload),
                **dict(payload.get("metadata", {})),
            },
        )
        return EntityWritePlan(action, entity=entity, existing_entity=existing, reason="canonical entity plan prepared")

    def _quality_assessment(self, request: IngestionRequest, plan: EntityWritePlan) -> QualityAssessment:
        score = float(request.payload.get("trust_score", request.payload.get("quality_score_100", 100.0)))
        score = max(0.0, min(100.0, score))
        issues = []
        for issue in request.payload.get("quality_issues", ()):
            severity = issue.get("severity", QualityIssueSeverity.WARNING)
            issues.append(
                QualityIssue(
                    rule_id=str(issue.get("rule_id", "source_quality_issue")),
                    dimension=str(issue.get("dimension", "validity")),
                    message=str(issue.get("message", "source quality issue")),
                    severity=severity,
                    deduction=float(issue.get("deduction", 100.0 - score)),
                )
            )
        dimension_scores = {
            dimension: QualityDimensionScore(dimension, score, tuple(issues))
            for dimension in QUALITY_DIMENSIONS
        }
        trust_score = TrustScore(
            final_score=score,
            dimension_scores=dimension_scores,
            weights={dimension: round(1.0 / len(QUALITY_DIMENSIONS), 8) for dimension in QUALITY_DIMENSIONS},
            deductions={dimension: round(100.0 - score, 4) for dimension in QUALITY_DIMENSIONS},
            explanation=(f"source-provided orchestration trust score={score:.2f}",),
        )
        entity = plan.entity
        if entity is None:
            raise OrchestrationValidationError("entity write plan requires entity for quality assessment")
        return QualityAssessment(
            subject_id=entity.id,
            subject_type="entity",
            organization_id=entity.organization_id,
            tenant_id=entity.tenant_id,
            source_system=entity.source_system,
            source_identifier=entity.source_identifier,
            dimension_scores=dimension_scores,
            issues=tuple(issues),
            trust_score=trust_score,
        )

    @staticmethod
    def _subject_key(tenant_context: TenantContext, plan: EntityWritePlan) -> tuple[str, str, str]:
        if plan.entity is None:
            return (tenant_context.organization_id, tenant_context.tenant_id, "")
        return (tenant_context.organization_id, tenant_context.tenant_id, plan.entity.id)


class InMemoryIngestionCoordinator(IngestionCoordinator):
    """In-memory coordinator for single-record and batch ingestion."""

    def __init__(self, pipeline: DefaultCanonicalizationPipeline | None = None) -> None:
        self.pipeline = pipeline or DefaultCanonicalizationPipeline()

    def ingest(self, request: IngestionRequest) -> CanonicalizationResult:
        return self.pipeline.process(request)

    def ingest_batch(self, request: BatchIngestionRequest) -> BatchIngestionResult:
        records: list[RecordProcessingResult] = []
        for index, item in enumerate(request.requests):
            try:
                result = self.ingest(item)
                success = result.succeeded
                records.append(
                    RecordProcessingResult(
                        index=index,
                        request_id=item.request_id,
                        success=success,
                        result=result,
                        issues=result.issues,
                    )
                )
                if request.fail_fast and not success:
                    break
            except Exception as exc:
                issue = ProcessingIssue("record_processing_failed", str(exc))
                records.append(
                    RecordProcessingResult(
                        index=index,
                        request_id=item.request_id,
                        success=False,
                        issues=(issue,),
                    )
                )
                if request.fail_fast:
                    break
        success_count = sum(1 for record in records if record.success)
        failure_count = len(records) - success_count
        return BatchIngestionResult(
            batch_id=request.batch_id,
            tenant_context=request.tenant_context,
            records=tuple(records),
            total_records=len(request.requests),
            success_count=success_count,
            failure_count=failure_count,
            fail_fast=request.fail_fast,
        )
