# P3 Storage Model

## Purpose

Define the storage model for the Data Fabric before any database implementation begins.

## Table Boundaries

### Current State

| Table | Purpose |
| --- | --- |
| `enterprise_entities` | Current canonical entity state. |
| `enterprise_relationships` | Current canonical relationship state. |
| `semantic_concepts` | Current ontology concepts. |
| `semantic_mappings` | Current source-term mappings. |

### Immutable History

| Table | Purpose |
| --- | --- |
| `entity_version_snapshots` | Immutable entity payload snapshots. |
| `relationship_version_snapshots` | Immutable relationship payload snapshots. |
| `temporal_history_records` | Effective-time history records. |
| `quality_assessments` | Immutable quality and trust results. |
| `lineage_events` | Append-only source-to-canonical events. |
| `provenance_records` | Append-only source authority records. |

### Control And Audit

| Table | Purpose |
| --- | --- |
| `idempotency_records` | Durable idempotency state. |
| `transaction_audit_records` | Transaction outcome and rollback audit. |
| `ingestion_batches` | Batch request metadata. |
| `ingestion_record_results` | Per-record processing outcomes. |

## Common Columns

Every tenant-scoped table requires:

- `organization_id`
- `tenant_id`
- stable primary id
- `created_at`
- `updated_at` where mutable
- `metadata_json` where flexible metadata is needed

Mutable current-state tables also require:

- `active`
- `deleted_at`
- `deleted_by`
- `row_version`

## Entity Current State

`enterprise_entities` should normalize:

- `id`
- `canonical_id`
- `entity_type`
- `name`
- `source_system`
- `source_identifier`
- `organization_id`
- `tenant_id`
- `version`
- `confidence_score`
- `quality_score`
- `created_at`
- `updated_at`
- `active`
- `row_version`

JSON fields:

- `tags_json`
- `metadata_json`
- embedded identity, quality, ownership, lineage summary, provenance summary where denormalization is justified

## Relationship Current State

`enterprise_relationships` should normalize:

- `id`
- `relationship_type`
- `source_entity_id`
- `target_entity_id`
- `source_system`
- `source_identifier`
- `organization_id`
- `tenant_id`
- `version`
- `confidence_score`
- `quality_score`
- `created_at`
- `updated_at`
- `active`
- `row_version`

## Immutable Snapshot Tables

Snapshot tables should normalize:

- `snapshot_id`
- `subject_id`
- `subject_type`
- `organization_id`
- `tenant_id`
- `version`
- `recorded_at`
- `effective_from`
- `effective_to`
- `source_system`
- `source_identifier`
- `payload_hash`
- `lineage_ref`
- `provenance_ref`

JSON field:

- `payload_json`

## Indexes

Required indexes:

- `(organization_id, tenant_id, id)`
- `(organization_id, tenant_id, canonical_id)`
- `(organization_id, tenant_id, source_system, source_identifier)`
- `(organization_id, tenant_id, entity_type)`
- `(organization_id, tenant_id, source_entity_id)`
- `(organization_id, tenant_id, target_entity_id)`
- `(organization_id, tenant_id, subject_id, version)`
- `(organization_id, tenant_id, subject_id, effective_from, effective_to)`
- `(organization_id, tenant_id, idempotency_key)`
- `(organization_id, tenant_id, source_system, source_term)`

## JSON Versus Normalized Columns

Normalize fields used for identity, tenant isolation, joins, uniqueness, filtering, and ordering. Store flexible payloads and explanation details as deterministic JSON.

## Soft Delete

Current-state records are deactivated with `active=false`, `deleted_at`, and `deleted_by`. Immutable history is append-only.
