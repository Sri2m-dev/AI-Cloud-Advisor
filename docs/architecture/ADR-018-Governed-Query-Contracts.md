# ADR-018: Governed Query Contracts

Status: Accepted
Date: 2026-07-24
Program: Program G — WP-009
Decision authority: Srikanth Mudaliar, Owner, Chief Architect, Program Sponsor

## Context

Nexora has canonical Data Fabric contracts, tenant-bound registries, and a
rebuildable Knowledge Graph projection. Existing dependency and impact
capabilities are useful, but without a common query boundary they can diverge
in authorization, traversal limits, ordering, temporal meaning, and disclosure
of the governed state used to produce a result.

WP-009 requires named dependency, impact, and evidence queries without making
the graph authoritative or selecting a public API or persistence system.

## Decision

Adopt a persistence-neutral governed query contract with three named
operations:

- **Dependency Query** returns bounded, ordered dependency paths from a named
  canonical entity.
- **Impact Query** returns bounded, ordered affected entities and the governed
  paths that establish impact.
- **Evidence Query** returns authorized evidence references associated with a
  canonical entity, relationship, or returned path.

Each operation requires explicit query parameters and `TenantContext`. Results
must identify the projection checkpoint or version used, the query evaluation
time, applicable effective/as-of time, limits, cost consumption, and whether
the result was truncated or partial.

## Canonical Authority

- Queries read governed projections and canonical evidence references.
- Query results are derived and never become canonical records or writes.
- No query, graph, or projection interface may mutate canonical Data Fabric
  state.
- Projection drift is corrected from canonical changes under ADR-008 and
  WP-008 controls, never from a query result.

## Tenant Authorization

- `TenantContext` is mandatory at every query boundary.
- Every entity, relationship, path, and evidence reference must match the
  requesting organization and tenant.
- Traversal stops and fails closed when an endpoint or relationship crosses a
  tenant boundary.
- A permitted starting entity does not authorize an otherwise unauthorized
  endpoint, path, or evidence reference.

## Determinism and Reproducibility

- Query parameters are explicit and included in result metadata.
- Entities, relationships, paths, and evidence references use stable,
  documented ordering.
- Equivalent queries over equivalent governed projection state produce
  equivalent ordered results.
- Results identify projection checkpoint sequence and state hash, plus
  canonical object versions where available.
- Path identity is the ordered sequence of relationship identifiers and
  endpoints; discovery order must not affect it.

## Traversal and Query-Cost Controls

Every query declares limits within implementation-defined hard ceilings:

- maximum traversal depth;
- maximum returned paths or results;
- maximum fan-out per expanded node;
- maximum work budget, measured deterministically as relationship
  examinations.

Implementations must be cycle safe and must sort candidates before applying
fan-out, path, result, or budget limits. Requests above a hard ceiling are
rejected. When a valid request reaches its declared limit, deterministic
truncation is permitted only if the result reports:

- `truncated=true`;
- the limiting reason;
- consumed and configured budget;
- `partial=true`.

Checkpoint advancement and canonical state are unaffected by query execution.

## Temporal Semantics

- Results disclose query/evaluation time and projection/checkpoint identity.
- `as_of` or effective time is accepted only when retained governed history
  can support it.
- An unsupported historical request is rejected rather than answered from
  current state.
- Historical or stale results must never be represented as current.
- Entity, relationship, and evidence timestamps and versions are retained in
  explanations where available.

## Compatibility and Reuse

The query layer reuses:

- WP-008 projection/checkpoint controls;
- canonical `EnterpriseEntity` and `EnterpriseRelationship`;
- `TenantContext`;
- existing relationship, versioning, lineage, provenance, quality, and trust
  contracts;
- existing dependency and impact algorithms through adapters where they
  satisfy this ADR.

It does not introduce a graph engine, evidence authority, identity framework,
public REST/GraphQL API, database schema, or persistence choice.

## Consequences

Consumers receive reproducible, bounded, tenant-safe query results with
explicit state and cost metadata. Existing legacy graph services remain
unchanged until separately adapted and certified. More permissive traversal is
not backward-compatible with this boundary and requires architecture review.

## Implementation Acceptance

Implementation evidence must cover deterministic dependency and impact paths,
tenant and evidence isolation, depth/result/fan-out/budget limits, cycles,
deterministic truncation, temporal disclosure, projection/checkpoint/version
disclosure, reproducibility, and absence of canonical write-back.
