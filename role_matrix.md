# Role Matrix for AI-Cloud-Advisor Platform

| Role         | Access Scope                |
|--------------|----------------------------|
| Leadership   | Executive only             |
| FinOps       | Approvals + Dashboards     |
| CloudOps     | Operations                 |
| Engineering  | Technical Analytics        |
| Governance   | Audit + SaaS               |

## Description
- **Leadership**: Access to Executive Dashboard only.
- **FinOps**: Access to approval workflows and all dashboards.
- **CloudOps**: Access to Operations Workspace.
- **Engineering**: Access to Technical Analytics.
- **Governance**: Access to Audit Timeline and SaaS Governance.

## Implementation Guidance
- Enforce this matrix in your RBAC logic (e.g., in Streamlit page guards or backend API).
- Use this as the source of truth for all role-based access checks.
