# NEXORA V1 Security and Regression Results

Execution date: 2026-11-13
Qualification data: synthetic only.

## Route, identity, and tenant controls

- **Page boundary:** `allowed_page_specs` and the V1 route policy register only
  Login, Logout, Customer Workspace, Approvals, and Reports. Customer workflow
  pages are limited to `client_admin`, `executive`, `cio`, `finance`,
  `operations`, and `auditor`; deferred pages are denied even if present in a
  legacy role map.
- **Navigation:** persona navigation was exercised in the authenticated app.
  The executive's Home, Board Pack, and Approvals entries reached the expected
  customer workflow pages. Auditor Home remains mapped to the approved audit
  item; its authenticated default is still constrained by the route policy.
- **Deferred APIs:** the production and compatibility FastAPI route registries
  omit the deferred Cost, Reports, Alerts, Recommendations, Governance, FinOps,
  and SaaS legacy route families. Tests confirm direct `/api/v1/cost` returns
  404. FastAPI is not part of the browser Compose project; these are API-level,
  not browser-level, results.
- **Tenant/JWT authorization:** live PostgreSQL checks denied Customer B access
  to Customer A's workspace and denied a JWT tenant-scope spoof. API/security
  regression cases deny actor/role spoofing, wrong-role approval actions, and
  unauthorized export access.
- **PostgreSQL enforcement:** `events`, `evidence_objects`, and `approvals`
  have forced RLS. Runtime role `nxr_customer_workflow_app` is neither a
  superuser nor `BYPASSRLS`; five tenant policies were present. These
  catalog/security checks were performed against the isolated live database.
- **G08:** privileged owner operations remained separate and fail-closed. No
  G08 activation or privileged execution was performed.
- **Background work:** the V1 worker/beat profile remains opt-in and disabled;
  startup guards reject V1 worker/beat execution, the V1 periodic schedule is
  empty, and a legacy task refuses to execute before its body. No production
  scheduler or alert delivery is claimed active.

## Regression results

| Validation | Result |
|---|---:|
| Source-mounted route, navigation, authentication, tenant, customer workflow, recovery, and operations regression selection | **73 passed, 0 failed, 4 skipped** |
| Skips | **4** PostgreSQL fixture cases requiring host PostgreSQL cluster binaries unavailable in the Linux test container. The separately running integrated PostgreSQL environment was checked live as described above. |
| Browser end-to-end journey | **Passed** for the synthetic customer workflow in the single route-freeze deployment; see [Integrated Customer Acceptance](./INTEGRATED_CUSTOMER_ACCEPTANCE.md). |
| API route and authorization checks | **Passed** in their focused FastAPI regression selection; separate from the browser deployment. |
| Browser download event | **Not captured**; export generation and persisted package integrity/linkage were verified. |

The test aggregate is reported as an aggregate for the actual focused regression
run; it is not combined with earlier reports' test counts. The four skipped
fixture cases are not counted as passes. Live PostgreSQL catalog, RLS, runtime
privilege, workflow persistence, and Customer B authorization checks provide
separate execution evidence, not a substitution for those skipped fixtures.

## Limitations

- The integrated journey restarted the application container, not PostgreSQL.
- Unknown `/api/...` paths on the Streamlit host return app-shell HTML with
  HTTP 200. This is not a mounted API response; FastAPI API denial is supported
  by its separate route-registry and TestClient checks.
- The saved export's browser file-transfer event was not captured.
- No production schedule, alert delivery, hosted identity/database behavior,
  or off-host recovery was tested or activated.

