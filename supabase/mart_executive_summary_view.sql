CREATE OR REPLACE VIEW public.mart_executive_summary AS
WITH cloud_spend AS (
    SELECT
        ROUND(SUM(cost)::numeric, 2) AS total_spend
    FROM public.unified_cloud_costs
),
anomalies AS (
    SELECT
        COUNT(*) AS anomaly_count
    FROM public.mart_cost_anomalies
    WHERE anomaly_status IN ('Critical', 'Anomaly')
),
optimization AS (
    SELECT
        ROUND(SUM(total_cost)::numeric, 2) AS optimization_savings
    FROM public.mart_optimization_opportunities
    WHERE savings_potential IN ('Critical', 'High')
),
governance AS (
    SELECT
        CASE
            WHEN (
                SELECT COUNT(*)
                FROM public.mart_cost_anomalies
                WHERE anomaly_status = 'Critical'
            ) >= 5 THEN 68
            WHEN (
                SELECT COUNT(*)
                FROM public.mart_cost_anomalies
                WHERE anomaly_status = 'Critical'
            ) >= 1 THEN 79
            ELSE 91
        END AS governance_score
)
SELECT
    cs.total_spend,
    a.anomaly_count,
    o.optimization_savings,
    g.governance_score,
    NOW() AS generated_at
FROM cloud_spend cs
CROSS JOIN anomalies a
CROSS JOIN optimization o
CROSS JOIN governance g;
