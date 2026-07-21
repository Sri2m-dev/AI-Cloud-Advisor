# ADR-024: Enterprise Metadata & Registry Platform

Status: Accepted
Date: 2026-07-21
Program: Program G — WP-006
Decision authority: Srikanth Mudaliar, Owner, Chief Architect, Program Sponsor

## Context and Rationale

The completed P3 foundation provides canonical contracts, identity resolution,
lineage, provenance, quality, ontology, versioning, and persistence boundaries.
WP-005 engineering adds stewardship behavior while its controlled database
release validation remains operationally pending. In this context, the former
WP-006 Business Service Registry is too narrow to provide consistent registry
semantics across enterprise technology domains.

Nexora requires one bounded metadata and registry capability that reuses P3
canonical authority rather than creating isolated registries with competing
definitions. Business Service Registry remains necessary and becomes Phase 1
of the broader platform.

## Decision

Amend WP-006 to **Enterprise Metadata & Registry Platform (EMRP)**.

WP-006 may implement only:

- registry interfaces;
- canonical entity models that conform to released P3 contracts;
- Business Service Registry as Phase 1;
- entity, relationship, identity, taxonomy, lineage, and metadata service
  interfaces;
- deterministic validation engines for duplication, reconciliation,
  relationships, ownership, taxonomy, circular dependencies, confidence, and
  completeness;
- repository interfaces without production persistence implementation;
- unit tests and implementation documentation.

The Data Fabric remains the canonical integration layer. EMRP organizes and
validates metadata through interfaces; it does not replace source authority or
bypass canonical stewardship.

## Architectural Impact

EMRP creates a cohesive domain/service boundary above existing P3 contracts.
It provides reusable registry semantics for later Business Service posture,
knowledge projection, evidence, decision, and experience work packages.

The architecture remains interface-first and independently compilable. No
runtime wiring, connector adoption, graph projection, public API, UI, or
database implementation is selected by this decision.

## Backward Compatibility

- Existing P3 canonical contracts remain authoritative and unchanged.
- Existing registry, connector, API, dashboard, authentication, AI, and graph
  behavior remains unchanged.
- Business Service Registry functionality is retained as Phase 1.
- New interfaces and models must be additive and must pass the released
  compatibility harness.
- No consumer is required to adopt EMRP during WP-006.

## Dependency Impact

WP-005 is split into two dependency states:

- **Engineering dependency: satisfied.** WP-005 engineering, technical review,
  remediation, local validation, evidence, and hosted CI are complete.
- **Release dependency: open.** WP-005 controlled database validation and
  closure remain pending.

WP-006 engineering may proceed from synchronized `main`. WP-006 merge and
release are blocked until WP-005 release validation completes and WP-005
closes. Later work packages retain their catalog dependencies.

## Implementation Boundaries

WP-006 must not modify:

- runtime wiring or existing application behavior;
- connectors or connector certification behavior;
- dashboards or other UI;
- authentication or RBAC;
- AI or Knowledge Graph runtime;
- existing public APIs;
- migrations, schemas, RLS, grants, Supabase, or other database objects;
- WP-005 code, migrations, evidence, or PR state.

Scope expansion beyond interfaces, models, services, validation, repository
interfaces, tests, and documentation requires another Owner decision and, when
architecturally material, a new or superseding ADR.

## Migration Strategy

WP-006 introduces no database migration and no runtime cutover. Adoption is
incremental:

1. define additive interfaces and canonical model adapters;
2. establish Business Service Registry behavior as Phase 1;
3. validate deterministic registry behavior with in-memory or test-only
   repositories;
4. retain existing runtime paths unchanged;
5. govern persistence or runtime adoption through a later explicit decision.

Rollback consists of removing or disabling unadopted additive modules before
merge. Because WP-006 does not alter runtime or persistence, no data rollback
is required.

## Risks and Controls

| Risk | Control |
| --- | --- |
| EMRP becomes a competing canonical authority | Reuse released P3 contracts and canonical stewardship; prohibit bypass writes. |
| Mega-registry scope | Interface-first bounded modules, Business Service Phase 1, and explicit exclusions. |
| Duplicate identities | Deterministic reconciliation and duplicate-detection tests. |
| Cross-tenant leakage | Mandatory tenant identifiers and WP-002 authorization patterns at applicable boundaries. |
| Circular or invalid relationships | Direction, taxonomy, cardinality, broken-link, and cycle validation. |
| Premature runtime coupling | No connectors, APIs, UI, graph runtime, persistence, or runtime wiring in WP-006. |
| Release dependency bypass | WP-006 merge remains blocked until WP-005 closes. |

## Approval Record

```text
Authority: Srikanth Mudaliar
Role: Owner, Chief Architect, Program Sponsor
Decision: ACCEPTED
Engineering authorization: YES
Merge authorization: NO
Release authorization: BLOCKED PENDING WP-005 CLOSURE
Approved branch after governance merge:
feature/wp-006-enterprise-registry
Date: 2026-07-21
```

This ADR supersedes only the former WP-006 title and scope. It does not close
WP-005, authorize WP-006 merge, or alter any other work package.
