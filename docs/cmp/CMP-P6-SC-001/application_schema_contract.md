# CMP-P6-SC-001 - Nexora v1 Current Application Schema Contract

**Status: BLOCKED_V1_SCHEMA_CONTRACT**

This document is new v1 contract work. It is not historical recovery and does
not claim that the old development database has been reconstructed.

## Tenant contract

The existing public application baseline uses `public.organizations.id` as the
organization identity and `public.users.org_id` as the user relationship. The
current application also uses text `org_id` and `tenant_id` on report and
financial compatibility paths. No second tenant identity is introduced here.

For every new tenant-sensitive object, the contract is not complete until the
current caller proves the exact key type, nullability, and cross-tenant policy.
The existing five-table bootstrap remains the only public DDL promoted as
certified authority at this checkpoint.

## Evidence rules

- E1: explicitly required by current SQL/query code.
- E2: explicitly required by a current Python model/domain contract.
- E3: explicitly required by a current test.
- E4: required by a proven relationship between E1-E3 contracts.
- E5: convenience or speculation; prohibited.

The matrix below records current disposition and evidence gaps. It does not
promote inferred columns, keys, indexes, views, or RPCs into DDL.

## 34-object disposition

The source matrix currently contains **8**, not 9, `V1_REQUIRED` rows. The
SC-001 report's count of 9 is inconsistent with its own disposition table.
`approval_audit` is not one of the DEF-003/004 unresolved objects and is not
promoted into this list merely to repair the count. SC-002 must resolve this
count discrepancy before claiming zero required dependencies.

