# ADR-016: Data Fabric Persistence Architecture

Status: Proposed
Date: 2026-07-10
Program: P3 Enterprise Data Fabric & Intelligence Platform

## Context

P3.2 through P3.10B established canonical contracts, registry interfaces, identity resolution, lineage and provenance, quality and trust scoring, versioning, semantic ontology, foundation utilities, idempotency, and orchestration contracts. The next architectural decision is how those contracts should be persisted without weakening tenant isolation, deterministic serialization, lineage, version history, or transaction semantics.

This ADR is architecture only. It does not introduce SQL migrations, Supabase code, ORM models, repository adapters, runtime wiring, dashboards, schedulers, connector changes, or Knowledge Graph integration.

## Decision

Adopt a layered persistence architecture for the Data Fabric with separate stores for current canonical state, immutable history, source identity, semantic ontology, lineage/provenance, quality assessment, idempotency, and transaction audit.

Persistence implementation must be introduced behind repository interfaces and adapter boundaries. Orchestration remains the only write coordinator for multi-store operations.

## Aggregate Roots

- Canonical entity
- Canonical relationship
- Semantic concept
- Semantic mapping
- Ingestion request / idempotency record
- Version snapshot
- Lineage event and provenance record

## Store Boundaries

Authoritative current-state stores:

- `enterprise_entities`
- `enterprise_relationships`
- `semantic_concepts`
- `semantic_mappings`

Immutable history and explainability stores:

- `entity_version_snapshots`
- `relationship_version_snapshots`
- `temporal_history_records`
- `lineage_events`
- `provenance_records`
- `quality_assessments`

Control stores:

- `idempotency_records`
- `transaction_audit_records`
- `ingestion_batches`
- `ingestion_record_results`

## Tenant Isolation

Every persisted tenant-scoped table must include `organization_id` and `tenant_id`. Repository methods must require `TenantContext`; adapters must reject attempts to read or write records outside that context.

Storage design must use composite tenant keys and database-level access policy when implemented. Application-level checks are not sufficient by themselves.

## Uniqueness And Indexing

Persistence must enforce tenant-scoped uniqueness for:

- canonical entity id
- canonical entity canonical id
- source system plus source identifier
- relationship id
- semantic concept id
- semantic canonical name
- semantic mapping source signature
- idempotency key
- version snapshot subject plus version number

Indexes must support tenant-filtered lookup by id, canonical id, source identity, entity type, relationship endpoints, semantic concept name, version, effective time, lineage subject, provenance source, and idempotency key.

## JSON And Normalized Columns

Normalized columns are required for tenant keys, ids, types, source identifiers, timestamps, scores, version numbers, active/deleted flags, and concurrency versions.

JSON columns may be used for flexible metadata, attributes, payload snapshots, quality dimension details, lineage metadata, provenance metadata, and orchestration explanations. JSON payloads must be produced through the shared deterministic serializer.

## Concurrency

Current-state tables must support optimistic concurrency with an integer row version or equivalent revision token. Repository updates must compare expected revision values and raise a conflict on mismatch.

Immutable history tables do not update in place. Correction requires a new record with explicit supersession or correction metadata.

## Soft Deletes

Current-state records use soft delete fields: `active`, `deleted_at`, and `deleted_by` or system actor. Deactivation must create lineage/provenance and version history when it changes canonical state.

Immutable records are never soft-deleted except by governed retention policy outside P3 implementation scope.

## Transactions And Idempotency

Repository adapters must participate in an orchestration-owned unit of work. Idempotency completion occurs only after the durable transaction commits. A duplicate idempotency key with a different deterministic payload hash must raise an explicit conflict.

## Consequences

This design separates current operational state from immutable evidence and history. It supports deterministic replay, tenant isolation, explainability, rollback, and future adapter substitution.

The consequence is that persistence implementation must be phased. Direct table writes from dashboards, connectors, or background jobs are prohibited.

## Implementation Readiness

Decision: GO WITH CONDITIONS for limited persistence implementation after this architecture is reviewed and merged.

Conditions:

- repository interfaces must be added before adapters
- migrations must follow the approved schema blueprint
- durable idempotency must be implemented before multi-record ingestion writes
- tenant isolation must be enforced in repositories and storage policy
- no dashboard, connector, runtime, scheduler, or Knowledge Graph wiring may be added in the first persistence implementation phase
