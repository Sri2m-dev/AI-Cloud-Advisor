# P3 Data Fabric Schema Blueprint

## Purpose

This blueprint defines schema boundaries and constraints for future Data Fabric persistence. It is not a migration and does not contain executable SQL.

## Naming Conventions

- Tables use lower snake case plural names.
- Primary keys are stable string identifiers unless a future adapter requires surrogate keys internally.
- Tenant columns are always `organization_id` and `tenant_id`.
- JSON columns end with `_json`.
- Optimistic concurrency column is `row_version`.
- Soft delete columns are `active`, `deleted_at`, and `deleted_by`.

## Current-State Tables

### enterprise_entities

Required uniqueness:

- `(organization_id, tenant_id, id)`
- `(organization_id, tenant_id, canonical_id)`
- `(organization_id, tenant_id, source_system, source_identifier)`

Required indexes:

- tenant plus `entity_type`
- tenant plus `name`
- tenant plus `updated_at`
- tenant plus `active`

### enterprise_relationships

Required uniqueness:

- `(organization_id, tenant_id, id)`
- optional natural uniqueness for `(relationship_type, source_entity_id, target_entity_id, source_system, source_identifier)` when source identity is available

Required indexes:

- tenant plus `relationship_type`
- tenant plus `source_entity_id`
- tenant plus `target_entity_id`
- tenant plus `active`

### semantic_concepts

Required uniqueness:

- `(organization_id, tenant_id, concept_id)`
- `(organization_id, tenant_id, canonical_name)`

Required indexes:

- tenant plus `concept_type`
- tenant plus `parent_concept_id`
- tenant plus `active`

### semantic_mappings

Required uniqueness:

- `(organization_id, tenant_id, mapping_id)`
- `(organization_id, tenant_id, source_system, source_term, source_type, source_identifier, provider, entity_type)` where nullable fields are normalized by adapter policy

Required indexes:

- tenant plus `concept_id`
- tenant plus `source_system`
- tenant plus `active`

## Immutable Tables

### entity_version_snapshots and relationship_version_snapshots

Required uniqueness:

- `(organization_id, tenant_id, snapshot_id)`
- `(organization_id, tenant_id, subject_id, version)`
- `(organization_id, tenant_id, subject_id, payload_hash)` may be used to detect duplicate snapshots

Required indexes:

- tenant plus `subject_id`
- tenant plus `recorded_at`
- tenant plus `effective_from`, `effective_to`

### temporal_history_records

Required uniqueness:

- `(organization_id, tenant_id, record_id)`
- `(organization_id, tenant_id, subject_id, version)`

Required indexes:

- tenant plus `subject_id`, `effective_from`, `effective_to`
- tenant plus `is_current` if implemented as materialized flag

### lineage_events

Required uniqueness:

- `(organization_id, tenant_id, id)`

Required indexes:

- tenant plus `entity_id`
- tenant plus `relationship_id`
- tenant plus `source_system`, `source_identifier`
- tenant plus `occurred_at`
- tenant plus `event_type`

### provenance_records

Required uniqueness:

- `(organization_id, tenant_id, id)`

Required indexes:

- tenant plus `entity_id`
- tenant plus `relationship_id`
- tenant plus `source_system`, `source_identifier`
- tenant plus `captured_at`

### quality_assessments

Required uniqueness:

- `(organization_id, tenant_id, assessment_id)` or deterministic assessment id

Required indexes:

- tenant plus `subject_id`
- tenant plus `subject_type`
- tenant plus `final_score`
- tenant plus `recorded_at`

## Control Tables

### idempotency_records

Required uniqueness:

- `(organization_id, tenant_id, idempotency_key)`

Required indexes:

- tenant plus `state`
- tenant plus `created_at`
- tenant plus `updated_at`
- tenant plus `correlation_id`

### transaction_audit_records

Required uniqueness:

- `(organization_id, tenant_id, transaction_id)`

Required indexes:

- tenant plus `request_id`
- tenant plus `status`
- tenant plus `started_at`
- tenant plus `completed_at`

### ingestion_batches and ingestion_record_results

Required indexes:

- tenant plus `batch_id`
- tenant plus `request_id`
- tenant plus `status`
- tenant plus input order

## Row-Level Access Policy

Future storage policy must enforce tenant scope at the storage layer, not only in Python repositories. The exact policy syntax is adapter-specific and intentionally deferred.
