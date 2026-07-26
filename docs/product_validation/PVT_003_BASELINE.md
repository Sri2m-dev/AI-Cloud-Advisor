# PVT-003 Baseline Product Certification

Baseline: `main` at `c82cc9faa0996581e7d5808540cd9782428dcce9`
Observed locally: 2026-07-26
Local main instance: `http://127.0.0.1:8502`

## Certification boundary

The main application started successfully. The authenticated dashboard pages require
an existing user session; no credentials, database changes, or synthetic data were
used for this certification. The values below are the accepted PVT-001 observed UI
baseline and are paired with code-traced source ownership.

| Product area | Baseline value/state | Authoritative current path |
| --- | --- | --- |
| Executive Dashboard: Enterprise Spend | `$0` | `EnterpriseFinancialModel`; legacy `mart_executive_summary` / `mart_enterprise_spend_v2` cards |
| Executive Dashboard: Allocation Coverage | `0.0%` | `EnterpriseFinancialModel.get_reconciliation_status()` |
| Executive Dashboard: Reconciliation | `Unmapped` | `EnterpriseFinancialModel` |
| Executive Dashboard: Optimization Potential | `$0` | Business-process/service financial inputs; legacy mart/recommendations support |
| CIO Dashboard: Technology Spend | `$0` | `TechnologySpendService` → `mart_enterprise_spend_v2` |
| CIO Dashboard: Applications | `0` | `application_registry` |
| CIO Dashboard: Technologies | `0` | `technology_inventory` / unallocated-spend analysis |
| CIO Dashboard: AWS Accounts | `0` | `unified_cloud_costs` account fields and cloud-account data |
| CIO Dashboard: Allocation Coverage | `0.0%` | `EnterpriseFinancialModel` |
| CIO Dashboard: Reconciliation | `Unmapped` | `EnterpriseFinancialModel` |
| Enterprise Spend / Cloud views | No CUR-derived spend | Existing marts and `unified_cloud_costs` |
| Business Services / Applications | No CUR-derived allocation | Business architecture repositories and application spend mapping |
| FinOps / Optimization | No CUR-derived certified result | Existing marts/rules; CUR alone is insufficient for utilization claims |

## Source-path findings

```text
Current upload page
→ direct simplified `unified_cloud_costs` insert

Current canonical financial model
business_processes → business_services → application_portfolio
→ EnterpriseFinancialModel → reconciliation cards

Current CIO technology-spend card
mart_enterprise_spend_v2 → TechnologySpendService
```

The current paths are disconnected. PVT-003A intentionally adds no product
behavior; PVT-003B through PVT-003D must connect tenant-scoped normalized CUR
facts to attribution, the canonical financial model, marts, and UI.

## Baseline non-goals

- No CUR upload was performed.
- No DEV or Production database was accessed or modified.
- No dashboard value was changed.
- No real Owner CUR was accessed.
