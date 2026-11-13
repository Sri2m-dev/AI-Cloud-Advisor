# Remaining Blockers

**Gate: V1 DATABASE CONTRACT NO-GO**

1. **Three required/supporting contracts are unresolved.**
   - `approval_requests` and `approval_history`: obtain complete lifecycle,
     key, tenant, owner, grant, RLS and retention decisions from the approval
     contract owner. Do not substitute `approval_audit` or assume the
     `nexora_v1_*` tables serve legacy callers.
   - `enterprise_data_fabric`: owner decides whether to remove the optional
     persistence or adapt it to canonical `data_fabric`; do not create a
     second authoritative graph.
2. **Seven objects remain UNKNOWN:** `alert_executions`, `approval_queue`,
   `enterprise_cost_attribution`, `mart_cost_anomalies`,
   `mart_enterprise_forecast`, `mart_optimization_opportunities`, and
   `recommendation_events`. Resolve scope, owner and canonical source before
   implementation. `alert_executions` has a live API caller despite its older
   legacy-unreachable classification.
3. **Deferred functionality is not actually isolated.** Product/release owner
   must approve the exact V1 route allowlist. The M0 catalogue is proposed;
   current navigation is broader, and direct-route restriction is unfinished.
   Implement and test route/API denial and prevent deferred jobs or persistence
   from being activated by environment flags.
4. **Six additional SC-001 V1_REQUIRED objects remain unresolved outside this
   29-object set:** `application_registry`,
   `application_spend_mapping`, `mart_application_spend`,
   `mart_enterprise_spend`, `mart_enterprise_spend_v2`, and
   `technology_inventory`.
5. **Application-level acceptance is incomplete.** After contracts and
   allowlist closure, run fresh-database migration/replay, schema catalog,
   ownership/grants/RLS checks, JWT spoofing negatives, tenant A/B API tests,
   full application startup, approval/finance/export tests, direct-route
   denial and browser journey on one isolated environment.

## Exit criteria

Do not declare V1 DATABASE CONTRACT GO until every reachable V1-required call
has an authoritative migration, supporting contracts are approved, deferred
paths are demonstrably inaccessible, tenant and least-privilege tests pass,
the six other SC-001 required dependencies are resolved, and the integrated
application/API acceptance succeeds.
