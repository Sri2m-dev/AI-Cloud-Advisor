# P3 Production Adapter Decision

## Decision

Selected first production adapter target: **Supabase PostgreSQL**.

Decision status: **GO WITH CONDITIONS** for adapter design and later limited implementation. No adapter implementation is included in P3.12.

## Evaluation Matrix

| Criterion | PostgreSQL Direct | Supabase PostgreSQL | SQLite Reference | Other Relational Store |
| --- | --- | --- | --- | --- |
| Production scalability | High | High | Low | Unknown |
| Tenant isolation | High with custom RLS | High with Supabase/Postgres RLS | Low to medium | Unknown |
| Transactions | Strong | Strong through Postgres; client path needs design | Limited | Unknown |
| Optimistic concurrency | Strong | Strong | Medium | Unknown |
| JSON support | JSONB | JSONB | JSON text/JSON1 variability | Unknown |
| Append-only history | Strong | Strong | Medium | Unknown |
| Temporal queries | Strong | Strong | Medium | Unknown |
| Indexing | Strong | Strong | Limited at scale | Unknown |
| Local development | Medium | Medium with local Supabase or hosted dev | High | Unknown |
| Test automation | High with containers | High with Supabase local/Postgres containers | High | Unknown |
| Migration tooling | Strong | Strong through Supabase migrations/Postgres SQL | Medium | Unknown |
| Deployment complexity | Medium | Medium; aligns with existing stack | Low but non-prod | High/unknown |
| Observability | Strong | Strong with Supabase/Postgres telemetry | Low | Unknown |
| Nexora alignment | Medium | High | Low | Low |

## Why Supabase PostgreSQL

The current repo already uses Supabase as a platform persistence path. Existing files reference `services.supabase_client`, Supabase environment variables, Supabase repositories, and a `supabase/` directory. Selecting Supabase PostgreSQL avoids creating a parallel production database strategy while preserving PostgreSQL capabilities.

## Why Alternatives Are Deferred

Direct PostgreSQL is a strong fallback for portability and transaction-heavy paths, but should not be the first adapter because it bypasses existing Nexora Supabase conventions.

SQLite is useful for local reference tests, but does not satisfy the production tenant isolation, RLS, concurrency, and operational requirements for Data Fabric.

Another relational store is rejected for first adapter because there is no current Nexora infrastructure signal to justify it.

## Implementation Boundary

Future implementation should create an adapter package only after this decision is merged. The adapter must depend on `data_fabric.persistence` contracts and must not be imported by domain contracts.

## Explicit Non-Implementation Statement

P3.12 does not add migrations, clients, ORM models, adapter classes, environment variables, runtime wiring, dashboards, connectors, schedulers, or Knowledge Graph integration.
