"""Build a bounded PUE-008 catalog from current governed metadata only."""

from universal_evidence.capability import (
    CapabilityScope,
    CapabilityState,
    DimensionValueType,
    InMemoryCapabilityRepository,
)
from universal_evidence.interpretation.fingerprint import fingerprint
from universal_evidence.interpretation.models import (
    AnalyticalConceptCatalog,
    CatalogDimension,
    CatalogMeasure,
)
from universal_evidence.interpretation.policy import InterpretationPolicy


def build_concept_catalog(
    capability_repository: InMemoryCapabilityRepository,
    scope: CapabilityScope,
    policy: InterpretationPolicy | None = None,
) -> AnalyticalConceptCatalog | None:
    policy = policy or InterpretationPolicy()
    assessment = capability_repository.get_current_assessment(scope.key)
    if assessment is None or assessment.scope != scope:
        return None
    measures = tuple(
        sorted(
            (
                CatalogMeasure(item.measure_id, item.semantic_concept_id)
                for item in assessment.measures
                if item.state is CapabilityState.SUPPORTED
            ),
            key=lambda item: (item.semantic_concept_id, item.measure_id),
        )
    )
    dimensions = tuple(
        sorted(
            (
                CatalogDimension(
                    item.dimension_id,
                    item.semantic_concept_id,
                    item.normalized_value_type,
                    item.allowed_filter_operators,
                    item.filterable,
                    item.normalized_value_type
                    in {DimensionValueType.DATE, DimensionValueType.DATETIME},
                )
                for item in assessment.dimensions
                if item.state is CapabilityState.SUPPORTED
                and item.normalized_value_type is not None
            ),
            key=lambda item: (item.semantic_concept_id, item.dimension_id),
        )
    )
    identity = fingerprint(
        scope,
        assessment.assessment_id,
        assessment.fingerprint,
        measures,
        dimensions,
        policy.catalog_version,
    )
    return AnalyticalConceptCatalog(
        scope,
        assessment.assessment_id,
        measures,
        dimensions,
        policy.catalog_version,
        assessment.fingerprint,
        identity,
    )
