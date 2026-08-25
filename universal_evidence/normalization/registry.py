"""Concept-aware registry that selects representation, never semantics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from universal_evidence.normalization.normalizers import (
    NormalizedResult,
    normalize_boolean,
    normalize_currency,
    normalize_date,
    normalize_datetime,
    normalize_decimal,
    normalize_integer,
    normalize_string,
)
from universal_evidence.normalization.policy import NormalizationPolicy
from universal_evidence.semantic.models import ConceptDefinition
from universal_evidence.semantic.registry import ConceptRegistry

Normalizer = Callable[[object, NormalizationPolicy], NormalizedResult]


@dataclass(frozen=True, slots=True)
class NormalizerRegistry:
    ontology: ConceptRegistry

    def concept(self, concept_id: str) -> ConceptDefinition | None:
        return next(
            (item for item in self.ontology.concepts if item.concept.concept_id == concept_id),
            None,
        )

    def normalizer(self, concept_id: str) -> Normalizer | None:
        definition = self.concept(concept_id)
        if definition is None:
            return None
        if concept_id == "financial.currency":
            return normalize_currency
        primitive_types = set(definition.concept.expected_primitive_types)
        if primitive_types == {"BOOLEAN"}:
            return normalize_boolean
        if primitive_types <= {"DATE"}:
            return normalize_date
        if primitive_types <= {"DATETIME"}:
            return normalize_datetime
        if primitive_types == {"INTEGER"}:
            return normalize_integer
        if primitive_types and primitive_types <= {"INTEGER", "DECIMAL"}:
            return normalize_decimal
        if "STRING" in primitive_types:
            return normalize_string
        return None
