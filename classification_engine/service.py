"""Deterministic field-level enterprise classification orchestration."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4

from classification_engine.confidence import (
    ENGINE_VERSION,
    ConfidenceDimensions,
    calculate_confidence,
)
from classification_engine.models import (
    ApprovalStatus,
    ClassificationEvidence,
    ClassificationPolicy,
    ClassificationResult,
    InferenceStatus,
)
from classification_engine.policy import inference_outcome
from classification_engine.repository import InMemoryClassificationRepository
from data_fabric.foundation import TenantContext

SUPPORTED_FIELDS = (
    "account_name",
    "business_unit",
    "department",
    "cost_center",
    "environment",
    "application",
    "business_service",
    "owner",
    "technical_owner",
    "finance_owner",
    "criticality",
)


class ClassificationService:
    def __init__(self, repository=None) -> None:
        self.repository = repository or InMemoryClassificationRepository()

    def classify_account(
        self,
        context: TenantContext,
        *,
        account_id: str,
        evidence: tuple[ClassificationEvidence, ...],
        policy: ClassificationPolicy,
        now: datetime | None = None,
    ) -> tuple[ClassificationResult, ...]:
        if (policy.organization_id, policy.tenant_id) != (
            context.organization_id,
            context.tenant_id,
        ):
            raise PermissionError("cross-tenant classification policy rejected")
        for item in evidence:
            if (item.organization_id, item.tenant_id) != (
                context.organization_id,
                context.tenant_id,
            ):
                raise PermissionError("classification evidence crosses tenant boundary")
        timestamp = now or datetime.now(timezone.utc)
        by_field: dict[str, list[ClassificationEvidence]] = defaultdict(list)
        for item in evidence:
            if item.observed_field in SUPPORTED_FIELDS and item.observed_value.strip():
                by_field[item.observed_field].append(item)
        return tuple(
            self.repository.save(
                context,
                self._classify_field(
                    context, account_id, field_name, by_field[field_name], policy, timestamp
                ),
            )
            for field_name in SUPPORTED_FIELDS
        )

    def _classify_field(self, context, account_id, field_name, evidence, policy, timestamp):
        evidence = sorted(
            evidence, key=lambda item: (item.observed_value.casefold(), item.evidence_id)
        )
        evidence_hash = hashlib.sha256(
            json.dumps(
                [(e.evidence_id, e.evidence_hash) for e in evidence], separators=(",", ":")
            ).encode()
        ).hexdigest()
        if not evidence:
            return ClassificationResult(
                id=str(uuid4()),
                organization_id=context.organization_id,
                tenant_id=context.tenant_id,
                entity_type="cloud_account",
                entity_id=account_id,
                field_name=field_name,
                inferred_value=None,
                confidence_score=0,
                inference_method="NO_EVIDENCE",
                inference_status=InferenceStatus.NEEDS_REVIEW,
                policy_version=policy.policy_version,
                engine_version=ENGINE_VERSION,
                evidence_set_hash=evidence_hash,
                source_timestamp=timestamp,
                created_at=timestamp,
                valid_from=timestamp,
                valid_to=None,
                approval_status=ApprovalStatus.NEEDS_APPROVAL,
                evidence_ids=(),
                review_reason="no supporting evidence",
            )
        grouped: dict[str, list[ClassificationEvidence]] = defaultdict(list)
        for item in evidence:
            grouped[item.observed_value.strip()].append(item)
        total = len(evidence)
        candidate_scores = {}
        for value, items in sorted(grouped.items()):
            reliability = sum(item.source_reliability for item in items) / len(items)
            freshness = sum(
                max(0, 1 - (timestamp - item.observed_at).days / max(1, policy.freshness_days))
                for item in items
            ) / len(items)
            stated_coverage = [
                float(item.metadata["coverage"]) for item in items if "coverage" in item.metadata
            ]
            dimensions = ConfidenceDimensions(
                source_reliability=reliability,
                consistency=len(items) / total,
                freshness=freshness,
                coverage=(
                    sum(stated_coverage) / len(stated_coverage)
                    if stated_coverage
                    else min(1, len(items) / 2)
                ),
                corroboration=min(1, len({item.source_type for item in items}) / 2),
                contradiction_penalty=(total - len(items)) / total,
            )
            candidate_scores[value] = calculate_confidence(dimensions).score
        ordered = sorted(candidate_scores.items(), key=lambda item: (-item[1], item[0].casefold()))
        value, confidence = ordered[0]
        conflict = len(grouped) > 1
        status, approval = inference_outcome(
            confidence=confidence, conflict=conflict, policy=policy
        )
        approved_by = policy.approved_by if approval is ApprovalStatus.AUTO_APPROVED else None
        approved_at = timestamp if approval is ApprovalStatus.AUTO_APPROVED else None
        return ClassificationResult(
            id=str(uuid4()),
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            entity_type="cloud_account",
            entity_id=account_id,
            field_name=field_name,
            inferred_value=value,
            confidence_score=confidence,
            inference_method="DETERMINISTIC_MULTI_SOURCE",
            inference_status=status,
            policy_version=policy.policy_version,
            engine_version=ENGINE_VERSION,
            evidence_set_hash=evidence_hash,
            source_timestamp=max(item.observed_at for item in evidence),
            created_at=timestamp,
            valid_from=timestamp,
            valid_to=None,
            approval_status=approval,
            approved_by=approved_by,
            approved_at=approved_at,
            evidence_ids=tuple(item.evidence_id for item in evidence),
            candidate_values=candidate_scores,
            conflict=conflict,
            review_reason="conflicting evidence requires review" if conflict else None,
        )
