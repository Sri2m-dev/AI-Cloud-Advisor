# NEXORA V1 Updated Route Matrix

Review date: 2026-11-13  
The checked-in M0 catalogue remains unchanged; this is the runtime enforcement
overlay for the current V1 candidate profile.

## Page routes

| Route class | Count / examples | Runtime decision | Evidence and notes |
|---|---:|---|---|
| Authenticated customer workflow extension | Customer Workspace, Approvals, Reports | Allowed only for `client_admin`, `executive`, `cio`, `finance`, `operations`, and `auditor`; Approval and Reports are aliases into the canonical workflow. | `auth/v1_route_policy.py`, `app_main.py`, customer workflow API/service tests. |
| M0 supported candidates, excluding explicit closures | 20 of the catalogue's 23 candidates | Eligible only when the existing role map contains the page. Eligibility is not acceptance or database-contract certification. | M0 still marks these routes `NOT_CURRENTLY_CERTIFIED`. |
| Cost Intelligence | `pages/cost_intelligence.py` | Denied for every role. | Its three unknown cost relations are not required for the approved journey; full dashboard behavior is deferred. |
| Dependency Analysis | `pages/dependency_analysis.py` | Denied for every role. | Its Enterprise Graph repository reaches unresolved legacy application/technology/spend-mapping relations. |
| Technology Digital Twin | `pages/technology_digital_twin.py` | Denied for every role. | Its service reads legacy `application_registry`, `mart_enterprise_spend_v2`, and technology inventory sources. |
| Controlled-supporting M0 routes | 8 | Not registered. | Existing route policy and page-spec tests. |
| Deferred M0 routes | 82 | Not registered. | Existing route policy and page-spec tests. |
| Logout | `pages/logout.py` | Always available as the termination route. | Explicit route-policy exception. |

The three explicit exclusions are applied before candidate/role-map checks, so
adding a page to a role mapping cannot make them reachable. Direct Streamlit
page registration tests cover all three paths. The current browser target was
unavailable, so this is not browser-level URL evidence.

### Canonical Data Fabric credential boundary

The V1 Enterprise Registry composition uses only the canonical Data Fabric
source and does not merge legacy rows; focused service tests pass. Production
page acceptance remains blocked because operations Compose gives the frontend
the anon-key file, while the service-role-key file is configured for the API
container. The registry reader requires a server-side Data Fabric credential.
Do not pass the service-role secret to the browser; provide an authenticated
backend read path or exclude the dependent page before claiming it accepted.

## API routes

| Endpoint family | Decision | Evidence |
|---|---|---|
| `/api/v1/approvals/*` | Mounted through the canonical `CustomerWorkflowService`; bearer identity, role, stage, tenant, and export checks remain enforced. | Approval API tests cover unauthenticated denial, wrong-stage/wrong-role denial, actor spoofing, A/B isolation, history, and export. |
| `/api/v1/cost` | Not mounted; direct requests return 404 in both production and compatibility FastAPI applications. | `tests/security/test_v1_route_enforcement.py`. |
| Reports, alerts, recommendations, governance, FinOps, SaaS legacy APIs | Not mounted by the V1 API entry points. | API registry tests in `tests/security/test_v1_route_enforcement.py`. |
| G08 owner execution | Separate and fail-closed; no privileged activation was performed. | Existing G08 fail-closed route tests and architecture decision. |

## Persona navigation correction

The customer workflow uses an existing Home slot for client administrator,
executive, CIO, finance, and operations roles, preserving the curated item
counts and canonical section taxonomy. The auditor retains its existing Audit
Timeline Home item; the app's authenticated default and the Reports alias still
provide access to the customer workspace. All destinations remain subject to
the route policy and role authorization.

## Worker and scheduled-job entry points

| Entry point | V1 control | Verification |
|---|---|---|
| Operations `worker` Compose service | Opt-in `jobs` profile; fixed V1 profile, schedule disabled, empty allowlist; runtime startup refuses the V1 worker role. | `test_runtime_and_config.py` validates startup denial and Compose preflight. |
| Operations `beat` Compose service | Same V1 controls; runtime startup refuses the V1 beat role. | `test_runtime_and_config.py`. |
| Celery schedule construction | `periodic_schedule` returns `{}` for the V1 profile, regardless of an allowlist. | `test_health_and_jobs.py`. |
| Queued legacy task bodies | `require_enabled_task` raises before work for V1 in development or production, even when manually allowlisted. | `test_health_and_jobs.py`. |
| FastAPI in-process scheduler | Existing startup gate still refuses enabling legacy jobs in the V1 API route profile. | `test_v1_route_enforcement.py`. |

No claim is made that any production worker, schedule, monitor, or alert
delivery is active.
