# P3 Persistence Readiness Checklist

| Area | Status | Notes |
| --- | --- | --- |
| Contract stability | PASS WITH CONDITIONS | P3 domain, orchestration, and persistence contracts remain stable; P3.12 adds adapter decision docs only. |
| Repository boundaries | PASS WITH CONDITIONS | Repository interfaces distinguish mutable, append-only, temporal, lookup/mapping, and idempotency concerns. |
| Mapping strategy | PASS WITH CONDITIONS | Domain-to-persistence mappers preserve tenant context, normalize datetimes, and reject unsupported schema versions. |
| Tenant isolation | PASS WITH CONDITIONS | P3.13 enables RLS on the entity table and adapter queries apply explicit organization/tenant filters; production RLS policies remain future reviewed work. |
| Identifier strategy | PASS WITH CONDITIONS | P3.13 adds tenant-scoped canonical/source uniqueness constraints for enterprise entities; other aggregate constraints remain future work. |
| Versioning semantics | PASS WITH CONDITIONS | Version repository contract is append-only; Supabase PostgreSQL JSONB/indexing supports future durable snapshots. |
| Serialization | PASS WITH CONDITIONS | Repository adapters must use deterministic serialization for JSONB payloads and payload hashes. |
| Transaction boundaries | PASS WITH CONDITIONS | Unit-of-work contracts exist; Supabase transaction/RPC/direct SQL strategy must be finalized before adapter code. |
| Idempotency | PASS WITH CONDITIONS | Idempotency repository semantics exist; durable implementation should be first adapter milestone. |
| Optimistic concurrency | PASS WITH CONDITIONS | P3.13 entity updates use a reviewed RPC with tenant filters and expected-revision compare-and-advance. |
| Soft deletion | PASS WITH CONDITIONS | P3.13 entity schema and repository include active, deactivated_at, and deactivated_by fields. |
| Append-only history | PASS WITH CONDITIONS | Append-only contracts exist; future database adapter must enforce duplicate behavior and immutable updates. |
| Adapter compliance | PASS WITH CONDITIONS | P3.13 adds Supabase entity adapter unit coverage with fake-client behavior; full live compliance remains gated by safe integration configuration. |
| Adapter technology decision | PASS WITH CONDITIONS | Supabase PostgreSQL selected as first production adapter target. Direct PostgreSQL remains fallback; SQLite deferred. |
| Migration strategy | PASS WITH CONDITIONS | P3.13 adds reviewed, non-destructive entity foundation migrations under `migrations/data_fabric/`; no automatic startup execution is approved. |
| Test strategy | PASS WITH CONDITIONS | Local, CI, integration, migration, tenant, and transaction test strategy is documented. |
| Operational readiness | PASS WITH CONDITIONS | Observability, retries, timeouts, secrets, backup, and recovery expectations are documented. |
| Runtime integration | DEFERRED | No dashboard, connector, scheduler, Knowledge Graph, or runtime wiring is approved yet. |

## Decision

P3.13 keeps persistence readiness at **GO WITH CONDITIONS** for a limited Supabase PostgreSQL canonical entity adapter foundation.

Still blocked until future review and merge: migration runner, additional repository adapters, production RLS policies, ORM models if needed, runtime wiring, dashboards, connectors, schedulers, and Knowledge Graph integration.
