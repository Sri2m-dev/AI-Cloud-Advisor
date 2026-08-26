"""Bounded mappings from PUE-007 intent to certified capability."""

from universal_evidence.capability import AuthorizedOperation
from universal_evidence.planning.models import AnalyticalIntentType

PLANNING_REGISTRY_VERSION = "pue-analytical-planning-registry-1"

INTENT_REGISTRY = {
    AnalyticalIntentType.COUNT_RECORDS: (
        "COUNT_EVIDENCE_RECORDS",
        AuthorizedOperation.COUNT,
    ),
    AnalyticalIntentType.TOTAL_MEASURE: (
        "MONETARY_TOTAL",
        AuthorizedOperation.SUM,
    ),
    AnalyticalIntentType.GROUP_MEASURE_BY_DIMENSION: (
        "MONETARY_TOTAL_BY_DIMENSION",
        AuthorizedOperation.GROUPED_SUM,
    ),
    AnalyticalIntentType.TIME_SERIES_MEASURE: (
        "MONETARY_TREND",
        AuthorizedOperation.TIME_BUCKETED_SUM,
    ),
}
