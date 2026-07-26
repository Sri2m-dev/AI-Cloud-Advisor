# PVT-003A AWS CUR Persistence Foundation

Status: Engineering complete; review and disposable migration validation pending.
Baseline: `c82cc9faa0996581e7d5808540cd9782428dcce9`
Scope: persistence/security foundation only.

## Added logical objects

| Object | Purpose |
| --- | --- |
| `cloud_cost_import` | Tenant-owned import manifest, source evidence, billing period, file identity, status, correction/supersession |
| `cloud_cost_import_part` | Multipart/chunk checkpoint, retry, and bounded error evidence |
| `cloud_account_mapping` | Authorized payer/member-account ownership and quarantine state |
| `cloud_cost_fact` | Normalized, source-row-identifiable CUR facts with explicit cost/commitment/adjustment semantics |
| `cloud_cost_reconciliation` | Source-to-normalized totals, counts, variance, and reconciliation evidence |

## Security model

- Each object has `organization_id` and `tenant_id`; the foundation intentionally
  requires equality until the platform’s organization/tenant identity model gains
  independently resolvable tenant identifiers.
- RLS is enabled on every new table.
- `anon` and `authenticated` receive no structural or write privileges.
- Authenticated users may read only their own import/history/account-resolution/
  reconciliation metadata, via the certified `users.email → users.org_id` JWT
  resolution pattern.
- Detailed `cloud_cost_fact` rows remain backend/service-only in this foundation.
- No service-role credential or write path is exposed to a browser.

## Reuse and exclusions

The foundation reuses the existing public `organizations` identity, Supabase RLS
pattern, `TenantContext` contract, Data Fabric deterministic-identity concepts,
`unified_cloud_costs` compatibility role, and later `EnterpriseCostAttributionService`
and ADR-002 `EnterpriseFinancialModel` propagation targets.

It does not implement a parser, upload, object storage, background worker,
normalization routine, rollup, attribution change, mart refresh, dashboard change,
or navigation exposure. Those are explicitly deferred to PVT-003B through PVT-003D.

## Deployment boundary

The migration is additive, transactional, idempotent where PostgreSQL permits,
and fail-closed for unsafe CUR-table policies. It has not been run against DEV,
Production, Supabase, or any disposable database in this phase.
