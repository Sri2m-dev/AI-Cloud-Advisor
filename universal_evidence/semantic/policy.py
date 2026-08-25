"""Classification-state policy kept separate from confidence scoring."""

from universal_evidence.contracts import ClassificationState, ConfirmationState
from universal_evidence.profiling import ColumnProfile
from universal_evidence.semantic.models import DiscoveryCandidate, DiscoveryConfig


def evaluate_discovery_state(
    candidates: tuple[DiscoveryCandidate, ...],
    column: ColumnProfile,
    config: DiscoveryConfig,
) -> tuple[ClassificationState, ConfirmationState, tuple[str, ...]]:
    if not candidates:
        return (
            ClassificationState.UNCLASSIFIED,
            ConfirmationState.NOT_REQUIRED,
            ("no candidate met the minimum evidence threshold",),
        )
    top = candidates[0]
    reasons: list[str] = []
    if top.confirmation_requirement is ConfirmationState.REQUIRED:
        reasons.append(
            f"semantic risk policy requires confirmation for {top.risk.value}"
        )
    if len(candidates) > 1:
        gap = top.confidence.score - candidates[1].confidence.score
        if gap < config.ambiguity_gap_threshold:
            reasons.append("top semantic candidates are within the ambiguity gap")
    if top.contradicting_signals:
        reasons.append("structural evidence contradicts part of the interpretation")
    if column.primitive_profile.coverage < config.low_coverage_threshold:
        reasons.append("column coverage is below semantic policy threshold")
    if top.confidence.score < config.auto_classification_threshold:
        reasons.append("top confidence is below automatic proposal threshold")
    if reasons:
        state = (
            ClassificationState.CANDIDATE
            if top.confidence.score < config.medium_band_threshold
            and len(candidates) == 1
            else ClassificationState.CONFIRMATION_REQUIRED
        )
        return state, ConfirmationState.REQUIRED, tuple(reasons)
    return ClassificationState.AUTO_CLASSIFIED, ConfirmationState.NOT_REQUIRED, ()
