# WP-009 Governed Query/Explainability Contracts Implementation Evidence

Status: Engineering complete; draft Program G review pending

Starting baseline: `acd0df68771935691120d0f7d63d85f5d69e997f`

Branch: `feature/wp-009-governed-query-contracts`

Governing decisions: ADR-018, ADR-019, ADR-024

## Scope and Reuse

WP-009 adds one persistence-neutral `GovernedQueryService` with the three named
catalog operations:

- dependency query;
- impact query;
- evidence query.

The service reads the tenant-scoped WP-008 `InMemoryProjectionStore` and its
committed checkpoint. It reuses canonical `EnterpriseEntity` and
`EnterpriseRelationship`, `TenantContext`, Data Fabric versions, and existing
lineage/provenance reference semantics. Its deterministic breadth-first path
semantics align with the existing dependency traversal capability while adding
the authorization, checkpoint, cost, temporal, and disclosure controls that
the legacy runtime path does not provide.

The evidence input is an iterable of governed references, not a new evidence
registry or store. WP-010 remains responsible for the governed evidence
registry/use model.

## Delivered Controls

- stable path, entity, relationship, evidence, and partial-reason ordering;
- mandatory tenant context and fail-closed cross-tenant records/evidence;
- checkpoint sequence and projection state-hash disclosure;
- entity and relationship version disclosure;
- projection time, evaluation time, parameters, and as-of disclosure;
- explicit maximum depth, results, fan-out, and work budget;
- hard ceilings and rejection above them;
- cycle-safe traversal and deterministic truncation;
- work-consumption, truncation reason, and partial-result metadata;
- AVAILABLE, STALE, and MISSING evidence semantics;
- observation time, lineage, and provenance references;
- facts/paths separated from derived dependency and impact inference;
- unsupported historical queries rejected rather than answered as current;
- no canonical mutation or graph-to-canonical write-back interface.

## Acceptance Coverage

Focused tests cover deterministic dependency paths and impact results, evidence
retrieval, tenant isolation, cross-tenant paths and evidence, depth/result/
fan-out/work limits, hard ceilings, cycles, deterministic truncation, temporal
and freshness disclosure, missing and stale evidence, partial results,
checkpoint/state-hash/object-version disclosure, reproducibility, and the
canonical no-write-back boundary.

## Changed Files

- `governed_queries/__init__.py`;
- `governed_queries/models.py`;
- `governed_queries/service.py`;
- `tests/governed_queries/test_governed_queries.py`;
- `docs/program_g/WP_009_IMPLEMENTATION_EVIDENCE.md`.

## Validation

| Gate | Result |
| --- | --- |
| WP-009 focused | 20 passed |
| Program G combined | 129 passed |
| P3 non-secret | 94 passed |
| Full repository | 505 passed, 5 expected skips |
| Governance/security/certification | 57 passed |
| Secret-gated integrations | 5 collected, 5 expected no-secret skips |
| Contract/event governance | Passed; 3 providers, 3 consumers |
| Connector certification | Passed; 2 profiles, 4 pages, 4 observations |
| Ruff | Passed |
| Compile/import | Passed; representative imports passed |
| `pip check` | Passed |
| `git diff --check` | Passed |
| Hosted CI | Pending draft PR |

## Boundaries

Migration/schema required: **No**

Database accessed or modified: **No**

Runtime wiring, existing graph runtime, public API, REST, GraphQL, UI,
dashboard, connector, AI, identity, lineage/provenance framework, and evidence
registry changes: **No**

The implementation is additive and unadopted. Rollback is a source revert; no
data rollback is necessary. Merge and closure remain subject to Program G
review, explicit Owner approval, and exact-main post-merge validation.
