"""Cross-container semantic region candidate classification."""

from universal_evidence.semantics.region_classifier import (
    SEMANTIC_CLASSIFIER_VERSION,
    EvidenceSetCandidate,
    NormalizedRegionFeatures,
    RegionSemanticCandidate,
    RegionSemanticClassification,
    SemanticRegionType,
    classify_decomposition,
    classify_region,
    group_evidence_sets,
    normalize_region_features,
)

__all__ = [
    "SEMANTIC_CLASSIFIER_VERSION",
    "EvidenceSetCandidate",
    "NormalizedRegionFeatures",
    "RegionSemanticCandidate",
    "RegionSemanticClassification",
    "SemanticRegionType",
    "classify_decomposition",
    "classify_region",
    "group_evidence_sets",
    "normalize_region_features",
]
