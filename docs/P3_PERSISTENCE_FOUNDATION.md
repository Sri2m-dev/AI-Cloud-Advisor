# P3 Persistence Foundation

## Purpose

P3.11 introduces persistence-facing repository contracts, value models, mapping boundaries, unit-of-work contracts, and in-memory compliance adapters. It does not add SQL migrations, Supabase clients, PostgreSQL, SQLite, ORM models, repository adapters, dashboard wiring, connector runtime changes, schedulers, or Knowledge Graph integration.

## Package Architecture

| Module | Responsibility |
| --- | --- |
| `data_fabric.persistence.models` | Persistence records, concurrency tokens, queries, paging, and operation results. |
| `data_fabric.persistence.interfaces` | Repository contracts by persistence category. |
| `data_fabric.persistence.mappers` | Domain-to-persistence mapping boundaries. |
| `data_fabric.persistence.repositories` | In-memory compliance repositories only. |
| `data_fabric.persistence.unit_of_work` | Persistence unit-of-work and repository provider contracts. |
| `data_fabric.persistence.compliance` | Reusable compliance suites for future adapters. |
| `data_fabric.persistence.exceptions` | Persistence exception types mapped to `DataFabricError` hierarchy. |

## Dependency Rules

Allowed:

```text
data_fabric.persistence -> data_fabric.contracts
data_fabric.persistence -> data_fabric.foundation
data_fabric.persistence -> data_fabric.orchestration models where necessary
```

Forbidden:

```text
data_fabric.contracts -> data_fabric.persistence
```

Domain contracts must remain persistence-agnostic.

## Repository Classification

| Classification | Repositories |
| --- | --- |
| Mutable current state | Entity, Relationship, Identity, Ontology, Semantic Mapping, Idempotency |
| Immutable append-only | Lineage, Provenance, Version, Quality Assessment |
| Temporal history | Temporal History |
| Lookup/mapping | Ontology, Semantic Mapping, Identity |
| Control | Idempotency |

Repositories are tenant-scoped and do not permit cross-tenant aggregation.

## Domain Versus Persistence Boundary

Domain contracts remain the business-facing shape. Persistence records carry storage-facing fields such as `record_id`, tenant keys, timestamps, schema version, metadata, payload, concurrency token, and soft-delete state.

Mappers own conversion between the two worlds. Repository adapters must not mutate domain objects.

## Mapper Lifecycle

Mappers support:

- `domain_to_record`
- `record_to_domain`
- deterministic conversion
- source object immutability
- tenant context preservation
- enum value stability
- UTC datetime normalization
- UUID stability
- metadata defensive copying
- schema version checks
- explicit failure for unsupported schema versions

## Mutable Versus Immutable Records

Mutable records support optimistic concurrency and soft delete. Immutable and append-only records support insertion only. Update attempts against append-only repositories raise explicit immutable-state errors.

## Optimistic Concurrency

Mutable records carry a revision and concurrency token. Update operations require the expected revision. Successful updates advance the revision. Stale updates raise `PersistenceConflictError`.

## Soft Deletion

Mutable current-state repositories deactivate records rather than physically deleting them. Deactivated records are excluded from default reads and searches. `include_inactive=True` is required to return them.

Immutable history is never deleted through these interfaces.

## Tenant Isolation

Every repository method requires or derives tenant context. Cross-tenant lookup returns no result. Cross-tenant mutation raises a tenant-boundary error.

## Transaction Semantics

`InMemoryPersistenceUnitOfWork` demonstrates:

- begin
- staged operations
- commit
- rollback
- repository provider access
- tenant binding
- transaction state
- staged operation count
- failure reason
- no tenant switching during an open transaction

The in-memory implementation uses snapshots to demonstrate atomic commit and rollback behavior.

## Compliance Testing Strategy

Compliance suites validate reusable adapter behavior:

- base repository behavior
- mutable repository behavior
- append-only behavior
- temporal history behavior
- tenant isolation
- transaction behavior

Future PostgreSQL or Supabase adapters should pass the same suite before product wiring.

## Adapter Extension Guide

A future production adapter must:

1. Implement the repository interfaces.
2. Use the persistence mappers.
3. Preserve tenant context on every query and write.
4. Enforce optimistic concurrency in storage.
5. Preserve append-only semantics for history and evidence.
6. Map storage errors to `DataFabricError` types.
7. Pass the reusable compliance suite.
8. Remain unwired from dashboards and connector runtime until separately approved.

## Current Limitations

- No production database adapter exists.
- No migrations exist.
- No Supabase, PostgreSQL, SQLite, or ORM integration exists.
- Compliance repositories are in-memory validation references, not domain registry replacements.
- Runtime integration remains deferred.
