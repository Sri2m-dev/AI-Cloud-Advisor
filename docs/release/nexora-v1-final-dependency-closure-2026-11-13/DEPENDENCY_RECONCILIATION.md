# NEXORA V1 Final Reachable Dependency Reconciliation

Review date: 2026-11-13  
Branch: `program/nexora-production-activation`  
Scope: local repository changes and isolated synthetic tests only. No cloud,
Supabase, protected database, or production resource was accessed or changed.

## Executive decision

The six SC-001 objects are no longer dependencies of the approved customer
workflow: three are superseded for the workflow's canonical reads and three
are excluded by the enforced V1 route profile. No speculative SQL or
compatibility objects were created.

**Six-object reachable-path closure: GO within the current customer workflow
scope. Full V1 database contract qualification: NO-GO.** Twenty remaining M0
supported-candidate pages are still eligible for role-based registration and
are not collectively certified for their database dependencies. The M0 file
itself continues to mark the catalogue proposed and its candidates
`NOT_CURRENTLY_CERTIFIED`.

## Cost Intelligence decision

The approved V1 journey is authenticated workspace, evidence, bounded Ask,
decision, staged approval, and evidence-linked export. Cost Intelligence's
forecast/anomaly/optimization dashboard is not an essential step in that
journey. The canonical workspace does not provide a feature-equivalent
replacement for that entire dashboard; it provides only the bounded
evidence-backed customer workflow and canonical reads where available.
Therefore the dashboard is deferred rather than represented as complete.

The previous API object register identified three dependencies without
authoritative schema/output contracts: `enterprise_cost_attribution`,
`mart_cost_anomalies`, and `mart_optimization_opportunities`. The Cost
Intelligence page and `/api/v1/cost` route are now excluded. The route is
unmounted from both FastAPI entry points; unauthenticated direct requests
return 404. The three contracts remain unresolved and no financial values are
fabricated.

The page exclusion is enforced by
[`v1_route_policy.py`](../../../auth/v1_route_policy.py), not by hiding a
sidebar link. The API router was removed from
[`backend/main.py`](../../../backend/main.py). Tests cover direct page
registration denial and `/api/v1/cost` 404 responses for both API apps.

## SC-001 six-object reconciliation

The SC-001 source matrix remains the historical schema-contract baseline. Its
`V1_REQUIRED` labels are not silently rewritten; this table records their
current reachability and necessity after the route-profile changes.

| Object | Original SC-001 requirement | Current callers and reachability | Authoritative V1 source / necessity | Final classification |
|---|---|---|---|---|
| `application_registry` | Required for application identity and ownership fields. | Legacy `ApplicationRepository`, `EnterpriseGraphRepository`, and Technology Digital Twin paths read it. Dependency Analysis and Technology Digital Twin are now blocked. The Application Portfolio code path calls `ApplicationPortfolioService.get_portfolio`, which reads canonical Data Fabric entities. | The V1 composition has a canonical Data Fabric source and tests prove it does not merge legacy rows. However, the operations frontend receives only the anon key; the service-role key is mounted in the API container, not the frontend. The direct frontend reader is therefore not production-qualified. The approved customer workflow does not require this legacy relation. | **Superseded for the approved customer workflow; production qualification of the separate registry page remains blocked.** |
| `application_spend_mapping` | Required by legacy application/spend allocation joins. | Legacy cost-attribution, graph, and technology paths use it. Cost Intelligence, Dependency Analysis, and Technology Digital Twin are excluded; business allocation pages are M0 deferred or controlled-supporting. | No canonical application-level financial mapping contract exists, and the customer workflow does not require one. Application spend remains `UNKNOWN` rather than fabricated. | **Excluded through enforced V1 scope.** |
| `mart_application_spend` | Required by legacy application-spend projections. | Its business capability/service/process consumers are M0 deferred or controlled-supporting and are not registered in V1. | No canonical projection contract is established. Application-level spend allocation is not part of the approved customer workflow. | **Excluded through enforced V1 scope.** |
| `mart_enterprise_spend` | Required by legacy enterprise-spend readers. | Legacy leadership/reporting readers are outside the approved workflow. The reachable Enterprise Spend/customer path uses the P1 `EnterpriseSpendService` and source-fact financial authority. | P1 is the existing financial authority for V1 posture; unsupported amounts remain unavailable/unknown. This does not claim that every legacy report is reproduced. | **Superseded by an existing canonical V1 service.** |
| `mart_enterprise_spend_v2` | Required by legacy dashboards and guarded-query tests. | Technology Digital Twin is now blocked; the older dashboard and its direct consumers are deferred. | V1 financial posture uses P1; the V1 workflow does not require the legacy V2 dashboard projection. No replacement mart or DDL was added. | **Superseded by an existing canonical V1 service.** |
| `technology_inventory` | Required by legacy technology inventory and graph paths. | Technology Digital Twin and Dependency Analysis are blocked; Technology Portfolio is M0 deferred. Other legacy inventory readers are not used by the V1 customer workflow. | Technology portfolio/inventory is not required for evidence upload, bounded Ask, approval, or export. No canonical technology inventory contract was added. | **Excluded through enforced V1 scope.** |

