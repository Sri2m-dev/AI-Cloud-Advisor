# WP-005 Implementation Evidence

## Status

- Work package: WP-005 — Canonical coverage and stewardship
- Branch: `feature/wp-005-enterprise-stewardship`
- Baseline: `main` at `219c14445464958a3ef097bcfcfa4d9029622f69`
- Owner: Srikanth Mudaliar
- Local implementation validation: Passed
- Database application and live validation: **Not performed**
- Hosted CI, Program G review, merge, and closure: Pending

## Scope Implemented

- Migration `0019` adds exactly the approved tenant-scoped policy, review-item,
  and immutable audit tables.
- Migration `0020` adds exactly the approved atomic create/transition RPCs.
- `canonical_stewardship` provides immutable authority, freshness, review, and
  coverage models; deterministic policy evaluation; a repository protocol; and
  a tenant-authorized Supabase adapter.
- Focused tests validate migration structure, authority conflicts, freshness,
  coverage reconciliation, replay conflicts, revision collisions, scoped reads,
  and pre-RPC cross-tenant denial.

No existing canonical table, Data Fabric contract, registry contract,
connector, runtime wiring, API, UI, graph, AI service, or migrations `0001–0018`
were modified.

## Migration Security Review

- Mandatory `organization_id` and `tenant_id` on every table.
- UUID primary keys and index-backed tenant replay keys.
- RLS enabled with no anonymous policy.
- Composite audit foreign key includes review, organization, and tenant.
- No cascade delete; audit history is preserved.
- Audit UPDATE and DELETE are rejected by triggers.
- Mutable records require revisions to increase by exactly one.
- Tenant scope, record identities, and creation identity are immutable.
- RPCs use `SECURITY DEFINER` with safe `search_path`.
- RPCs validate tenant scope, authorization state/permission, revision,
  lifecycle edge, idempotency key, and payload hash.
- `PUBLIC` execute is revoked and `service_role` execute is explicit.
- Migrations are manual artifacts and were not executed by application code.

## Local Validation

| Gate | Result |
| --- | --- |
| WP-005 focused tests | 7 passed |
| WP-001–WP-005 combined focused gates | 53 passed |
| Full suite | 373 passed, 5 expected skips, 0 failed |
| P3 non-secret gate | 94 passed, 0 failed |
| Ruff for changed Python | Passed |
| Focused compile | Passed |
| `pip check` | Passed |
| Git whitespace check | Passed |

Known warnings are three existing Pydantic v2 deprecations and local pytest
cache-permission warnings. The five skips remain the approved opt-in Supabase
integrations. No live Supabase or external-system access occurred.

## Architecture-Controlled Commits

- `be3b5111` — Migration 0019 stewardship persistence schema.
- `8aab2928` — Migration 0020 atomic stewardship RPCs.
- `c5fcf5ed` — stewardship models, repository/service boundary, adapter, tests,
  and migration inventory.

## Remaining Gates

WP-005 is not ready to merge or close until:

1. migrations `0019–0020` receive explicit technical review;
2. a hardened, approved non-production target is confirmed;
3. the new migrations are applied only through the controlled manual process;
4. live zero-row, RLS/privilege, tenant-isolation, replay, revision,
   concurrency, lifecycle, idempotency, audit-immutability, and rollback tests
   pass;
5. mutable test records are scoped and cleaned while audit evidence is retained;
6. final hosted CI passes, Program G approves merge, and post-merge CI/CD passes.

No database operation should proceed merely because this document exists.
