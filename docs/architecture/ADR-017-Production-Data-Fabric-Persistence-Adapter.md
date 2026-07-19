# ADR-017: Production Data Fabric Persistence Adapter

Status: Accepted — P3 foundation implemented and validated
Date: 2026-07-10
Program: P3 Enterprise Data Fabric & Intelligence Platform

## Context

P3.11 introduced persistence-facing repository contracts, mappers, in-memory compliance adapters, and reusable compliance suites. The next decision is the first production persistence adapter target. The repository already contains extensive Supabase usage through `services.supabase_client`, Supabase environment variables, Supabase-facing repositories, and a `supabase/` project directory.

This ADR is architecture only. It does not create migrations, database clients, ORM models, adapter implementation, environment-variable changes, runtime wiring, dashboards, connector changes, schedulers, or Knowledge Graph integration.

## Decision

Select **Supabase PostgreSQL** as the first production Data Fabric persistence adapter target.

The adapter should be implemented as a Data Fabric repository adapter package in a later phase, behind the P3.11 repository contracts and compliance suites. Direct PostgreSQL remains the portability fallback. SQLite is deferred to optional local reference testing only.

## Alternatives Considered

| Option | Decision | Rationale |
| --- | --- | --- |
| PostgreSQL directly | Deferred | Strong transaction and SQL fit, but does not align as tightly with current Nexora Supabase usage and would duplicate connection/secrets patterns. |
| Supabase PostgreSQL | Selected | Aligns with existing platform infrastructure, Postgres semantics, JSONB, indexing, transactions, RLS policy model, and current operational direction. |
| SQLite reference adapter | Deferred | Useful for local tests but insufficient for tenant isolation, production concurrency, RLS, and append-only history at Nexora scale. |
| Another relational store | Rejected for first adapter | No repo evidence or current operational need justifies adding another database family. |

## Required Adapter Boundaries

Future adapter code must live behind Data Fabric persistence contracts, likely under a dedicated adapter package such as `data_fabric/persistence_adapters/supabase_postgres/` or an equivalent reviewed boundary. Domain contracts must not import adapter code.

## Client Strategy

The first implementation should prefer the platform-approved Supabase/PostgREST client path for consistency, while documenting where direct SQL/RPC may be required for transactions, concurrency, and migration-controlled operations.

## Tenant Isolation

Tenant isolation must use both application-level `TenantContext` enforcement and database-level policy. Supabase Row Level Security or equivalent Postgres policy must be part of the migration design before runtime writes are enabled.

## Transaction Strategy

Multi-repository writes must remain orchestration-owned. The adapter must expose a transaction boundary compatible with P3.11 `PersistenceUnitOfWork`. If a PostgREST path cannot express a required transaction safely, an approved RPC or direct Postgres transaction path must be designed before implementation.

## Concurrency Strategy

Mutable current-state tables must enforce optimistic concurrency with `row_version` or an equivalent revision column. Stale updates must map to `DataFabricConflictError` or a persistence subtype.

## JSON And Schema Strategy

Use normalized columns for tenant keys, identifiers, types, source identifiers, timestamps, scores, version numbers, active flags, and row versions. Use JSONB for deterministic payloads, metadata, quality dimensions, lineage metadata, provenance metadata, and explanations.

## Consequences

Choosing Supabase PostgreSQL aligns the Data Fabric with existing Nexora infrastructure and keeps production scale, tenant isolation, JSONB, and operational observability within the current platform direction. The tradeoff is that transaction semantics must be designed carefully around Supabase client capabilities before any production adapter code is approved.

## Decision Status

**GO WITH CONDITIONS** for Supabase PostgreSQL adapter design and later limited implementation.

Conditions:

- migration design must be reviewed before migration files are created
- adapter package boundary must be reviewed before code
- compliance suites must pass before runtime wiring
- RLS/tenant policy must be part of implementation readiness
- no dashboard, connector, scheduler, Knowledge Graph, or runtime integration in the first adapter implementation
