"""
mock_data/optimization_mock.py

Stub data for views/optimization_insights.py sections that are not yet
wired to live cloud telemetry. Each block documents the production
replacement source.

Replace / remove each block once the corresponding API / Supabase table
is available.
"""

# ---------------------------------------------------------------------------
# Commitment Utilization
# Production replacement: AWS Cost Explorer DescribeSavingsPlansCoverage /
#   DescribeReservationCoverage — store in Supabase table
#   `commitment_utilization` (columns: month, ri_cost, on_demand_equivalent).
# ---------------------------------------------------------------------------
COMMITMENT_MOCK = {
    "monthly_commitment": 8_500,       # RI / Savings Plans monthly cost ($)
    "on_demand_equivalent": 5_950,     # Current usage in on-demand terms ($)
}

# ---------------------------------------------------------------------------
# Reserved Instance Purchase Timing
# Production replacement: AWS Cost Explorer GetCostAndUsage (MONTHLY granularity,
#   last 12 months) — pipe into `services/optimization_engine.py`.
# ---------------------------------------------------------------------------
RI_TIMING_MOCK = {
    "monthly_cost_history": [
        48_200, 49_100, 50_300, 51_000, 50_800, 52_100,
        51_900, 53_200, 52_800, 54_100, 53_600, 53_661,
    ],
    "on_demand_monthly": 53_661.0,
    "existing_ri_coverage": 0.45,   # fraction (0–1)
}

# ---------------------------------------------------------------------------
# Network / Data Transfer
# Production replacement: AWS Cost Explorer GetCostAndUsage filtered by
#   UsageType containing "DataTransfer" — store in Supabase `network_costs`.
# ---------------------------------------------------------------------------
NETWORK_MOCK = {
    "total_data_transfer_cost": 1_730.46,
    "nat_gateway_cost": 680.00,
    "cross_region_cost": 540.00,
    "internet_egress_cost": 510.46,
}

# ---------------------------------------------------------------------------
# Tagging / Attribution
# Production replacement: AWS Resource Groups Tagging API
#   GetResources — store compliance data in Supabase `resource_tagging`.
# ---------------------------------------------------------------------------
TAGGING_MOCK = {
    "total_monthly_spend": 53_660.90,
    "untagged_fraction": 0.28,       # 28 % untagged
    "partial_fraction": 0.22,        # 22 % partially tagged
}

# ---------------------------------------------------------------------------
# Cost Anomaly Detection (baseline comparison)
# Production replacement: AWS Cost Anomaly Detection GetAnomalies /
#   live data from Supabase `unified_cloud_costs` (7-day rolling avg).
# ---------------------------------------------------------------------------
ANOMALY_BASELINE_MOCK = {
    "baseline_daily": 215.50,
    "recent_daily": 258.75,
}

# ---------------------------------------------------------------------------
# Budget Thresholds
# Production replacement: AWS Budgets API / user-configured budgets stored
#   in Supabase `budgets` table.
# ---------------------------------------------------------------------------
BUDGET_MOCK = {
    "monthly_budget": 12_000,
    "current_spend": 8_950,
}

