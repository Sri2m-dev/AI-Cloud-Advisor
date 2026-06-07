# Data Lineage Registry: Total Cloud Spend KPI

This document traces the full lineage for the "Total Cloud Spend" KPI, ensuring enterprise data governance and auditability.

---

## KPI: Total Cloud Spend

| Layer             | Source/Component                        | File(s) / Table(s)                        | Notes                                      |
|-------------------|-----------------------------------------|--------------------------------------------|--------------------------------------------|
| Dashboard         | Executive Dashboard                     | pages/executive_dashboard.py             | Displays Total Cloud Spend KPI             |
| Mart/View         | kpi_total_cloud_spend                   | mart_kpi_table_schemas.md                  | Aggregated spend, daily/monthly granularity|
| Warehouse Table   | unified_cloud_costs                     | unified_cloud_costs (Supabase/Postgres)    | Source of truth for all spend marts/KPIs   |
| Ingestion Script  | AWS/Azure/GCP cost sync/ingest scripts  | aws_athena_ingest.py, azure_cost_sync.py, gcp_cost_sync.py | ETL from each cloud                        |
| Cloud Source      | Cloud Billing APIs/Exports               | AWS CUR, Azure Cost Management, GCP Billing Export | Raw billing data from each provider        |

---

> Update this registry for every critical KPI to maintain full data lineage and compliance.
