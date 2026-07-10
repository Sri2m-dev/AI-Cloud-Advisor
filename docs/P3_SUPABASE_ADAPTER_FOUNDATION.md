# P3.13 Supabase PostgreSQL Adapter Foundation

## Purpose

P3.13 introduces the first production persistence adapter boundary for the Nexora Data Fabric. The scope is intentionally narrow: canonical enterprise entities only, backed by reviewed Supabase PostgreSQL migration files and a server-side adapter package.

This phase does not wire persistence into dashboards, connectors, schedulers, Knowledge Graph flows, or runtime services.

## Package Boundary

The adapter lives under `data_fabric/adapters/supabase/` and is isolated from product runtime paths.

Implemented boundaries:

- `DataFabricDatabaseConfig` validates server-side Supabase connection settings and redacts the service role key in representations.
- `SupabaseDataFabricClient` wraps the Supabase client, schema-qualified table access, RPC calls, retries, and error normalization.
- `SupabaseEntityRepository` implements the canonical entity repository slice.
- `SupabaseDataFabricUnitOfWork` defines an explicit transaction boundary placeholder without pretending REST calls are multi-statement transactions.
- `SupabaseAdapterHealthCheck` provides an adapter-local health check hook.

## Migration Framework

Migration files are stored in `migrations/data_fabric/` and are not executed automatically at application startup.

Initial migrations:

- `0001_create_data_fabric_schema.sql` creates the dedicated `data_fabric` schema.
- `0002_create_enterprise_entities.sql` creates the canonical entity current-state table, constraints, tenant indexes, and RLS enablement.
- `0003_create_entity_update_rpc.sql` creates an atomic update function with tenant filters and optimistic revision checks.

Migration execution remains an explicit operator or deployment step for a later reviewed phase.

## Canonical Entity Store

`data_fabric.enterprise_entities` is the authoritative current-state store for canonical entities.

Key design points:

- `id` remains a text identifier to match the P3 contract boundary.
- `(organization_id, tenant_id, canonical_id)` is unique.
- `(organization_id, tenant_id, source_system, source_identifier)` is unique.
- `active`, `deactivated_at`, and `deactivated_by` implement soft deletion.
- `revision` supports optimistic concurrency.
- `confidence_score` and `quality_score` are stored as 0-100 numeric values while contracts expose 0-1 scores.
- `metadata` and `tags` use JSONB for flexible contract extension.

## Repository Methods

The first repository slice implements:

- `add`
- `get`
- `find_by_canonical_id`
- `find_by_source_identity`
- `search`
- `list_entities`
- `update`
- `deactivate`
- `exists`
- `count`

Every read and update path carries explicit organization and tenant filters.

## Optimistic Concurrency

Updates call `data_fabric.data_fabric_update_enterprise_entity` with:

- entity ID
- organization ID
- tenant ID
- expected revision
- replacement entity payload

The function updates only when the tenant scope and expected revision match. A stale revision or missing entity returns no row and the adapter raises `SupabaseAdapterConflictError`.

## RLS Strategy

The entity table enables row-level security immediately. No anonymous access policy is created in this phase. Server-side service-role usage remains confined to the adapter boundary and repository methods still apply tenant filters explicitly.

Future persistence phases must add reviewed RLS policies for authenticated tenant-bound execution before any client-facing runtime integration.

## Secrets Strategy

The adapter requires a server-side service role key but does not hardcode credentials. Configuration must be supplied from secure server environment or secret storage in a future runtime wiring phase.

The service role key must never be exposed to dashboards, browser code, connector payloads, or client-side execution paths.

## Error Handling

Supabase errors are normalized into adapter exceptions:

- configuration errors use `SupabaseAdapterConfigurationError`
- operation errors use `SupabaseAdapterOperationError`
- stale revisions use `SupabaseAdapterConflictError`

## Tests

P3.13 adds structural and unit tests with a fake Supabase client. Integration tests are present but skip unless an explicit safe test environment is configured.

The test scope verifies package isolation, tenant filtering, score mapping, duplicate source/canonical lookup behavior, optimistic concurrency, soft deletion, retry/error normalization, and no automatic migration execution.

## Remaining Conditions

P3.13 is still not a complete persistence rollout. The following remain deferred:

- migration runner
- production RLS policy implementation
- repository adapters for relationships, identity, lineage, provenance, quality, versioning, semantic, ontology, temporal history, and idempotency
- transaction and idempotency repositories
- runtime service wiring
- dashboards and connector integration
- Knowledge Graph integration

## Decision

P3.13 is **GO WITH CONDITIONS** for review and merge as a limited canonical entity adapter foundation. It is **not** approval to enable production persistence in the live product path.
