"""Two-pass, profile-only PUE-002 semantic discovery orchestration."""

from __future__ import annotations

import hashlib
from collections import Counter

from universal_evidence.profiling import FileProfile
from universal_evidence.semantic.concepts import DEFAULT_CONCEPT_REGISTRY
from universal_evidence.semantic.models import (
    ColumnDiscoveryResult,
    DiscoveryConfig,
    FileDiscoveryResult,
    SemanticDiscoveryProvenance,
)
from universal_evidence.semantic.policy import evaluate_discovery_state
from universal_evidence.semantic.registry import ConceptRegistry
from universal_evidence.semantic.scoring import score_candidate


def _fingerprint(value: object) -> str:
    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()


def discover_semantics(
    profile: FileProfile,
    *,
    registry: ConceptRegistry = DEFAULT_CONCEPT_REGISTRY,
    config: DiscoveryConfig | None = None,
) -> FileDiscoveryResult:
    """Generate column-meaning hypotheses without reparsing or normalization."""
    policy = config or DiscoveryConfig()
    structural_fingerprint = _fingerprint(profile.structural_fingerprint)
    results: list[ColumnDiscoveryResult] = []
    for sheet in profile.sheets:
        for column in sheet.columns:
            candidates = tuple(
                sorted(
                    (
                        candidate
                        for definition in registry.concepts
                        if (
                            candidate := score_candidate(
                                definition,
                                column,
                                sheet,
                                policy,
                                decided_at=profile.profiled_at,
                            )
                        )
                        is not None
                    ),
                    key=lambda item: (-item.confidence.score, item.semantic_concept_id),
                )
            )
            state, confirmation, reasons = evaluate_discovery_state(
                candidates, column, policy
            )
            provenance = SemanticDiscoveryProvenance(
                column.column.context.analysis_id,
                column.column.context.prospect_id,
                column.column.context.organization_id,
                column.column.context.tenant_id,
                column.column.context.source_id,
                column.column.file_id,
                column.column.sheet_id,
                column.column.column_id,
                structural_fingerprint,
                tuple(sample.row_reference for sample in column.samples),
                profile.profiler_version,
                policy.classifier_version,
                registry.ontology_version,
                policy.policy_version,
            )
            discovery_id = (
                "discovery-"
                + _fingerprint(
                    (
                        provenance,
                        column.column.original_header,
                        candidates,
                        state,
                        confirmation,
                    )
                )[:24]
            )
            results.append(
                ColumnDiscoveryResult(
                    discovery_id,
                    column.column.column_id,
                    column.column.original_header,
                    candidates,
                    state,
                    confirmation,
                    reasons,
                    policy.classifier_name,
                    policy.classifier_version,
                    registry.ontology_version,
                    policy.policy_version,
                    profile.profiled_at,
                    provenance,
                )
            )
    counts = Counter(
        candidate.dimension for result in results for candidate in result.candidates
    )
    semantic_fingerprint = _fingerprint(
        (
            structural_fingerprint,
            policy,
            registry.ontology_version,
            tuple(results),
        )
    )
    return FileDiscoveryResult(
        profile.evidence_file.file_id,
        structural_fingerprint,
        semantic_fingerprint,
        policy.classifier_version,
        registry.ontology_version,
        policy.policy_version,
        tuple(results),
        tuple(sorted(counts.items())),
        sum(not result.candidates for result in results),
    )
