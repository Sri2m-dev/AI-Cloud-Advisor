# NEXORA V1 Final Route Manifest

Qualification date: 2026-11-13
Scope: local, synthetic route-freeze candidate; not production activation.

## Frozen decision

The 20 remaining M0 supported candidates are classified **4 REQUIRED_V1, 0
OPTIONAL_V1, and 16 DEFERRED**. No candidate is optional: pages without a
complete V1 security and database contract are excluded rather than exposed
conditionally. The canonical Customer Workspace is an additional required
workflow extension and is not one of the 20 M0 candidates.

The 20-candidate denominator excludes the three earlier explicit exclusions:
Cost Intelligence, Dependency Analysis, and Technology Digital Twin. The M0
catalogue still contains 23 `SUPPORTED_CANDIDATE` rows, 8
`CONTROLLED_SUPPORTING` rows, and 82 `DEFERRED_NOT_PUBLIC_V1` rows; its
acceptance metadata remains proposed / `NOT_CURRENTLY_CERTIFIED`.

## Candidate manifest

| M0 candidate | Page | Decision | Reason |
|---|---|---|---|
| Login | `pages/login.py` | **REQUIRED_V1** | Authenticated entry to the tenant workflow. |
| Logout | `pages/logout.py` | **REQUIRED_V1** | Required termination and reauthentication lifecycle. |
| Approvals | `pages/approval_center.py` (`/approval_center`) | **REQUIRED_V1** | Role-protected alias into the canonical Customer Workflow approval record and history. |
| Reports | `pages/reports.py` (`/reports`) | **REQUIRED_V1** | Role-protected evidence-export entry; final export generation and authorization remain in the canonical Customer Workspace. |
| Analyse Your Environment | `pages/analyze_environment.py` | **DEFERRED** | Environment assessment is not part of the approved workflow and has no V1 acceptance requirement. |
| Application Portfolio | `pages/application_inventory.py` | **DEFERRED** | Portfolio inventory is not needed to complete the evidence and approval journey. |
| Audit Timeline | `pages/audit_timeline.py` | **DEFERRED** | The canonical workflow exposes its own approval history; the separate legacy timeline is not required. |
| CEO Workspace | `pages/ceo_workspace.py` | **DEFERRED** | CEO approval is performed as the final stage in the canonical workflow, not through this separate workspace. |
| Financial Health / CFO Workspace | `pages/cfo_workspace.py` | **DEFERRED** | Financial dashboard acceptance and its data dependencies are outside the approved journey. |
| CIO Workspace | `pages/cio_workspace.py` | **DEFERRED** | CIO approval is a canonical workflow stage; a separate CIO workspace is unnecessary. |
| Executive Decisions / Decision Intelligence | `pages/decision_intelligence.py` | **DEFERRED** | The required customer decision is created in the canonical workspace; the broader page is not required. |
| Enterprise AI Copilot | `pages/enterprise_ai_copilot.py` | **DEFERRED** | V1 includes only bounded, evidence-grounded Ask, not the broader copilot surface. |
| Enterprise Registry | `pages/enterprise_registry.py` | **DEFERRED** | Not essential to the workflow; production page access would require a server-side Data Fabric reader. No service-role credential is exposed to the frontend and no new backend architecture is approved here. |
| Enterprise Spend | `pages/enterprise_spend.py` | **DEFERRED** | Broader spend analytics are not required for the synthetic customer journey. |
| Executive Overview / Command Center | `pages/executive_command_center.py` | **DEFERRED** | Dashboard functionality is outside the minimum workflow and is not separately qualified. |
| FinOps Workspace | `pages/finops_workspace.py` | **DEFERRED** | FinOps analytics are outside the approved V1 journey. |
| Operations Command Center | `pages/operations_command_center.py` | **DEFERRED** | Operational administration is not a customer workflow requirement. |
| Organization & Team | `pages/organization_administration.py` | **DEFERRED** | Organization administration is not required to exercise the already-provisioned synthetic tenants. |
| Relationship Explorer | `pages/relationship_explorer.py` | **DEFERRED** | Relationship graph functionality is outside the V1 journey and its legacy dependencies are not accepted. |
| Welcome | `pages/welcome.py` | **DEFERRED** | A separate landing page is unnecessary; authenticated users enter the customer workspace. |

## Runtime enforcement

- [`auth/v1_route_policy.py`](../../../auth/v1_route_policy.py) is the
  application-entry allowlist. It admits the required workflow pages and the
  separate Customer Workspace extension; it does not trust role-map membership
  to make any other M0 page reachable.
- [`app_main.py`](../../../app_main.py) registers only page specs returned by
  that policy. The sidebar links use the same role-scoped page mappings.
- Customer Workspace, Approvals, and Reports are restricted to
  `client_admin`, `executive`, `cio`, `finance`, `operations`, and `auditor`.
  Logout remains available for termination.
- The Approvals and Reports routes were opened in the authenticated browser.
  `/approval_center` rendered “Customer Approvals”; `/reports` rendered
  “Evidence-linked Exports”. Both provide an explicit link back to Customer
  Workspace.
- Deferred page registration is covered by route-policy tests. An authenticated
  browser request to `/enterprise_registry` rendered the app's page-not-found
  fallback rather than the deferred page.
- Cost Intelligence, Dependency Analysis, and Technology Digital Twin remain
  explicitly denied; they are not reclassified or counted among the 20.
- V1 background worker and scheduled-job entry points remain disabled by the
  V1 profile and fail closed; this freeze does not activate G08 or production
  jobs.

## API boundary

The isolated browser deployment contains the Streamlit application and
qualification services, not the separate FastAPI deployment. FastAPI route
registry tests verify that deferred legacy routers are not mounted and that a
direct `/api/v1/cost` request returns 404. The integrated Streamlit host returns
app-shell HTML for unknown `/api/...` paths; this is not an API response and is
not represented as FastAPI browser-level evidence.

