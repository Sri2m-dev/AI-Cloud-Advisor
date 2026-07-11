# P3 Persistence Readiness Checklist

| Area | Status | Notes |
| --- | --- | --- |
| Contract stability | PASS WITH CONDITIONS | P3 domain, orchestration, and persistence contracts remain stable; P3.12 adds adapter decision docs only. |
| Repository boundaries | PASS WITH CONDITIONS | Repository interfaces distinguish mutable, append-only, temporal, lookup/mapping, and idempotency concerns. |
| Mapping strategy | PASS WITH CONDITIONS | Domain-to-persistence mappers preserve tenant context, normalize datetimes, and reject unsupported schema versions. |
| Tenant isolation | PASS WITH CONDITIONS | P3.13 enables RLS on the entity table and adapter queries apply explicit organization/tenant filters; production RLS policies remain future reviewed work. |
| Identifier strategy | PASS WITH CONDITIONS | P3.13 adds tenant-scoped canonical/source uniqueness constraints for enterprise entities; other aggregate constraints remain future work. |
| Versioning semantics | PASS WITH CONDITIONS | P3.14 adds append-only entity version storage with tenant-scoped entity/version uniqueness and mutation-prevention triggers. |
| Serialization | PASS WITH CONDITIONS | Repository adapters must use deterministic serialization for JSONB payloads and payload hashes. |
| Transaction boundaries | PASS WITH CONDITIONS | P3.15B adds reviewed Supabase RPC boundaries for atomic canonical entity and relationship write bundles; runtime consumers remain deferred. |
| Idempotency | PASS WITH CONDITIONS | P3.15B completes idempotency inside the same database transaction after current-state and append-only writes succeed. |
| Optimistic concurrency | PASS WITH CONDITIONS | P3.15B entity and relationship update/deactivate bundles require tenant-filtered expected-revision checks and increment revision once. |
| Soft deletion | PASS WITH CONDITIONS | P3.13 entity schema and repository include active, deactivated_at, and deactivated_by fields. |
| Append-only history | PASS WITH CONDITIONS | P3.14 adds append-only version, lineage, and provenance tables with repository-level update rejection and database mutation-prevention triggers. |
| Adapter compliance | PASS WITH CONDITIONS | P3.14 extends fake-client coverage to relationships, versions, lineage, and provenance; full live compliance remains gated by safe integration configuration. |
| Adapter technology decision | PASS WITH CONDITIONS | Supabase PostgreSQL selected as first production adapter target. Direct PostgreSQL remains fallback; SQLite deferred. |
| Migration strategy | PASS WITH CONDITIONS | P3.14 adds reviewed relationship/history migrations under `migrations/data_fabric/`; no automatic startup execution is approved. |
| Test strategy | PASS WITH CONDITIONS | Local, CI, integration, migration, tenant, and transaction test strategy is documented. |
| Operational readiness | PASS WITH CONDITIONS | Observability, retries, timeouts, secrets, backup, and recovery expectations are documented. |
| Runtime integration | DEFERRED | No dashboard, connector, scheduler, Knowledge Graph, service, or runtime wiring is approved yet. |

## Decision

P3.15B keeps persistence readiness at **GO WITH CONDITIONS** for a controlled Supabase atomic canonical-write boundary.

Still blocked until future review and certification: migration runner, production RLS policies, ORM models if needed, live integration validation against a disposable Supabase environment, runtime wiring, dashboards, connectors, schedulers, services, and Knowledge Graph integration.

## P3.15A Update

- Quality assessments are append-only with database mutation-prevention triggers.
- Ontology and semantic mappings use tenant-filtered optimistic-concurrency RPCs.
- Idempotency transitions use explicit atomic RPCs.
- Runtime wiring remains disabled.

## P3.15B Update

- Atomic current-state plus history writes are now represented by one RPC per entity or relationship bundle.
- The transaction boundary is PostgreSQL, not Python-side sequential REST calls.
- Idempotency completion occurs last inside the same RPC transaction.
- Rollback behavior relies on unhandled PostgreSQL exceptions; failed bundles do not leave completed idempotency records or partial append-only rows.
- Optimistic concurrency is enforced by tenant and revision predicates on update/deactivate operations.
- Adapter error mapping routes revision, tenant, idempotency, validation, and transaction failures to stable Data Fabric error types.
- Runtime integration readiness remains **DEFERRED** pending a P3 persistence certification checkpoint and live safe-environment validation.
