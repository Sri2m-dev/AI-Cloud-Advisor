"""Measure, dimension, aggregation, query, and future fusion contracts."""

from dataclasses import dataclass

from universal_evidence.contracts.enums import (
    AggregationCapabilityState,
    ConfirmationState,
    FusionMatchState,
    QueryCapabilityState,
)
from universal_evidence.contracts.provenance import EvidenceProvenance
from universal_evidence.contracts.scope import EvidenceAnalysisContext


@dataclass(frozen=True, slots=True)
class GovernedDimension:
    semantic_concept_id: str
    mapping_ids: tuple[str, ...]
    record_coverage: float
    confirmation_state: ConfirmationState
    structurally_usable: bool


@dataclass(frozen=True, slots=True)
class GovernedMeasure:
    semantic_concept_id: str
    mapping_ids: tuple[str, ...]
    record_coverage: float
    confirmation_state: ConfirmationState
    unit: str | None
    currency: str | None
    currency_resolved: bool
    mixed_currency: bool = False


@dataclass(frozen=True, slots=True)
class AggregationCapability:
    context: EvidenceAnalysisContext
    state: AggregationCapabilityState
    measure: GovernedMeasure | None
    dimensions: tuple[GovernedDimension, ...]
    filters: tuple[str, ...]
    row_scope: str | None
    aggregation_rule: str | None
    limitations: tuple[str, ...]
    provenance: EvidenceProvenance | None = None

    def __post_init__(self) -> None:
        if self.state is AggregationCapabilityState.SUPPORTED:
            if self.measure is None or not self.row_scope or not self.aggregation_rule:
                raise ValueError("supported aggregation requires measure, row scope, and rule")
            if not self.measure.currency_resolved or self.measure.mixed_currency:
                raise ValueError("unresolved or mixed currency cannot support aggregation")
            if self.measure.confirmation_state in {
                ConfirmationState.REQUIRED,
                ConfirmationState.PENDING,
            }:
                raise ValueError("unresolved measure confirmation cannot support aggregation")


@dataclass(frozen=True, slots=True)
class QueryCapability:
    context: EvidenceAnalysisContext
    state: QueryCapabilityState
    question_intent: str
    required_measure_concepts: tuple[str, ...]
    required_dimension_concepts: tuple[str, ...]
    evidenced_measure_concepts: tuple[str, ...]
    evidenced_dimension_concepts: tuple[str, ...]
    missing_requirements: tuple[str, ...]
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.state is QueryCapabilityState.SUPPORTED:
            required = set(self.required_measure_concepts + self.required_dimension_concepts)
            evidenced = set(self.evidenced_measure_concepts + self.evidenced_dimension_concepts)
            if not required.issubset(evidenced) or self.missing_requirements:
                raise ValueError("supported query requires every governed input")


@dataclass(frozen=True, slots=True)
class EvidenceFusionReference:
    context: EvidenceAnalysisContext
    source_ids: tuple[str, ...]
    match_state: FusionMatchState
    identity_rule_reference: str | None
    linked_normalized_record_ids: tuple[str, ...]
    confirmation_state: ConfirmationState

    def __post_init__(self) -> None:
        if len(set(self.source_ids)) < 2:
            raise ValueError("fusion requires at least two distinct sources")
        if self.match_state is FusionMatchState.MATCHED and not self.identity_rule_reference:
            raise ValueError("matched fusion requires an identity governance rule")
