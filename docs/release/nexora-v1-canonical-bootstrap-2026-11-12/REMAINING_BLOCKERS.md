# NEXORA V1 Canonical Bootstrap — Remaining Blockers

## Gate

**CANONICAL V1 BOOTSTRAP: NO-GO.**

The bounded 43-input local replay and synthetic workflow pass, but acceptance
requires the complete application database contract, runtime startup, and
security validation against that complete schema.

## Blocking items

1. **Missing authoritative schema contracts.** The current offline inventory
   identifies 29 distinct API object names without SQL creation definitions:
   approval requests/history/queue, cloud connections and upload records,
   connector state, recommendation/alert events, KPI and mart objects,
   platform-health objects, and SaaS technology views. Recover approved
   schema-only definitions, constraints, ownership, tenant keys, RLS/grants,
   and aggregation semantics. Do not infer them from application queries.
2. **V1 scope disposition for legacy callers.** The bounded synthetic workflow
   uses the namespaced `v1_customer_workflow` contract and does not call the 29
   legacy objects. Connector/cost, alerts, recommendation events, KPI/mart,
   platform-health, technology views, and legacy approval objects are candidate
   deferrals only; no approved V1 scope decision was found. Confirm the
   commercial V1 page/route set and disposition each dependency before claiming
   either that it is required or safely deferred.
3. **Full application bootstrap is not established.** The five-table public
   prerequisite is intentionally incomplete. The 43-input replay covers the
   existing migration chain, not every schema dependency used by the current
   application.
4. **Application runtime not verified on the bootstrap.** The test starts
   `CustomerWorkflowService`, not the complete Streamlit/FastAPI application.
5. **Browser journey not run on the new target.** The service-level workflow
   passes, but login, JWT propagation, pages, and browser logout/reauthentication
   against this database remain unverified.
6. **Hosted Supabase compatibility not tested.** Auth shims and roles are local
   test scaffolding. No Supabase API or project was accessed; hosted Auth,
   PostgREST, role ownership, RLS, and PostgreSQL 17 compatibility are
   unverified.
7. **Production migration semantics remain unqualified.** The hash ledger and
   second-pass skips are test-only. No production migration runner or deployed
   migration history was exercised; the production manifest correctly remains
   non-executable.

## Historical finding superseded

The earlier report of a compilation failure in
`migrations/data_fabric/0020_create_stewardship_rpcs.sql` is historical. The
current source compiled in the replay, and migrations 0021–0023 executed. It is
not a remaining blocker.

## Next executable task

Obtain approved schema-only definitions and tenant-access contracts for the
29 unresolved API objects. Classify them as V1-required or deferred without
creating speculative replacements. Then version the complete V1 bootstrap and
repeat fresh-database migration, application-startup, and tenant-security
verification.

No production activation, hosted project change, cloud operation, commit, tag,
push, deployment, or G08 activation is authorized by this qualification.
