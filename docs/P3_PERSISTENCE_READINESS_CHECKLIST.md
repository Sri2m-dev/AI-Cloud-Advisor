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
| Transaction boundaries | PASS WITH CONDITIONS | P3.14 uses RPC for single-relationship optimistic updates and formally defers multi-repository relationship/history atomic bundles to a future controlled RPC. |
| Idempotency | PASS WITH CONDITIONS | Idempotency repository semantics exist; durable implementation should be first adapter milestone. |
| Optimistic concurrency | PASS WITH CONDITIONS | P3.13 entity updates use a reviewed RPC with tenant filters and expected-revision compare-and-advance. |
| Soft deletion | PASS WITH CONDITIONS | P3.13 entity schema and repository include active, deactivated_at, and deactivated_by fields. |
| Append-only history | PASS WITH CONDITIONS | P3.14 adds append-only version, lineage, and provenance tables with repository-level update rejection and database mutation-prevention triggers. |
| Adapter compliance | PASS WITH CONDITIONS | P3.14 extends fake-client coverage to relationships, versions, lineage, and provenance; full live compliance remains gated by safe integration configuration. |
| Adapter technology decision | PASS WITH CONDITIONS | Supabase PostgreSQL selected as first production adapter target. Direct PostgreSQL remains fallback; SQLite deferred. |
| Migration strategy | PASS WITH CONDITIONS | P3.14 adds reviewed relationship/history migrations under `migrations/data_fabric/`; no automatic startup execution is approved. |
| Test strategy | PASS WITH CONDITIONS | Local, CI, integration, migration, tenant, and transaction test strategy is documented. |
| Operational readiness | PASS WITH CONDITIONS | Observability, retries, timeouts, secrets, backup, and recovery expectations are documented. |
| Runtime integration | DEFERRED | No dashboard, connector, scheduler, Knowledge Graph, or runtime wiring is approved yet. |

## Decision

P3.15A keeps persistence readiness at **GO WITH CONDITIONS** for a limited Supabase governance, semantic, and idempotency adapter slice.

Still blocked until future review and merge: migration runner, production RLS policies, ORM models if needed, P3.15B multi-repository transaction RPC, runtime wiring, dashboards, connectors, schedulers, and Knowledge Graph integration.

## P3.15A Update

- Quality assessments are append-only with database mutation-prevention triggers.
- Ontology and semantic mappings use tenant-filtered optimistic-concurrency RPCs.
- Idempotency transitions use explicit atomic RPCs.
- Runtime wiring remains disabled.
