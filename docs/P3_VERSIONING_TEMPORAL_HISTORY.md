# P3 Versioning and Temporal History Interfaces

P3.7 introduces provider-agnostic versioning, immutable snapshots, temporal-history records, and deterministic comparison for canonical entities and relationships. This phase is in-memory only.

## Architecture

The package is isolated under `data_fabric/versioning`:

- `VersionStore` defines immutable snapshot storage behavior.
- `TemporalHistoryStore` defines effective-time history behavior.
- `VersionComparator` defines deterministic payload comparison.
- `InMemoryVersionStore` and `InMemoryTemporalHistoryStore` are reference implementations.
- `DeterministicVersionComparator` reports stable added, removed, and changed field differences.

The package reuses canonical contracts from `data_fabric/contracts` and can retain optional lineage/provenance references. It is not wired into registries, identity resolution, quality evaluation, connectors, dashboards, persistence, schedulers, or graph projection.

## Snapshot Immutability

Snapshots are frozen dataclasses. Snapshot payloads are recursively frozen:

- dictionaries become read-only mappings with sorted keys
- lists and tuples become tuples
- sets become frozensets
- nested dataclasses are converted to dictionaries before freezing

Snapshot creation deep-copies contract state through dataclass serialization, so later source mutations do not affect stored snapshots.

## Version Lifecycle

Version numbers are monotonic per organization, tenant, and subject id. Duplicate versions and out-of-order versions are rejected. By default, a new version with unchanged content is rejected even when the version number increases. Unchanged content may be stored only when `allow_unchanged=True` is passed explicitly.

`EntityVersion` remains the canonical version metadata contract. P3.7 adds snapshot and store records around it rather than replacing it.

## Effective Time And Recorded Time

`effective_from` and `effective_to` describe the business validity interval. `recorded_at` describes when the snapshot or temporal record was captured in memory.

Point-in-time lookup uses:

```text
effective_from <= query_time < effective_to
```

For open-ended records, `effective_to` is `None`. Only one current open record may exist per organization, tenant, and subject.

## Content Hashing

Content hashes are deterministic SHA-256 hashes over the canonical snapshot payload. The hash ignores `snapshot_id` and `recorded_at`; version is treated as snapshot metadata rather than business content so a version-only bump is still detected as unchanged.

Canonicalization behavior:

- dictionary insertion order is ignored
- datetimes are converted to UTC ISO strings
- enums use their values
- UUIDs use string form
- sets are sorted by canonical JSON representation
- tuples and lists are order-sensitive arrays
- nested dataclasses are expanded into dictionaries

## Comparison Semantics

The comparator reports:

- `added` fields
- `removed` fields
- `changed` fields

Each `VersionDifference` includes `path`, `old_value`, and `new_value`. Dictionary key ordering is irrelevant. List and tuple ordering is significant and compared by index. Output ordering is stable by field path and change type. Unchanged payloads return an empty difference set.

## Tenant Isolation

Stores partition records by `organization_id`, `tenant_id`, and subject id. Duplicate ids in separate tenants remain isolated. Cross-tenant lookups do not return records.

## Extension Model

Provider-specific history policies, retention rules, or domain comparison behavior can be introduced later by implementing the interfaces. The core package stays provider-agnostic.

## Examples

```python
from data_fabric.versioning import InMemoryVersionStore

store = InMemoryVersionStore()
snapshot = store.create_entity_snapshot(entity)
latest = store.get_latest_entity_snapshot(
    entity.id,
    organization_id=entity.organization_id,
    tenant_id=entity.tenant_id,
)
```

## Limitations

- No persistence is included.
- No Supabase/database writes are included.
- No migrations are included.
- No runtime integration, background jobs, or schedulers are included.
- No dashboard, connector, registry, identity resolver, quality evaluator, or Knowledge Graph wiring is included.
