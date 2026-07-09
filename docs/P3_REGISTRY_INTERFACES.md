# P3 Registry Interfaces

P3.3 introduces registry interfaces for canonical Enterprise Data Fabric entities and relationships. This is an interface and in-memory reference layer only.

## Scope

Included:

- `EntityRegistry` and `RelationshipRegistry` abstract interfaces.
- `InMemoryEntityRegistry` and `InMemoryRelationshipRegistry` reference implementations.
- Validation for required canonical identity and source fields.
- Explicit duplicate `canonical_id` handling for entities.
- Non-destructive deactivation via metadata flags.

Excluded:

- Database persistence.
- Supabase writes.
- Migrations.
- Dashboard changes.
- Connector runtime changes.
- P1/P2 behavior changes.

## Entity Registry Methods

- `register_entity(entity)`
- `get_entity(entity_id)`
- `find_entity_by_canonical_id(canonical_id)`
- `search_entities(...)`
- `update_entity(entity)`
- `deactivate_entity(entity_id)`

## Relationship Registry Methods

- `register_relationship(relationship)`
- `get_relationship(relationship_id)`
- `search_relationships(...)`
- `deactivate_relationship(relationship_id)`

## Validation Rules

Entities require:

- `id`
- `canonical_id`
- `source_system`
- `source_identifier`

Relationships require:

- `id`
- `source_entity_id`
- `target_entity_id`
- `source_system`
- `source_identifier`

Duplicate entity `canonical_id` values raise `DuplicateCanonicalIdError`. This keeps identity conflict behavior explicit before persistence, identity resolution, or graph integration is introduced.

## Persistence Position

The in-memory registries are reference implementations for contract validation and interface tests. They must not be treated as durable storage and do not write to Supabase, local databases, files, dashboards, or connector runtimes.