### Classification totals

- 6 objects reviewed.
- 3 superseded by existing canonical V1 services.
- 3 excluded through enforced route scope.
- 0 new SQL definitions.
- 0 speculative compatibility objects.
- The legacy contracts remain unresolved for future/non-V1 functionality.

## Other reachability findings

`pages/dependency_analysis.py` is also excluded because its
`EnterpriseGraphService` reaches `EnterpriseGraphRepository`, which reads the
legacy application, technology, and spend-mapping relations. This was an
additional caller discovered during the six-object trace; it is not treated as
a customer-workflow requirement.

The V1 Enterprise Registry composition now requires the canonical Data Fabric
reader and skips compatibility-source reads. Its six focused tests pass,
including a V1 assertion that legacy-only rows are not returned. This does not
establish a production page integration: operations Compose gives the frontend
`SUPABASE_KEY_FILE` for the anon key, while `SUPABASE_SERVICE_ROLE_KEY_FILE`
is configured for the API service. The direct frontend registry reader has no
server-side reader credential and fails closed. Do not expose the service-role
secret to the browser; an authenticated backend read path or explicit route
exclusion is required before that page can be accepted.

The M0 route catalogue lists 23 supported candidates. The route policy now
excludes Cost Intelligence, Dependency Analysis, and Technology Digital Twin,
leaving 20 candidates eligible subject to each role's existing authorization
mapping. That is not evidence that the remaining candidates are certified.
See the [updated route matrix](./UPDATED_ROUTE_MATRIX.md).

## Navigation and role behavior

The extra “Customer Workspace” persona item caused the three reproduced GA
navigation assertions to fail by changing curated counts and adding a
noncanonical section. The implementation now reuses the existing Home entry
for `client_admin`, `executive`, `cio`, `finance`, and `operations`. The
auditor's existing Audit Timeline Home entry is preserved; its customer
workflow default and Reports alias continue to provide workspace access.
Existing role/page authorization is not broadened.

The full-page registration policy remains server-side and role-aware. G08
owner execution remains separate and fail-closed.

## Celery and scheduled-job closure

The operations Compose file keeps worker and beat under the opt-in `jobs`
profile, but both now receive `NEXORA_PRODUCT_PROFILE=v1`, a fixed disabled
schedule flag, and an empty job allowlist. Operational startup rejects those
worker/beat roles in the V1 profile. `periodic_schedule` returns no schedules
for V1, and every queued legacy task body refuses execution in V1 even if a
task name is manually allowlisted. The preflight validates this configuration.

This is a local configuration/code qualification only. It does not claim that
production scheduling, job monitoring, or alert delivery is active.

## Evidence references

- Original six-object evidence: [`application_schema_contract.md`](../../../cmp/CMP-P6-SC-001/application_schema_contract.md).
- Prior 29-object disposition: [`UPDATED_API_OBJECT_REGISTER.md`](../nexora-v1-route-approval-consolidation-2026-11-12/UPDATED_API_OBJECT_REGISTER.md).
- Approval and customer workflow authority: [`ARCHITECTURE_DECISION.md`](../nexora-v1-route-approval-consolidation-2026-11-12/ARCHITECTURE_DECISION.md).
- Route, API, job, customer-service, canonical portfolio/financial, and fresh PostgreSQL tests: [`REGRESSION_RESULTS.md`](./REGRESSION_RESULTS.md).
- Canonical-only Enterprise Registry composition and its deployment credential boundary: [`enterprise_registry_composition.py`](../../../services/enterprise_registry_composition.py), [`compose.yaml`](../../../deploy/operations/compose.yaml), and [`test_canonical_data_fabric_reader.py`](../../../tests/enterprise_registry/test_canonical_data_fabric_reader.py).
- Remaining gate blockers: [`REMAINING_BLOCKERS.md`](./REMAINING_BLOCKERS.md).

## Verdicts

| Gate | Verdict |
|---|---|
| Six SC-001 object paths in the approved customer workflow | **GO, limited to this route profile and evidence** |
| Full V1 database contract qualification | **NO-GO** — remaining supported candidates are not all database-contract qualified |
| PostgreSQL customer workflow service/recovery tests | **GO within the isolated synthetic test scope** |
| Authenticated browser acceptance | **NOT RUN** — the existing browser target did not respond |
| Overall V1 production readiness | **NO-GO** |
