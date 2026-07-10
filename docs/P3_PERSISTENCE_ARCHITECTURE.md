# P3 Persistence Architecture

## Purpose

This document defines the architecture for persisting the P3 Data Fabric. It is design only. It does not implement repositories, migrations, Supabase clients, ORM models, runtime wiring, dashboard changes, connector changes, schedulers, or Knowledge Graph integration.

## Architecture Principles

1. Orchestration owns multi-store write coordination.
2. Repositories own persistence boundaries, not business workflow.
3. Current state and immutable history are separate stores.
4. Tenant context is mandatory for every persisted read and write.
5. Deterministic serialization is required for payload hashes and JSON payloads.
6. Idempotency completion happens only after durable transaction commit.
7. Dashboards and connectors must not write Data Fabric stores directly.

## Aggregate Roots

| Aggregate | Role | Current State | History |
| --- | --- | --- | --- |
| Canonical entity | Primary canonical object | `enterprise_entities` | `entity_version_snapshots`, `temporal_history_records` |
| Canonical relationship | Relationship between canonical entities | `enterprise_relationships` | `relationship_version_snapshots`, `temporal_history_records` |
| Semantic concept | Ontology concept | `semantic_concepts` | concept version audit in later phase |
| Semantic mapping | Source term to concept mapping | `semantic_mappings` | mapping audit in later phase |
| Ingestion request | Orchestration write request | `idempotency_records`, `ingestion_record_results` | transaction audit |
| Lineage/provenance | Explainability evidence | append-only records | append-only records |
| Quality assessment | Trust and quality result | latest pointer optional | immutable assessment records |

## Repository Boundaries

Initial repository interfaces should be defined before adapters:

- `EntityRepository`
- `RelationshipRepository`
- `VersionRepository`
- `TemporalHistoryRepository`
- `LineageRepository`
- `ProvenanceRepository`
- `QualityAssessmentRepository`
- `SemanticConceptRepository`
- `SemanticMappingRepository`
- `IdempotencyRepository`
- `TransactionAuditRepository`

Repositories must accept `TenantContext` and must not infer tenant scope from payload fields alone.

## Adapter Boundary

Adapters translate repository contracts into concrete storage. The first adapter can target Supabase/Postgres, but adapter code is not part of P3.10C.

Adapter responsibilities:

- enforce tenant filters
- map contracts to storage rows
- use deterministic serializer for JSON fields
- handle optimistic concurrency
- translate storage errors to `DataFabricError` hierarchy
- participate in transaction boundary where supported

## Write Flow

1. `IngestionCoordinator` receives an `IngestionRequest`.
2. Pipeline validates tenant context and idempotency.
3. Pipeline creates entity/relationship write plans.
4. Quality gate decides allow, warning, quarantine, or reject.
5. Version policy decides whether history is needed.
6. Lineage and provenance plans are prepared.
7. Unit of work stages current-state, history, evidence, and idempotency writes.
8. Durable transaction commits.
9. Idempotency record is completed.
10. Explainable result is returned.

## Read Flow

Read models should query current-state repositories first. History, lineage, provenance, and quality repositories should be joined by explicit service methods, not implicit dashboard queries.

## Runtime Boundary

No existing dashboard, connector, or runtime path should be changed during architecture design. Future runtime integration must call service-layer orchestration, not repository adapters directly.

## Decision

P3.10C approves persistence architecture design and allows a later limited implementation phase only after review and merge.
