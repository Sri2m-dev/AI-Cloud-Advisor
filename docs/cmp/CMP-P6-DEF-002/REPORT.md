# CMP-P6-DEF-002 - Complete Blank-Database Bootstrap Certification

**Status: BLOCKED. Recommendation: BLOCKED. Do not create staging.**

## 0020 root cause and correction

Data Fabric migration 0020 used `if not case ... end then` in
`stewardship_transition_review`. PostgreSQL rejects that construct while
compiling the PL/pgSQL function because the `NOT` operator was placed directly
before the `CASE` expression.

The authorized correction is the smallest syntax-only change:

```sql
if not (case v_current.state
    when 'discovered' then v_target in ('classified','rejected')
    when 'classified' then v_target in ('under_review','rejected')
    when 'under_review' then v_target in ('steward_approved','rejected')
    when 'steward_approved' then v_target in ('canonical','rejected')
    when 'canonical' then v_target='superseded'
    when 'superseded' then v_target='archived'
    else false
end) then
```

Parenthesizing the CASE result preserves the original allowed edges and the
fail-closed `else false` behavior. The focused stewardship regression checks the
corrected PostgreSQL form and all lifecycle edges. A fresh PostgreSQL compile
replay remains pending because PostgreSQL client/server binaries are unavailable
in this environment.

## Active public-schema inventory

The DEF-001 lexical/AST inventory remains the authoritative evidence source. It
covers 244 literal database API calls, 152 dynamic calls, SQL definitions,
qualified references, structural objects, and historical-file classifications.
The inventory is conservative and does not treat mocked tests as proof that an
object is unnecessary.

The 34 unresolved application names are:

- `alert_executions`
- `application_registry`
- `application_spend_mapping`
- `approval_history`
- `approval_queue`
- `approval_requests`
- `cloud_connections`
- `connector_certification`
- `connector_credential_vault`
- `connector_quality_event`
- `connector_sync_run`
- `cost_uploads`
- `enterprise_connector_registry`
- `enterprise_cost_attribution`
- `enterprise_data_fabric`
- `kpi_spend_by_cloud`
- `kpi_top_services`
- `kpi_total_cloud_spend`
- `mart_application_spend`
- `mart_cost_anomalies`
- `mart_enterprise_forecast`
- `mart_enterprise_spend`
- `mart_enterprise_spend_v2`
- `mart_optimization_opportunities`
- `mart_service_classification`
- `notification_queue`
- `platform_health_history`
- `platform_health_snapshot`
- `platform_operations_log`
- `refresh_kpis`
- `technology_inventory`
- `vw_inactive_saas_users`
- `vw_saas_renewal_risk`
- `vw_vendor_spend`

The five-table prerequisite bootstrap is authoritative only for the objects it
creates: `organizations`, `users`, `clients`, `recommendations`, and
`report_history`. The dated public migrations and Data Fabric migrations remain
classified as their existing versioned providers. Supabase `auth.*` functions
and standard roles are system prerequisites. Universal Evidence is a separate
local SQLite store. Historical dumps and scripts with unsafe grants, tenant
backfills, or conflicting definitions are evidence only, not deployment input.

## Missing DDL resolution

No missing object was added. Repository evidence does not establish the minimum
safe columns, keys, joins, tenant policies, or aggregation semantics for the
unresolved objects. Adding definitions would invent schema semantics and would
violate the checkpoint requirement to stop rather than guess. Therefore the
complete public bootstrap is not certifiable.

## Migration sequence

The manifest preserves one ordered sequence:

1. Standard blank Supabase project prerequisites.
2. `supabase/bootstrap/public_prerequisites.sql`.
3. All 17 dated public migrations in chronological order.
4. Data Fabric migrations `0001` through `0023` in numeric order.
5. Universal Evidence lifecycle initialization in its separate local SQLite
   store through the existing startup initializer.

The sequence is documented, but not executable as a deployment certification
until the public bootstrap is complete and a disposable PostgreSQL environment
is available.

## Certification results

| Check | Result |
| --- | --- |
| 0020 source correction | PASS; 15 focused stewardship tests |
| Public bootstrap | DEF-001 five-table prerequisites only; incomplete |
| Dated public migrations | Previously PASS; not rerun in this checkpoint |
| Data Fabric 0001-0019 | Previously PASS; not rerun in this checkpoint |
| Data Fabric 0020-0023 | NOT CERTIFIED; fresh PostgreSQL replay unavailable |
| Application schema contract | BLOCKED; 34 unresolved authoritative DDL objects |
| Security and tenancy static review | Existing DEF-001 evidence retained; external Supabase behavior pending |
| Fresh local PostgreSQL replay | BLOCKED; `psql`, `pg_ctl`, and `createdb` unavailable |
| Full repository tests | PASS; 1858 passed, 2 skipped, 0 failures |
| Security/artifact scans | PASS; focused credential-pattern scan on new report, existing DEF-001 scans retained |
| `git diff --check` | PASS |

## Migration failure and recovery contract

The repository documents one-time ordered application. A failed deployment must
stop, restore the database from the pre-deployment backup, and restart from a
new blank or restored checkpoint. The prior partial 0020 execution must not be
continued manually. The manifest is a ledger of the required order and hashes;
it is not permission to skip a failed migration.

## Decision

**BLOCKED**

Concrete blockers:

1. Active application objects still have no authoritative creation DDL.
2. Fresh local PostgreSQL certification of 0020-0023 and the complete chain is
   unavailable in the current environment.
3. Full local PostgreSQL replay remains unavailable, so the corrected chain is
   not yet execution-certified.

External Supabase certification remains pending. No staging project, external
system, commit, or push was performed.
