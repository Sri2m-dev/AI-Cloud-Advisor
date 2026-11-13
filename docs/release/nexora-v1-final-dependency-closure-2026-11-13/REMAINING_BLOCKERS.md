# NEXORA V1 Final Dependency Closure — Remaining Blockers

## V1 database contract — NO-GO

1. **Twenty M0 supported-candidate pages remain eligible for role-based
   registration.** Their catalogue metadata is still
   `NOT_CURRENTLY_CERTIFIED`, and this task did not qualify every dependency
   called by those pages. Close each route against an authoritative contract or
   remove it from the V1 route profile before declaring the complete database
   gate GO.
2. **Production Enterprise Registry reads are not configured in the frontend.**
   `deploy/operations/compose.yaml` gives the frontend the anon-key file
   (`SUPABASE_KEY_FILE`); the service-role-key file is mounted in the API
   container instead. `enterprise_registry_service` requires a server-side
   Data Fabric reader in production/V1. The direct page therefore fails closed
   until an authenticated backend reader is implemented or the route is
   excluded. Do not move the service-role secret into the frontend.
3. **The canonical schema-contract artifact remains blocked.** The original
   SC-001 contract still lacks DDL/contracts for legacy objects; this work
   classifies six specific names by current journey reachability but does not
   rewrite that historical contract or create compatibility SQL.
4. **Cost Intelligence remains deferred, not implemented.** The three
   unknown cost dependencies are still undefined. The route and API are
   blocked, but the dashboard is not claimed to be reproduced by the canonical
   workspace.
5. **No one-target authenticated browser acceptance was completed.** The
   existing local browser target could not reach its Streamlit server. API and
   service tests do not establish browser login, logout, or reauthentication.

## Production readiness — NO-GO

- No frozen release candidate or single integrated deployment has been
  accepted.
- The local PostgreSQL workflow qualification is not evidence of installed
  Supabase schema/RLS or a hosted application integration.
  - Canonical-only Enterprise Registry behavior passed service tests, but its
    production frontend credential path is not accepted; see the database
    blockers above.
- Independent off-host recovery, owner-approved RPO/RTO, key custody, and
  production alert delivery remain unqualified as recorded in the master
  status report.
- The operations V1 profile prevents Celery jobs from running; production
  scheduling and alert delivery are not active.
- G08 owner operations remain fail-closed and were not activated.
- Customer pilot, support, terms, and actual operating-cost evidence remain
  outstanding.

## Next executable task

Inventory the database dependencies of the 20 remaining role-eligible M0
candidate routes, beginning with a safe authenticated backend reader for
canonical Data Fabric pages (or explicitly excluding those pages). For each
route, verify its authoritative contract and authorization on a fresh isolated
database or exclude it through the server-side V1 route policy. Then rerun the
consolidated API/database/browser acceptance on one frozen candidate. Do not
write SQL from call-site guesses or expose a service-role secret to the
frontend.
