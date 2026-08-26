"""Bounded mapping from certified capability to executable operation."""

from universal_evidence.capability import AuthorizedOperation

EXECUTION_REGISTRY_VERSION = "pue-aggregation-registry-1"

CAPABILITY_OPERATIONS = {
    "COUNT_EVIDENCE_RECORDS": frozenset({AuthorizedOperation.COUNT}),
    "MONETARY_TOTAL": frozenset({AuthorizedOperation.SUM}),
    "MONETARY_TOTAL_BY_DIMENSION": frozenset({AuthorizedOperation.GROUPED_SUM}),
    "MONETARY_TREND": frozenset({AuthorizedOperation.TIME_BUCKETED_SUM}),
    "CURRENCY_GROUPED_TOTAL": frozenset({AuthorizedOperation.GROUPED_SUM}),
}