| Object | Disposition | Current evidence | Contract state |
| --- | --- | --- | --- |
| `alert_executions` | LEGACY_UNREACHABLE | No table query; alert route refers to an RPC-shaped name | No DDL |
| `application_registry` | V1_REQUIRED | Current repositories select `app_code`, `app_name`, business ownership, criticality, cloud provider, cost center, `active`, and `allocation_enabled` | PK, tenant key, uniqueness, and write contract unresolved |
| `application_spend_mapping` | V1_REQUIRED | Current code selects `spend_application_name`, `registry_app_name` and inserts mapping rows | PK, tenant key, uniqueness, and foreign-key contract unresolved |
| `approval_history` | V1_REQUIRED | Approval repository selects by `approval_request_id`, orders by `created_at`, and inserts stage transition fields | PK, tenant key, retention and policy contract unresolved |
| `approval_queue` | V1_OPTIONAL | Current durable approval path uses `approval_requests`; historical SQL only alters this name | Base table authority unresolved; not promoted |
| `approval_requests` | V1_REQUIRED | Current code filters `status`, `current_approver_role`, orders by `created_at`, reads SLA/workflow fields, updates by `id` | Complete insert, key, tenant, and policy contract unresolved |
| `cloud_connections` | V1_OPTIONAL | Current page references the object, but no complete repository write/query contract was established | Schema and credential boundary unresolved |
| `connector_certification` | V1_OPTIONAL | Repository stores in memory by default; Supabase persistence requires opt-in env flag | Optional persistence contract unresolved |
| `connector_credential_vault` | V1_OPTIONAL | Repository stores credential references in memory by default; persistence is opt-in | Secret-reference schema and policy unresolved |
| `connector_quality_event` | V1_OPTIONAL | Repository stores events in memory by default; persistence is opt-in | Optional persistence contract unresolved |
| `connector_sync_run` | V1_OPTIONAL | Repository stores runs in memory by default; persistence is opt-in | Optional persistence contract unresolved |
| `cost_uploads` | V1_OPTIONAL | Page references the table, but no complete current write/read contract was established | Schema and data-retention contract unresolved |
| `enterprise_connector_registry` | V1_OPTIONAL | Repository memory store; persistence is opt-in and upserts by organization/name | Optional persistence contract unresolved |
| `enterprise_cost_attribution` | V1_OPTIONAL | Service references the object as a compatibility data source | Canonical authority and output shape unresolved |
| `enterprise_data_fabric` | V1_OPTIONAL | Connector repository memory store; persistence is opt-in | Must not duplicate `data_fabric` authority |
| `kpi_spend_by_cloud` | V1_OPTIONAL | Current utilities read the name; historical migration only alters it with `IF EXISTS` | External producer and output contract unresolved |
| `kpi_top_services` | V1_OPTIONAL | Current utilities read the name; historical migration only alters it with `IF EXISTS` | External producer and output contract unresolved |
| `kpi_total_cloud_spend` | V1_OPTIONAL | Current utilities read the name; historical migration only alters it with `IF EXISTS` | External producer and output contract unresolved |
| `mart_application_spend` | V1_REQUIRED | Current repositories select `*` and use application spend results | Output columns, authority, tenant key, and producer unresolved |
| `mart_cost_anomalies` | V1_OPTIONAL | Current cost/leadership paths select `*`; historical executive view references the name | Output shape and canonical P1 authority unresolved |
| `mart_enterprise_forecast` | V1_OPTIONAL | Reports/cost paths select the name | Output shape and canonical financial authority unresolved |
| `mart_enterprise_spend` | V1_REQUIRED | Cost intelligence selects one row from the name | Output shape and canonical P1 authority unresolved |
| `mart_enterprise_spend_v2` | V1_REQUIRED | Current dashboard and guarded-query tests reference the name | Output shape and canonical P1 authority unresolved |
| `mart_optimization_opportunities` | V1_OPTIONAL | Current paths select `*` and order by `total_cost` | Output shape and canonical P2 authority unresolved |
| `mart_service_classification` | V1_OPTIONAL | Service explorer references the name | Output shape and producer unresolved |
| `notification_queue` | V1_OPTIONAL | Escalation service references the name | Insert/update and delivery contract unresolved |
| `platform_health_history` | V1_OPTIONAL | Documentation/reference only in current reachability review | No active query contract established |
| `platform_health_snapshot` | V1_OPTIONAL | Documentation/reference only in current reachability review | No active query contract established |
| `platform_operations_log` | V1_OPTIONAL | Documentation/reference only in current reachability review | No active query contract established |
| `refresh_kpis` | V1_OPTIONAL | Background job attempts an RPC call with failure handling | Arguments, return shape, and canonical authority unresolved |
| `technology_inventory` | V1_REQUIRED | Current connector and technology paths read and upsert by technology name with organization context | Full columns, key, tenant policy, and canonical projection contract unresolved |
| `vw_inactive_saas_users` | LEGACY_UNREACHABLE | Connector metadata names it; no current select contract established | No DDL |
| `vw_saas_renewal_risk` | LEGACY_UNREACHABLE | No current query site established | No DDL |
| `vw_vendor_spend` | LEGACY_UNREACHABLE | Legacy table set includes the name, but no current production query contract established | No DDL |

## Current authority boundaries

- `organizations`, `users`, `clients`, `recommendations`, and
  `report_history` remain the existing public baseline authority.
- Data Fabric remains the canonical enterprise entity, relationship, source
  fact, and stewardship authority. No public compatibility table may become a
  second canonical graph.
- Existing P1/P2 financial authorities remain canonical. No mart/KPI table is
  promoted without an evidenced output contract and authority mapping.
- Connector repository persistence is optional by environment flag and does not
  justify adding speculative durable tables to the blank bootstrap.

## Blocking gaps

The contract cannot yet produce a complete authoritative bootstrap because the
following active objects lack E1-E4 evidence for required keys, complete
columns, or authority boundaries: `application_registry`,
`application_spend_mapping`, `approval_history`, `approval_requests`,
`mart_application_spend`, `mart_enterprise_spend`, `mart_enterprise_spend_v2`,
and `technology_inventory`. The optional financial and integration objects
also lack enough evidence to define safe compatibility projections.

No E5 fields, speculative foreign keys, synthetic defaults, guessed views, or
general-purpose RPCs were added. This is therefore a bounded contract result,
not a staging-ready schema.
