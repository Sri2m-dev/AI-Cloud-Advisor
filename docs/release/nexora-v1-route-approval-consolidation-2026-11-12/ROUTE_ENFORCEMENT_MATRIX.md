# V1 Route Enforcement Matrix

## Streamlit pages

The route catalog contains 113 rows. The runtime treats only
`SUPPORTED_CANDIDATE` rows as eligible for registration and then applies the
existing role-to-page mapping. Login is the only unauthenticated page.
Authenticated sessions are checked for a tenant context before a registered
page runs; role mismatches are replaced with the role derived by the
authenticated context.

| Catalogue scope | Count | Runtime behavior | Evidence |
|---|---:|---|---|
| `SUPPORTED_CANDIDATE` | 23 | Registered only for roles already mapped to that page. `pages/customer_workspace.py` is an explicit customer-workflow extension for client admin, Finance, CIO, executive, operations, and auditor roles. | `tests/security/test_v1_route_enforcement.py` asserts catalogue totals and per-role registration behavior. |
| `CONTROLLED_SUPPORTING` | 8 | Not registered in the public V1 route profile pending separate acceptance. This includes Business Services and Data Fabric pages with legacy/optional dependencies. | Same route-policy test; direct page URLs are not in the Streamlit registry. |
| `DEFERRED_NOT_PUBLIC_V1` | 82 | Not registered. The sidebar is filtered using the same policy; selected page links and programmatic links are checked before navigation. | Same route-policy test and local direct-URL browser check. |

`Approval Center` and `Reports` remain role-restricted links into the canonical
customer workflow. They no longer load the legacy approval/reporting services.
The Reports alias exposes only the evidence-linked export workflow, which
requires final approval.

The browser was opened at the unauthenticated local app. The root rendered the
login page; a direct request to `/cloud_connections` returned HTTP 404. This
proves unauthenticated direct-route denial. An authenticated browser journey
was not run in this task; role-specific registration and API authorization are
covered by automated tests.

## HTTP APIs

| Entry point | Mounted routes | Removed from this profile |
|---|---|---|
| `backend.main:app` | Auth, tenant-guarded cost, and authenticated customer approvals; health/readiness/metrics | Alerts, recommendations, legacy reports, governance |
| `api.v1.endpoints:app` | Authenticated customer approvals and health | Legacy governance, FinOps, and SaaS routers |

Approval API reads, requests, transitions, history, and export use the
authenticated customer-workflow service. A missing bearer token is denied;
organization/actor selector overrides are rejected; tenant B receives no
tenant A approval record. Removed router paths are absent from both app
registries, so navigation bypass cannot invoke those APIs.

The V1 API also rejects `BACKGROUND_JOBS_ENABLED=true` at startup rather than
starting the legacy in-process scheduler. This does **not** disable a separately
launched Celery worker or task queue. Those deployment profiles remain an
operational blocker and are not represented as disabled by this route change.

## G08 and supported-page boundary

G08 owner-operation endpoints remain separate and fail-closed. The existing
G08 integration suite continues to verify denial when owner assurance and
atomic execution providers are unavailable.

For registered supported-candidate pages, the entry point validates the
authenticated tenant context, the role allowlist controls registration, and
the page's existing role/RPC/data-access guards remain in force. This route
gate is not proof that each candidate page's unresolved database contracts
have been completed.

## Source catalogue caveat

The task instruction identified M0 as approved for route scoping. The checked-in
catalogue still labels itself proposed and marks acceptance
`NOT_CURRENTLY_CERTIFIED`. This implementation enforces its scope values but
does not claim product acceptance or database readiness for any candidate
page.
