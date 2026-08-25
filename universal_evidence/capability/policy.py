"""Versioned PUE-005 sufficiency and capability policies."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CoveragePolicy:
    version: str = "pue-coverage-policy-1"
    minimum_coverage_ratio: float = 0.80
    minimum_validity_ratio: float = 0.90
    maximum_invalid_ratio: float = 0.10
    minimum_dimension_validity_ratio: float = 0.80
    minimum_measure_validity_ratio: float = 0.90
    minimum_row_binding_ratio: float = 1.0

    def __post_init__(self) -> None:
        values = (
            self.minimum_coverage_ratio,
            self.minimum_validity_ratio,
            self.maximum_invalid_ratio,
            self.minimum_dimension_validity_ratio,
            self.minimum_measure_validity_ratio,
            self.minimum_row_binding_ratio,
        )
        if any(not 0 <= value <= 1 for value in values):
            raise ValueError("coverage policy ratios must be between zero and one")


@dataclass(frozen=True, slots=True)
class CapabilityPolicy:
    version: str = "pue-capability-policy-1"
    monetary_measure_concepts: frozenset[str] = frozenset(
        {
            "financial.cost.total",
            "financial.cost.monthly",
            "financial.cost.unit",
            "financial.price",
            "financial.savings",
            "financial.budget",
        }
    )
    non_dimension_concepts: frozenset[str] = frozenset(
        {
            "financial.currency",
            "saas.license_count",
            "saas.utilization",
            "operational.cpu",
            "operational.memory",
            "operational.utilization",
            "operational.incident_count",
        }
    )
    time_concept_fragments: tuple[str, ...] = ("date", "time", "period")
