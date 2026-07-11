# P3.14 Supabase Relationship And Immutable History Adapter

## Purpose

P3.14 extends the Supabase Data Fabric adapter beyond canonical entities into one mutable relationship store and three append-only history stores.

Implemented persistence areas:

- `enterprise_relationships`
- `entity_versions`
- `lineage_events`
- `provenance_records`

Deferred persistence areas:

- quality assessments
- ontology
- semantic mappings
- idempotency
- runtime wiring
- dashboard, connector, scheduler, and Knowledge Graph integration

## Table Architecture

`data_fabric.enterprise_relationships` is a mutable current-state table. It uses tenant-scoped uniqueness for active relationships and optimistic revision checks for updates.

`data_fabric.entity_versions`, `data_fabric.lineage_events`, and `data_fabric.provenance_records` are append-only history tables. They enable RLS, expose no repository update/delete paths, and include database triggers that reject mutation after insert.

No cascade delete is used. P3.14 intentionally avoids foreign keys where they would be incompatible with the current string entity identifier contract and the UUID relationship/history schema requested for this slice.

## Repository Behavior

Mutable relationship repository:

- add
- get
- search
- list relationships
- source lookup
- target lookup
- update
- deactivate
- exists
- count

Append-only version repository:

- append
- get snapshot
- latest by entity
- list entity versions
- payload hash lookup
- exists
- count

Append-only lineage repository:

- append
- get
- list by entity
- list by relationship
- list by correlation
- search
- count

Append-only provenance repository:

- append
- get
- source identity lookup
- list by entity
- list by relationship
- search
- count

All repository methods apply explicit organization and tenant filters.

## Relationship Concurrency

Relationship updates call `data_fabric.data_fabric_update_enterprise_relationship` with relationship ID, organization ID, tenant ID, expected revision, and replacement payload. The RPC updates only when the tenant filters and expected revision match, then increments `revision` in the database.

A stale revision or missing relationship returns no rows and the adapter raises a conflict error.

## Append-Only Enforcement

Version, lineage, and provenance repositories do not expose update or deactivate methods. Calls to the required abstract update method raise an adapter operation error.

Database migrations also register mutation-prevention triggers for update/delete operations on append-only tables.

## History Ordering

Version history is ordered by `version` for entity-specific reads. Lineage and provenance history are ordered by event timestamps: `occurred_at` for lineage and `captured_at` for provenance.

## RLS Strategy

RLS is enabled for all four P3.14 tables. These foundation migrations do not add anonymous access policies. Server-side service-role usage remains confined to the adapter package, and repository methods still apply tenant filters explicitly.

## Transaction Boundary

Supabase REST calls do not provide transparent multi-statement atomicity. P3.14 supports single-repository atomic updates where the database guarantees them, specifically relationship revision updates through RPC.

The multi-repository scenario is formally deferred:

1. create or update relationship
2. append corresponding version record
3. append lineage event
4. append provenance record

The next phase requiring that bundle must introduce a controlled SQL/RPC boundary that validates tenant context once and commits all writes atomically. P3.14 does not claim atomicity for that bundle.

## Integration Testing

Integration tests are environment-gated. They require explicit safe test configuration and must never run against an unapproved production database.

## Rollback

P3.14 migrations are additive. Runtime wiring remains disabled, so rollback is primarily operational: stop using the adapter package, restore database backup if a test environment must be reset, or apply a reviewed forward migration. Do not physically delete append-only history as part of normal rollback.

## Decision

P3.14 is **GO WITH CONDITIONS** for review as a limited persistence expansion. It is not approval to wire Supabase persistence into product runtime paths.
