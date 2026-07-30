# PVT-003C.1 Enterprise Financial Data Fabric — Implementation Trace

## Baseline

- Branch: `feature/pvt-003c-cur-activation-dashboard`
- Preserved discovery commit: `b4853e2437ac59388527ce06a9e0befb47774ef4`
- Validated ingestion commit: `df9c6a6ccc1614c1db3077f9fe7429059949df73`
- Authorized environment: AI-Cloud-Advisor-Dev (`iafrrtmvvqmuksvprrsj`) only
- Validated CUR organization: `71cf875a-2103-47a0-8886-41a97c5750ec`
- Existing local-development organization: `bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c`

The worktree was clean at the baseline. No Production-named credentials were
present. The feature branch did not yet have a remote tracking branch.

## Discovery

The authenticated Streamlit session exposes an organization identifier, but
does not validate it as a UUID, resolve its name, or bind it to a reusable
financial-service contract. Local development login assigns its seeded users
to `bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c`. That identifier must not be replaced
or silently rewritten to expose the real CUR tenant.

The existing `data_fabric.foundation.TenantContext` is the canonical
organization/tenant persistence primitive. It remains unchanged. An
authenticated-session adapter will add user identity, role, organization name,
and authorization claims, then expose the existing Data Fabric context to
repositories.

The CIO financial flow currently reaches legacy, unscoped sources through:

`pages/cio_dashboard.py`
→ `CIOWorkspaceService`
→ `CioDashboardCertificationService`
→ `TechnologySpendService` / `TechnologySpendRepository`
and `EnterpriseFinancialModel`.

Those legacy paths use unfiltered financial reads and tenant-agnostic
five-minute caches. The dashboard does not consume `cloud_cost_fact`,
`cloud_cost_import`, or `cloud_cost_reconciliation`. Quarantined CUR facts are
therefore absent from technology spend and appear as zero.

## Authorized architecture

1. `AuthenticatedTenantContext` validates authenticated session identity,
   organization UUID, resolved organization name, normalized role, and
   membership-derived authorization claims.
2. `EnterpriseFinancialPosture` is an immutable, Decimal-preserving,
   provider-neutral contract with explicit ingestion, spend, governance, and
   reconciliation semantics.
3. Tenant-scoped canonical repositories call guarded database aggregation
   functions. No repository offers an unfiltered financial method.
4. `EnterpriseSpendService` accepts only an authenticated tenant context and
   returns the canonical posture, distributions, import history, and account
   readiness.
5. Database aggregation functions are additive, use a fixed `search_path`,
   validate the caller against `public.users`, and grant execution only to
   `authenticated` and `service_role`.
6. Consumer caches include organization, tenant, authorization scope, period,
   currency, and contract version. Missing context returns a safe unavailable
   state; it never falls back to all organizations.
7. CIO, Executive, Enterprise Spend, and Import History consumers use the
   canonical service or a tenant-required compatibility adapter. Legacy marts
   remain in place for later deprecation and may supply only explicitly
   classified non-cloud data.

## Development tenant-alignment decision

The local demo organization is treated as a legitimate separate tenant until
DEV membership inspection proves otherwise. It will not be overwritten.
Real-CUR UI validation must use a separate authenticated test user, or an
explicit additional membership supported by an approved membership model.
No membership or account mapping is changed in this implementation baseline.

## Consumer inventory

| Consumer | Current source | Scope/cache risk | PVT-003C.1 decision |
|---|---|---|---|
| CIO Dashboard | technology spend service, executive marts, unified cloud costs | unscoped reads and global cache | migrate cloud posture now |
| Executive Dashboard | executive certification/service and marts | duplicated/unscoped financial calculations | migrate cloud posture now |
| Enterprise/Technology Spend | technology spend repository and legacy marts | cloud overlap/double-count risk | compatibility adapter; canonical cloud only |
| Import History | no governed page | absent | add tenant-safe read-only page |
| Reports | report services and legacy marts | inventory required | compatibility adapter later; disable unscoped cloud sections |
| Optimization / Savings | cost intelligence and legacy cloud sources | possible cloud overlap | retain recommendations, migrate financial baseline later |
| Cost Explorer / Forecasts | legacy cloud costs | unscoped and non-canonical | deprecate later; no new bypass |
| AI recommendations | downstream legacy summaries | inherited provenance risk | consume canonical posture in later package |
| Business allocation | enterprise financial model | tenant-agnostic cache | canonical posture now; allocation integration later |
| Governance / Exports | mixed repositories | tenant scope varies | require tenant adapter before CUR exposure |

## Legacy-source decisions

| Source | Decision | Replacement / prerequisite |
|---|---|---|
| `mart_enterprise_spend_v2` | retain for explicitly non-cloud categories; deprecate later | canonical compatibility adapter and consumer migration |
| `mart_executive_summary` | migrate cloud metrics now; deprecate later | `EnterpriseSpendService` |
| `unified_cloud_costs` | unsafe for canonical cloud totals; disable in migrated financial sections | canonical CUR aggregation |
| legacy cloud financial repositories | compatibility adapter only | tenant-scoped canonical repositories |
| unscoped global financial caches | disable immediately in migrated paths | tenant-aware cache keys and invalidation |

Raw CUR evidence remains in persistence and is not returned by dashboard
repositories.

## Browser-continuation consumer safety closure

The shared Supabase application client now treats the following legacy
financial sources as protected:

- `mart_enterprise_spend`
- `mart_enterprise_spend_v2`
- `mart_executive_summary`
- `unified_cloud_costs`
- `mart_enterprise_forecast`
- `mart_budget_vs_actual`
- `recommendations`
- `cost_allocations`
- `application_cost_allocations`
- application-spend mapping and cost-usage tables
- cost trend, forecast, anomaly, optimization, savings, and recommendation marts
- managed-service, SaaS, license, and vendor-spend compatibility sources

An explicit `organization_id`, `org_id`, or `tenant_id` equality filter is
required before a protected query executes. Tenant-scoped compatibility reads
continue to RLS. An unscoped legacy read returns an empty result, safely
disabling that financial section. An unscoped write is rejected. This closes
active unfiltered reads in Finance, Technology Spend, reports, legacy Executive
v2, forecasting, allocation, digital-twin, operations, analytics, and
recommendation consumers without deleting their legacy marts.

The CIO, Executive, Enterprise Spend, and Import History pages remain migrated
to `EnterpriseSpendService` for canonical cloud financial posture. Where
Enterprise Spend retains legacy SaaS, MSP, license, forecast, budget, or
recommendation categories, those compatibility reads carry the authenticated
organization scope and do not reuse legacy cloud totals.

`Default Org` is the authoritative current DEV organization name resolved from
the authenticated CUR tenant. Renaming it is a later administrative data
change, not a dashboard override.
