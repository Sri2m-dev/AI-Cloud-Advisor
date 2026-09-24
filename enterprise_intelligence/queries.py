"""Canonical CMP-P5 query-family names."""

FINANCIAL_QUERIES = (
    "enterprise_spend_summary",
    "spend_by_domain",
    "spend_by_application",
    "spend_by_business_unit",
    "spend_by_provider",
    "spend_by_service",
    "spend_by_business_service",
    "spend_by_cost_center",
    "spend_by_owner",
    "spend_by_technology",
)
OPTIMIZATION_QUERIES = (
    "optimization_summary",
    "opportunities_for_entity",
    "savings_by_application",
    "savings_by_business_service",
    "savings_by_cost_center",
    "savings_by_owner",
    "savings_by_technology",
)
CONTEXT_QUERIES = (
    "owner_for_entity",
    "business_service_for_application",
    "cost_center_for_entity",
    "dependencies_for_entity",
    "impact_of_change",
)
TRUST_QUERIES = ("source_explanation", "source_health", "unresolved_context", "conflicted_context")
ALL_QUERY_FAMILIES = FINANCIAL_QUERIES + OPTIMIZATION_QUERIES + CONTEXT_QUERIES + TRUST_QUERIES
