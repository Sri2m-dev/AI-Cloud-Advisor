"""Thin adapters over the existing evidence registry contract."""

from __future__ import annotations

from classification_engine.models import ClassificationEvidence
from evidence_registry.models import EvidenceItem


def from_registry_evidence(item: EvidenceItem) -> ClassificationEvidence:
    metadata = dict(item.metadata)
    return ClassificationEvidence(
        evidence_id=item.evidence_id,
        organization_id=item.organization_id,
        tenant_id=item.tenant_id,
        source_type=str(metadata.get("source_type") or item.source_system),
        source_name=item.source_system,
        source_reference=item.source_identifier,
        observed_field=str(metadata.get("observed_field") or "unknown"),
        observed_value=str(metadata.get("observed_value") or ""),
        observed_at=item.observed_at,
        source_reliability=float(item.quality_score if item.quality_score is not None else 0.5),
        evidence_hash=item.evidence_hash,
        lineage_reference=item.lineage_ref,
        provenance_reference=item.provenance_ref,
        metadata=metadata,
    )
