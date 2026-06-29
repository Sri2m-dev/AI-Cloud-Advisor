# Data Lineage Registry: KPI Lineage

This document traces the full lineage for key KPIs, supporting enterprise governance and auditability.

---

## KPI: Anomalies
| Layer             | Source/Component                        | File(s) / Table(s)                        | Notes                                      |
|-------------------|-----------------------------------------|--------------------------------------------|--------------------------------------------|
| Dashboard         | Nexora Executive Command Center, Technical Analytics| pages/executive_dashboard.py, pages/technical_analytics.py | Shows active anomalies, trends             |
| Mart/View         | mart_cost_anomalies                     | mart_kpi_table_schemas.md                  | Aggregated anomaly data                    |
| Warehouse Table   | cost_anomaly_events                     | cost_anomaly_events (Supabase/Postgres)    | Source of truth for anomaly detection      |
| Ingestion Script  | anomaly_detection_engine.py             | anomaly_detection_engine.py                | ETL/ML for anomaly detection               |
| Cloud Source      | Cloud Billing APIs/Exports               | AWS CUR, Azure, GCP Billing Export         | Raw billing data                          |

---

## KPI: Recommendations
| Layer             | Source/Component                        | File(s) / Table(s)                        | Notes                                      |
|-------------------|-----------------------------------------|--------------------------------------------|--------------------------------------------|
| Dashboard         | Nexora Executive Command Center, Approval Center    | pages/executive_dashboard.py, pages/approval_center.py | Shows open recommendations, approval queue |
| Mart/View         | mart_recommendations                    | mart_kpi_table_schemas.md                  | Aggregated recommendations                 |
| Warehouse Table   | recommendations                         | recommendations (Supabase/Postgres)        | Source of truth for recommendations        |
| Ingestion Script  | ai_recommendation_engine.py, real_recommendation_engine.py | ai_recommendation_engine.py, real_recommendation_engine.py | ETL/ML for recommendations                |
| Cloud Source      | Cloud Billing APIs/Exports, Usage APIs  | AWS, Azure, GCP                            | Raw usage and billing data                |

---

## KPI: Governance Score
| Layer             | Source/Component                        | File(s) / Table(s)                        | Notes                                      |
|-------------------|-----------------------------------------|--------------------------------------------|--------------------------------------------|
| Dashboard         | SaaS Governance, Nexora Executive Command Center    | pages/saas_governance.py, pages/executive_dashboard.py | Shows governance score, trends             |
| Mart/View         | mart_governance_score                   | mart_kpi_table_schemas.md                  | Aggregated governance metrics              |
| Warehouse Table   | governance_events, compliance_checks    | governance_events, compliance_checks (Supabase/Postgres) | Source of truth for governance             |
| Ingestion Script  | governance_engine.py                    | governance_engine.py                       | ETL/ML for governance scoring              |
| Cloud Source      | Cloud Config, Security APIs             | AWS Config, Azure Policy, GCP Security     | Raw compliance and config data            |

---

## KPI: SaaS Optimization
| Layer             | Source/Component                        | File(s) / Table(s)                        | Notes                                      |
|-------------------|-----------------------------------------|--------------------------------------------|--------------------------------------------|
| Dashboard         | SaaS Governance, Nexora Executive Command Center    | pages/saas_governance.py, pages/executive_dashboard.py | Shows SaaS optimization KPIs               |
| Mart/View         | mart_saas_optimization                  | mart_kpi_table_schemas.md                  | Aggregated SaaS optimization data          |
| Warehouse Table   | saas_usage, saas_costs                  | saas_usage, saas_costs (Supabase/Postgres) | Source of truth for SaaS optimization      |
| Ingestion Script  | saas_ingest.py                          | saas_ingest.py                             | ETL for SaaS usage/costs                   |
| Cloud Source      | SaaS Provider APIs                      | O365, Google Workspace, Salesforce, etc.   | Raw SaaS usage/cost data                  |

---

## KPI: AI Forecasts
| Layer             | Source/Component                        | File(s) / Table(s)                        | Notes                                      |
|-------------------|-----------------------------------------|--------------------------------------------|--------------------------------------------|
| Dashboard         | Nexora Executive Command Center, Technical Analytics| pages/executive_dashboard.py, pages/technical_analytics.py | Shows AI-powered forecasts                  |
| Mart/View         | mart_ai_forecasts                       | mart_kpi_table_schemas.md                  | Aggregated AI forecast data                |
| Warehouse Table   | ai_forecast_results                     | ai_forecast_results (Supabase/Postgres)    | Source of truth for AI forecasts           |
| Ingestion Script  | ai_forecast_engine.py                   | ai_forecast_engine.py                      | ETL/ML for AI forecasting                  |
| Cloud Source      | Cloud Billing APIs/Exports, Usage APIs  | AWS, Azure, GCP                            | Raw usage and billing data                |

---

> Update this registry for every critical KPI to maintain full data lineage, governance, and compliance. This document is the foundation of your enterprise governance metadata layer.
