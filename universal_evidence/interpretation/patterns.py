"""Bounded PUE-008 phrase-pattern vocabulary."""

UNSUPPORTED_OPERATION_TERMS = {
    "average": "AVERAGE",
    "minimum": "MINIMUM",
    "maximum": "MAXIMUM",
    "top ": "RANKING",
    "most expensive": "RANKING",
    "the most": "RANKING",
    "highest": "RANKING",
    "lowest": "RANKING",
    "save": "RECOMMENDATION",
    "savings": "RECOMMENDATION",
    "optimize": "RECOMMENDATION",
    "wasteful": "RECOMMENDATION",
    "risk": "RISK",
    "depend on": "RELATIONSHIP",
    "depends on": "RELATIONSHIP",
}

COUNT_RECORD_PATTERNS = ("how many records", "record count", "count records")
DISTINCT_COUNT_TERMS = ("how many services", "how many providers", "how many regions")
TIME_PATTERNS = {
    "trend": "MONTH",
    "over time": "MONTH",
    "by month": "MONTH",
    "monthly trend": "MONTH",
    "daily trend": "DAY",
    "quarterly trend": "QUARTER",
    "yearly trend": "YEAR",
}
