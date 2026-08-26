"""Versioned PUE-006 precision and execution policy."""

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN


@dataclass(frozen=True, slots=True)
class AggregationExecutionPolicy:
    version: str = "pue-aggregation-execution-policy-1"
    decimal_precision: int = 38
    rounding_mode: str = ROUND_HALF_EVEN
    output_scale: int | None = None
    max_materialized_provenance_references: int = 1000

    def __post_init__(self) -> None:
        if self.decimal_precision <= 0:
            raise ValueError("decimal precision must be positive")
        if self.output_scale is not None and self.output_scale < 0:
            raise ValueError("output scale cannot be negative")
        if self.max_materialized_provenance_references <= 0:
            raise ValueError("provenance-reference limit must be positive")
