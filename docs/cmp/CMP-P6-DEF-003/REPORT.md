# CMP-P6-DEF-003 - Historical Public Schema Recovery

**Status: BLOCKED_SCHEMA_RECOVERY**

## Scope and preservation

This was a read-only repository archaeology checkpoint. Existing DEF-001 and
DEF-002 work was preserved. No checkout, reset, fetch, push, commit, external
Supabase access, staging creation, AWS/Azure access, or schema invention was
performed.

The complete matrix is in
`docs/cmp/CMP-P6-DEF-003/recovery_matrix.json`.

## Original unresolved set

The current DEF-001 audit contains 34 unresolved active public object names:

`alert_executions`, `application_registry`, `application_spend_mapping`,
`approval_history`, `approval_queue`, `approval_requests`, `cloud_connections`,
`connector_certification`, `connector_credential_vault`,
`connector_quality_event`, `connector_sync_run`, `cost_uploads`,
`enterprise_connector_registry`, `enterprise_cost_attribution`,
`enterprise_data_fabric`, `kpi_spend_by_cloud`, `kpi_top_services`,
`kpi_total_cloud_spend`, `mart_application_spend`, `mart_cost_anomalies`,
`mart_enterprise_forecast`, `mart_enterprise_spend`, `mart_enterprise_spend_v2`,
`mart_optimization_opportunities`, `mart_service_classification`,
`notification_queue`, `platform_health_history`, `platform_health_snapshot`,
`platform_operations_log`, `refresh_kpis`, `technology_inventory`,
`vw_inactive_saas_users`, `vw_saas_renewal_risk`, and `vw_vendor_spend`.

The matrix records each object's expected type, current application operations,
known historical evidence, source grade, and decision. The application calls
remain active evidence; mocked tests were not used to dismiss them.

## Historical search performed

The search covered current and untracked repository-relevant SQL, schema,
documentation, backups, tags, local branches, and remote-tracking refs. Safe
Git commands included `git log --all -S`, `git log --all -G`, `git grep` against
historical trees, and `git show`. The worktree was never replaced by a
historical checkout.

Important refs inspected:

- `v2-executive-dashboard-complete` at
  `cf1e8a1e5e4e0f4a99752a2522414467aa32e360`
- `v4.0-enterprise-connector-platform` at
  `8fcd1aee9f24d2f533b89f6cc54b6296502a3a77`
- `main` at
  `715ae97a902b84adaf7b6493801b904ef99d17f3`
- matching historical commit `66b2941b5ed7710857c4fe1af58cba4ddf2cfea0`

The history search found useful adjacent evidence:

- `supabase/approval_workflow.sql` alters `approval_queue` and creates
  `approval_audit`; it does not create `approval_requests` or
  `approval_history`.
- `supabase/mart_executive_summary_view.sql` creates
  `mart_executive_summary` but only references `mart_cost_anomalies` and
  `mart_optimization_opportunities`; it does not create those objects.
- `supabase/migration_standardize_org_tenant_account.sql` uses
  `ALTER TABLE IF EXISTS` for KPI/mart names, proving pre-existence was
  assumed, not establishing their creation DDL.
- `supabase/connector_tenancy.sql` alters and updates `technology_inventory`
  but does not create it.
- Historical connector files create differently named
  `enterprise_connector_*` objects. Name similarity is insufficient to treat
  them as aliases for `connector_*` or `enterprise_connector_registry`.
- Historical backups contain other mart views and the five-table baseline, but
  no authoritative CREATE for the 34 exact active names. Data-bearing dumps
  were not replayed or copied into current evidence.
- `mart_kpi_table_schemas.md` is documentation with example columns and
  explicitly says to adjust for the warehouse; it is Grade D, not executable
  DDL.

Result: no Grade A, B, or C creation DDL was established for any of the 34
exact unresolved names. Adjacent or ALTER-only evidence was retained in the
matrix and did not become bootstrap input.

## Recovery result

| Result | Count |
| --- | ---: |
| Original unresolved | 34 |
| Recoverable authoritative | 0 |
| Recoverable with review | 0 |
| Superseded, not required | 0 |
| Proven dead reference | 0 |
| Still unresolved | 34 |

No object was marked `DEAD_REFERENCE`: each has reachable repository references
or insufficient evidence to prove that it is absent from production, startup,
worker, Executive, Ask, or migration paths. No active code was deleted.

No bootstrap changes were made. This is intentional: the historical search
recovered assumptions and adjacent objects, not safe current contracts.

## 0020 status

The DEF-002 source correction remains present and uncommitted:
`IF NOT CASE ... END THEN` became `IF NOT (CASE ... END) THEN`.
The focused stewardship regression and prior full repository run remain green,
but PostgreSQL execution certification is still pending.

## PostgreSQL tooling investigation

A safe local replay option is available now: native PostgreSQL 18 is installed
under `C:\Program Files\PostgreSQL\18`, and the PostgreSQL 14 installation is
also present. `docker.exe` and `supabase.exe` are installed. Docker Desktop is
installed but its daemon is unavailable because Docker Desktop is stopped; WSL
only reports the stopped `docker-desktop` distribution. No software was
installed and no database process was started in this checkpoint.

Recommended next certification path: start a disposable native PostgreSQL 18
instance bound to loopback on a fresh data directory, apply the authoritative
sequence from zero, and shut it down after evidence capture. Use Docker only if
its daemon is intentionally started later. Do not use a remote Supabase project
for this local checkpoint.

## Local artifacts

The repository contains historical SQL dumps, `backups/schema_v1.sql`, the
existing schema-only bootstrap, and a local SQLite file `cloud_advisor.db`.
Historical dumps may contain data and were treated as evidence only. No client
rows, credentials, or secret values were extracted. The prior `.tmp/def001`
PostgreSQL data directory is not a running server and was not reused.

## Validation

Focused validation from DEF-002 remains green: the bootstrap/stewardship
regressions passed, and the prior full repository run passed `1858` tests with
`2` skips and `0` failures. This read-only checkpoint added no runtime code or
DDL, so no new product test was required. The recovery matrix was generated as
JSON and contains no secret material. `git diff --check` remains the required
final worktree check before release.

## Recommendation

**BLOCKED_SCHEMA_RECOVERY**

The next checkpoint should either obtain authoritative historical/external DDL
for the exact 34 objects or explicitly retire the reachable application
contracts through a separately authorized product decision. After that, rerun
from a new empty PostgreSQL 18 database and certify Data Fabric 0001-0023.

Commit: **NO**
Push: **NO**
