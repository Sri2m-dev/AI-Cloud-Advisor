# NEXORA V1 Canonical Bootstrap — Migration Inventory

## Inventory status

The bounded test-only PostgreSQL replay contains **43 inputs** in deterministic
order:

1. `supabase/bootstrap/public_prerequisites.sql` — schema-only five-table
   prerequisite subset.
2. **19** dated migrations under `supabase/migrations/`.
3. **23** migrations under `migrations/data_fabric/`, ordered 0001 through 0023.

The file hashes and exact paths are recorded in
[`migration_manifest.json`](../../cmp/CMP-P6-DEF-001/migration_manifest.json).
The production manifest is
[`bootstrap-manifest.json`](../../../deploy/production/bootstrap-manifest.json);
it now lists all 19 public migrations and remains explicitly blocked and
non-executable.

The local replay completed all 43 inputs, including Data Fabric 0020–0023. This
proves that these files compile and execute in the isolated test harness. It
does **not** make the incomplete application schema deployable.

## PostgreSQL input groups

### Public chain — 19 files

- `202607230001_public_security_reconciliation.sql`
- `202607260001_aws_cur_ingestion_foundation.sql`
- `202607290001_enterprise_financial_data_fabric.sql`
- `202607290002_optimize_enterprise_financial_posture.sql`
- `202607290003_materialize_cloud_financial_projections.sql`
- `202607290004_correct_persisted_fact_posture.sql`
- `202607300001_bound_enterprise_financial_posture.sql`
- `202607310001_add_import_history_billing_period.sql`
- `202607310002_cloud_account_registry.sql`
- `202608080001_fg002_account_resolution.sql`
- `202608090001_p42_enterprise_classification.sql`
- `202608090002_p42_owner_optional_resolution.sql`
- `202608090003_p42_aws_user_tag_normalization.sql`
- `202608090004_p42_inference_persistence_rpc.sql`
- `202608090005_p42_persistence_lock_key.sql`
- `202608090006_p42_batch_account_evidence.sql`
- `202608090007_p42_single_scan_batch_evidence.sql`
- `202610090001_retire_legacy_auth_user_trigger.sql`
- `202610110001_bind_user_profiles_to_auth_uid.sql`

All paths are prefixed by `supabase/migrations/`.

### Data Fabric — 23 files

The exact chain is `migrations/data_fabric/0001_*.sql` through
`migrations/data_fabric/0023_*.sql`, in numeric order. The filenames and
checksums are in the machine-readable manifest. The test run compiled 0020 and
executed 0021–0023; the old 0020 syntax-error report is historical.

### Not part of the PostgreSQL chain

`migrations/universal_evidence/0001_create_lifecycle_state.sql` is an existing
local SQLite lifecycle migration. It is not applied to PostgreSQL or Supabase.
The separate workflow contract
`database/contracts/v1_customer_workflow/001_customer_workflow_postgres.sql`
is applied after the 43-input migration chain only by the synthetic workflow
integration test; it is not counted among the 43 inputs.

## Execution and idempotency boundary

- Replay ran only against disposable local PostgreSQL with synthetic data.
- The local harness supplied test-only Auth schema/functions/roles and a
  temporary migration-owner role. These are not a simulation of hosted GoTrue,
  PostgREST, or Supabase deployment behavior.
- The second-pass skip ledger is test-only. It does not establish a production
  migration runner, production migration history, or general migration
  idempotency.
- The bootstrap manifest remains non-executable; no external migration was
  performed.
- The current SQL inventory includes 252 worktree SQL files. The AST inventory
  finds 29 distinct API object names with no SQL creation definition. See the
  [P6 report](../../cmp/CMP-P6-DEF-001/REPORT.md) for the name-to-caller
  evidence and classification details.

## V1 dependency scope

The bounded synthetic journey directly exercised the existing
`database/contracts/v1_customer_workflow/001_customer_workflow_postgres.sql`
contract after replay. That contract supplies the namespaced workspace, event,
evidence, Ask, decision, approval, and export persistence used by
`CustomerWorkflowService`. The 29 unresolved legacy API names were not called
by that tested service journey.

The inventory therefore distinguishes the following:

- **Required for this migration replay:** the five-table public prerequisite,
  all 19 dated public migrations, and all 23 Data Fabric migrations.
- **Required for the bounded workflow test:** the existing
  `v1_customer_workflow` contract and its configured keys/roles, applied after
  the replay.
- **Candidate deferrals from the bounded journey, not approved scope cuts:**
  - Legacy approval: `approval_requests`, `approval_history`,
    `approval_queue`.
  - Connectors and cloud-cost intake: `cloud_connections`, `cost_uploads`,
    `connector_certification`, `connector_credential_vault`,
    `connector_quality_event`, `connector_sync_run`,
    `enterprise_connector_registry`, `enterprise_cost_attribution`,
    `enterprise_data_fabric`.
  - Alerts and recommendation jobs: `alert_executions`,
    `recommendation_events`, `refresh_kpis`, `notification_queue`.
  - KPI, mart, and reporting: `kpi_spend_by_cloud`, `kpi_top_services`,
    `kpi_total_cloud_spend`, `mart_cost_anomalies`,
    `mart_enterprise_forecast`, `mart_optimization_opportunities`,
    `mart_service_classification`.
  - Platform health: `platform_health_history`,
    `platform_health_snapshot`, `platform_operations_log`.
  - Technology/SaaS views: `vw_inactive_saas_users`,
    `vw_saas_renewal_risk`, `vw_vendor_spend`.

The tested V1 workflow uses its namespaced approval contract instead of the
legacy approval names.

These candidates map to product capabilities outside the exact workflow test,
but their omission from that test does not prove they may be removed from the
commercial V1 application. Product scope and full application startup must be
reviewed before any candidate is formally deferred. The full-bootstrap gate
therefore remains blocked rather than silently treating active callers as
optional.
