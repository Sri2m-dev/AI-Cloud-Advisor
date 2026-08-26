"""Versioned PUE-007 planning policy."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnalyticalPlanningPolicy:
    version: str = "pue-analytical-planning-policy-1"
    intent_version: str = "pue-analytical-intent-1"
    execution_policy_version: str = "pue-aggregation-execution-policy-1"
    canonical_concept_separator: str = "."
