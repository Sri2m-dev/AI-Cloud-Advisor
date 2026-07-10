# P3 Persistence Implementation Plan

## Purpose

Define the safe implementation order for Data Fabric persistence after P3.10C is reviewed and merged.

## Decision

P3.10C ends with **GO WITH CONDITIONS** for limited persistence implementation. The approval is limited to repository interfaces, schema migrations, and storage adapters behind orchestration contracts. It does not approve dashboard, connector runtime, scheduler, Supabase UI, or Knowledge Graph wiring.

## Conditions Before Code

- P3.10C docs and ADR-016 must be merged to `main`.
- Repository interfaces must be reviewed before adapter code.
- Migration scripts must be reviewed separately from repository adapters.
- Tenant isolation tests must exist before first adapter merge.
- Idempotency durability tests must exist before ingestion writes are enabled.
- Runtime integration remains blocked until persistence adapters pass focused validation.

## Phase 1: Repository Interfaces

Create interfaces only:

- entity repository
- relationship repository
- version repository
- temporal history repository
- lineage repository
- provenance repository
- quality assessment repository
- semantic concept repository
- semantic mapping repository
- idempotency repository
- transaction audit repository

No adapter code in this phase.

## Phase 2: Migration Blueprint To Concrete Migration

Create reviewed migrations for current-state, immutable, and control tables.

Requirements:

- tenant columns on every tenant-scoped table
- uniqueness constraints
- indexes from schema blueprint
- optimistic concurrency columns on mutable state
- soft delete columns on mutable state
- storage-level tenant policy where supported

## Phase 3: Persistence Adapter Skeleton

Add adapter classes that implement repository interfaces with no runtime wiring.

Requirements:

- deterministic serializer use
- `DataFabricError` mapping
- tenant boundary enforcement
- transaction participation
- no dashboard or connector imports

## Phase 4: Durable Idempotency And Transaction Audit

Implement idempotency repository and transaction audit repository first. Validate repeat request behavior before enabling entity writes.

## Phase 5: Current-State Repositories

Implement entity and relationship current-state repositories with optimistic concurrency and soft delete semantics.

## Phase 6: Immutable History And Evidence

Implement version snapshots, temporal history, lineage, provenance, and quality assessment repositories.

## Phase 7: Semantic Persistence

Implement semantic concept and mapping repositories.

## Phase 8: Orchestration Adapter Integration

Wire repositories into orchestration in an isolated service path. Still no dashboard, connector runtime, scheduler, or Knowledge Graph integration.

## Phase 9: Runtime Readiness Review

Before product wiring, run a review for:

- tenant isolation
- rollback behavior
- idempotency replay
- migration safety
- performance indexes
- failure modes
- observability

## Explicitly Out Of Scope

- dashboard changes
- connector runtime changes
- background jobs
- Knowledge Graph v2 wiring
- direct Supabase client use from product pages
- production data migration execution
