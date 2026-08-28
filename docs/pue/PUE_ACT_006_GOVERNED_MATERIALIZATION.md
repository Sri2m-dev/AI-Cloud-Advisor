# PUE-ACT-006 Governed Entity & Relationship Materialization

## Architecture boundary

ACT-006 uses the existing `data_fabric` canonical contracts and registries:

- `EnterpriseEntity` and `EnterpriseRelationship` remain the write contracts.
- `EnterpriseRegistryService` remains the canonical identity authority.
- `InMemoryEntityRegistry` and `InMemoryRelationshipRegistry` provide the bounded
  process-local pilot repositories.
- `EnterpriseKnowledgeGraphService` remains a read-only projection over those
  registries; no ACT-006 graph or database is introduced.

The materializer accepts normalized, governed observations and emits deterministic
entity and relationship proposals before registering anything. Candidate, rejected,
stale, ambiguous, unsupported, shadow, and kill-switch states fail closed.

## Identity and authority

Identity is scoped by tenant, organization, entity type, source system, and source
identifier. Exact canonical/source identity is preferred; exact same-type natural
keys are allowed. Fuzzy name similarity is not used. Existing ownership edges have
precedence over conflicting uploaded ownership evidence, which is surfaced as
`CONFLICT` without overwriting the existing edge.

Entity and relationship fingerprints include governed mapping and normalized
evidence references. Replaying the same observations resolves the same entities and
edges without duplicates. Every pilot entity stores proposal and source-row
references in canonical provenance metadata; every edge retains evidence references.

## Prospect and persistence boundary

ACT-006 is process-local pilot materialization. Prospect and analysis identifiers
remain part of proposal scope and are never promoted into production inventory by
upload. Production persistence, promotion, history, and destructive reconciliation
remain outside ACT-006 and are reserved for later reviewed programs.

## Workbook result

`temp_uploads/CUR Jan 2026.xlsx` contains 184 primary detail rows with Service,
Sub-Service/Type, Region, UoM, and financial columns. Without governed mappings for
those columns, ACT-006 retains the workbook as evidence and creates no entities.
With an authorized Service mapping, a value may propose an existing supported
Technology entity. Region has no dedicated canonical `EntityType` in the current
contract and is therefore unsupported rather than converted into a mystery entity.
Financial columns remain observations and are never converted into entities or
recomputed by ACT-006. The workbook does not itself authorize cloud resources,
applications, owners, providers, or relationships.

## Controlled fixture

The bounded fixture proves governed proposals for AWS, `i-test123`, Checkout, Order
Processing, Alice, and `CC-1001`; canonical resolution; four authorized edges;
replay idempotency; existing graph projection visibility; and Alice-over-Bob
ownership conflict handling. It does not modify production or demo seed data.

## Deferred work

ACT-C6 is backend-certified through the focused ACT-006 and existing registry/graph
tests. No browser acceptance is required because ACT-006 adds no production page or
new interactive behavior. A future integrated acceptance should verify the finished
workflow after ACT-013 is available.