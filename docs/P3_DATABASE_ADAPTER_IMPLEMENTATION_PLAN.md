# P3 Database Adapter Implementation Plan

## Purpose

Define the implementation-ready plan for a future Supabase PostgreSQL Data Fabric adapter without implementing it in P3.12.

## Package Boundary

Future adapter code should live outside domain contracts, for example:

```text
data_fabric/persistence_adapters/supabase_postgres/
```

Expected modules in a later implementation phase:

- client boundary
- row mappers
- repository adapters
- transaction boundary
- error translation
- compliance fixtures

## Phased Implementation Order

1. Adapter package skeleton and no-op imports check.
2. Supabase/Postgres client boundary interface.
3. Entity and relationship current-state repositories.
4. Idempotency repository.
5. Transaction audit repository.
6. Version and temporal history repositories.
7. Lineage and provenance repositories.
8. Quality assessment repository.
9. Semantic concept and semantic mapping repositories.
10. Compliance suite execution against the adapter.
11. Isolated orchestration adapter integration.
12. Runtime integration review.

## Client And Driver Strategy

Prefer the existing Supabase client convention for platform alignment. Use direct Postgres transaction/RPC design only when required for atomic multi-table behavior or concurrency guarantees that cannot be safely expressed through the standard client path.

## Repository Adapter Requirements

- implement P3.11 repository interfaces
- preserve `TenantContext`
- enforce optimistic concurrency
- map storage failures to `DataFabricError` hierarchy
- use deterministic serialization for JSONB payloads
- pass reusable compliance suites
- avoid importing dashboards, connectors, schedulers, or runtime modules

## Transaction Implementation

The adapter must support an orchestration-owned unit of work. Idempotency completion must occur after durable commit. Failed commits must leave no partial current-state/history writes.

## Retry And Timeout Policy

Retries should be limited to transient connection or timeout errors. Conflict, validation, tenant-boundary, and idempotency errors must not be retried silently. Timeouts should be explicit per operation class and documented before implementation.

## Secrets Handling

No new environment variables are added in P3.12. Future implementation must use the existing approved secrets pattern and distinguish local, CI, staging, and production credentials.

## Exit Criteria For First Adapter Merge

- migrations reviewed separately
- repository adapter passes compliance suite
- tenant isolation tests pass
- idempotency tests pass
- no product runtime imports
- rollback behavior documented and tested
