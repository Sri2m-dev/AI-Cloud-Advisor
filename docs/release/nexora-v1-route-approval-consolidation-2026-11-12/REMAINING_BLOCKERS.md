# Remaining Blockers

## Database contract and product scope

1. **Three unknown database dependencies remain on the supported-candidate
   Cost Intelligence page:** `enterprise_cost_attribution`,
   `mart_cost_anomalies`, and `mart_optimization_opportunities`. Their
   authoritative schema, tenancy, and output contracts are not established.
   Either obtain those contracts and validate them or remove Cost Intelligence
   from the public V1 route profile until it can fail safely.
2. **Six additional SC-001-required database objects** remain outside the
   original 29-object inventory and unresolved in the canonical bootstrap
   evidence.
3. **No definitions were added for the 29 inventory objects.** The two legacy
   approval table calls have been removed from the reachable customer path,
   not resolved by creating equivalent tables. Other unknown object contracts
   remain unknown even if current route policy excludes their pages.
4. The checked-in M0 catalogue still marks itself proposed and its candidate
   routes `NOT_CURRENTLY_CERTIFIED`. The current task directs using it for route
   scoping, but product acceptance metadata remains unreconciled.

## Route and runtime boundaries

5. Route enforcement and API mounts were verified in the local source profile;
   this is not an authenticated end-to-end browser acceptance. Only an
   unauthenticated direct request to a deferred URL was checked in a browser.
6. V1 API startup fails closed for `BACKGROUND_JOBS_ENABLED=true`; a
   separately launched Celery worker/task profile is not disabled or validated
   by this change. Its deployment entry point and database dependencies must be
   identified before claiming all deferred backend functionality is
   inaccessible.
7. Supported-candidate pages other than the tested customer workflow have not
   been accepted as having complete database contracts.
8. The wider navigation run has three failing persona-data assertions. The
   differences were not changed as part of this task and need a separate
   product-navigation decision.

## Qualification verdict

- Canonical approval architecture: **implemented locally** on the
  `CustomerWorkflowService`; not a production or browser acceptance.
- Route-profile restrictions: **implemented locally** in Streamlit and the
  two FastAPI entry points; separate task-worker entry points remain open.
- V1 database contract: **NO-GO**.
- Overall production activation: **NO-GO**.
- G08 owner operations remain **fail-closed**.

## Next executable task

Resolve the three Cost Intelligence contracts from authoritative product and
database sources, or remove that page from the V1 profile. Then address the six
remaining SC-001-required objects on a fresh isolated PostgreSQL target and
repeat database/API/browser acceptance. Do not write speculative DDL.
