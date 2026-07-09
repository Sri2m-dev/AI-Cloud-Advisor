# P3 Lineage and Provenance Interfaces

P3.5 introduces interface-only lineage and provenance tracking for explainability across connector, entity, relationship, dashboard, and AI interpretation flows. This phase does not integrate those flows yet.

## Scope

Included:

- `LineageTracker` and `ProvenanceTracker` abstract interfaces.
- `InMemoryLineageTracker` and `InMemoryProvenanceTracker` reference implementations.
- `LineageEvent`, `LineagePath`, and `ProvenanceRecord` dataclasses.
- Entity and relationship origin explanations.
- Source-based provenance tracing.

Excluded:

- Database persistence.
- Supabase writes.
- Migrations.
- Dashboard changes.
- Connector/runtime changes.
- Knowledge Graph writes or graph projection.
- P1/P2 behavior changes.

## Lineage Events

The lineage tracker supports four event types:

- `source`: source collection or connector ingestion event.
- `normalization`: source-to-normalized transformation event.
- `canonicalization`: normalized-to-canonical entity event.
- `relationship`: canonical relationship derivation event.

Lineage can be traced by `entity_id` or relationship id, and explanations summarize the recorded source and transformation path.

## Provenance Records

The provenance tracker records source authority and derivation context using:

- `source_system`
- `source_identifier`
- `collection_method`
- optional connector, normalization, identity-resolution, and review metadata

Provenance can be traced by source identity and explained for entities or relationships.

## Persistence Position

The in-memory trackers store records only inside Python object instances. They do not write to Supabase, local databases, files, dashboards, connector runtimes, or graph stores.
