"""Transparent score composition for PUE-002 column candidates."""

from __future__ import annotations

from universal_evidence.contracts import (
    ConfidenceBand,
    ConfirmationState,
    MappingConfidence,
)
from universal_evidence.profiling import ColumnProfile, SheetProfile
from universal_evidence.semantic.models import (
    ConceptDefinition,
    DiscoveryCandidate,
    DiscoveryConfig,
    SemanticSignal,
)
from universal_evidence.semantic.signals import (
    alias_strength,
    normalize_text,
    primitive_compatibility,
    sample_shape_support,
    tokens,
)


def confidence_band(score: float, config: DiscoveryConfig) -> ConfidenceBand:
    if score >= config.high_band_threshold:
        return ConfidenceBand.HIGH
    if score >= config.medium_band_threshold:
        return ConfidenceBand.MEDIUM
    if score >= config.low_band_threshold:
        return ConfidenceBand.LOW
    return ConfidenceBand.INSUFFICIENT


def _context_strength(
    definition: ConceptDefinition, column: ColumnProfile, sheet: SheetProfile
) -> bool:
    neighbor_tokens: set[str] = set(tokens(sheet.sheet.original_name))
    for neighbor in sheet.columns:
        if neighbor.column.column_id != column.column.column_id:
            neighbor_tokens.update(tokens(neighbor.column.original_header))
    expected = {normalize_text(item) for item in definition.context_tokens}
    return bool(neighbor_tokens.intersection(expected))


def score_candidate(
    definition: ConceptDefinition,
    column: ColumnProfile,
    sheet: SheetProfile,
    config: DiscoveryConfig,
    *,
    decided_at,
) -> DiscoveryCandidate | None:
    support: list[SemanticSignal] = []
    contradict: list[SemanticSignal] = []
    header_strength, alias = alias_strength(
        column.column.original_header, definition.concept.aliases
    )
    if header_strength <= 0:
        return None
    header_contribution = header_strength * config.header_weight
    support.append(
        SemanticSignal(
            "HEADER_ALIAS",
            f"header structurally matches registered alias '{alias}'",
            round(header_contribution, 6),
        )
    )
    score = header_contribution
    compatible, incompatible = primitive_compatibility(
        column, definition.concept.expected_primitive_types
    )
    if compatible:
        score += config.primitive_weight
        support.append(
            SemanticSignal(
                "PRIMITIVE_COMPATIBLE",
                f"dominant primitive {column.dominant_primitive_type.value} is compatible",
                config.primitive_weight,
            )
        )
    elif incompatible:
        score -= config.contradiction_penalty
        contradict.append(
            SemanticSignal(
                "PRIMITIVE_CONTRADICTION",
                f"dominant primitive {column.dominant_primitive_type.value} conflicts with concept",
                -config.contradiction_penalty,
            )
        )
    if set(column.structural_roles).intersection(definition.expected_roles):
        score += config.role_weight
        support.append(
            SemanticSignal(
                "STRUCTURAL_ROLE_COMPATIBLE",
                "one or more PUE-001 structural roles are compatible",
                config.role_weight,
            )
        )
    if sample_shape_support(column, definition.sample_shape):
        score += config.sample_weight
        support.append(
            SemanticSignal(
                "SAFE_SAMPLE_SHAPE",
                "bounded safe sample shape supports the candidate",
                config.sample_weight,
            )
        )
    if _context_strength(definition, column, sheet):
        score += config.context_weight
        support.append(
            SemanticSignal(
                "SHEET_LOCAL_CONTEXT",
                "neighboring structural headers weakly support the candidate",
                config.context_weight,
            )
        )
    score = round(min(max(score, 0.0), 1.0), 6)
    if score < config.minimum_candidate_score:
        return None
    confirmation = (
        ConfirmationState.REQUIRED
        if definition.risk in config.confirm_risks
        else ConfirmationState.NOT_REQUIRED
    )
    confidence = MappingConfidence(
        score,
        confidence_band(score, config),
        "transparent_weighted_signals",
        tuple(signal.signal_type for signal in (*support, *contradict)),
        config.classifier_version,
        config.policy_version,
        decided_at,
    )
    support_text = "; ".join(signal.detail for signal in support)
    contradiction_text = "; ".join(signal.detail for signal in contradict)
    explanation = (
        f"Supporting: {support_text or 'none'}. "
        f"Contradicting: {contradiction_text or 'none'}."
    )
    return DiscoveryCandidate(
        definition.concept.concept_id,
        definition.concept.version,
        definition.concept.dimension.value,
        confidence,
        definition.risk,
        tuple(support),
        tuple(contradict),
        explanation,
        confirmation,
    )
