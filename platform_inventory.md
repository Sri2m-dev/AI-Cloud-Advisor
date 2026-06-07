## Standardized Dashboards & Navigation

Only the following pages are official and should remain in /pages:

| Page File                  | Status   | Notes                |
|----------------------------|----------|----------------------|
| Executive_Dashboard.py   | ACTIVE   | Official dashboard   |
| Approval_Center.py       | ACTIVE   | Approval workflows   |
| Operations_Workspace.py  | ACTIVE   | Operations workspace |
| Technical_Analytics.py   | ACTIVE   | Technical analytics  |
| SaaS_Governance.py       | ACTIVE   | SaaS governance      |
| Audit_Timeline.py        | ACTIVE   | Audit timeline       |

All other pages (including 0_Login.py, Logout.py, and any legacy/archived dashboards) are deprecated or for authentication only. Remove or archive any non-standard pages to maintain a clean navigation structure.
# Platform Inventory (Enterprise Architecture Registry)

| Component                  | Status  | Used By         | Replace? |
|----------------------------|---------|-----------------|----------|
| aws_cost_sync.py           | ACTIVE  | ingestion       | keep     |
| cost_analysis.py           | LEGACY  | old UI          | remove   |
| unified_cloud_costs        | ACTIVE  | marts           | keep     |
| recommendation_events      | LEGACY  | old workflows   | replace  |
| leadership_dashboard.py    | LEGACY  | old dashboard   | merge    |

# --- Source of Truth Registry ---

## Spend
| Table/View                | Status   | Notes                        |
|---------------------------|----------|------------------------------|
| unified_cloud_costs       | OFFICIAL | Source of truth (spend)      |
| cost_data                 | DEPRECATED | Use unified_cloud_costs      |
| cloud_cost_history        | DEPRECATED | Use unified_cloud_costs      |
| duplicate spend tables    | DEPRECATED | Use unified_cloud_costs      |

## Recommendations
| Table/View                    | Status   | Notes                                 |
|-------------------------------|----------|---------------------------------------|
| recommendations               | OFFICIAL | Source of truth (recommendations)     |
| recommendation_transition_log | OFFICIAL | Audit log for recommendations         |
| recommendation_events         | DEPRECATED | Use recommendations                   |
| fragmented workflow tables    | DEPRECATED | Use recommendations                   |

## Governance KPIs
| Table/View         | Status   | Notes                              |
|--------------------|----------|------------------------------------|
| vw_governance_kpis | OFFICIAL | Source of truth (governance KPIs)  |

---

Update this registry as you consolidate and modernize your data model. Only use official sources for new marts, KPIs, and dashboards.

---

Add new components, scripts, tables, or dashboards as you build or refactor. Use this as your single source of truth for platform status and modernization planning.
