# WP-008 Knowledge Projection Control Implementation Evidence

Status: Engineering complete; draft Program G review pending

Work package: WP-008 — Knowledge projection control

Catalog outcome: Rebuildable projection, checkpoints, and reconciliation

Starting baseline: `f23342d8ac991c4e4a280a4c8d7cbb4be701ed97`

Branch: `feature/wp-008-knowledge-projection-control`

## Readiness and Requirement Classification

| Requirement | Starting classification | Delivery |
| --- | --- | --- |
| Accepted graph architecture | Already satisfied | ADR-003 is accepted |
| Canonical Data Fabric authority | Already satisfied | ADR-008/009 and WP-005 remain authoritative |
| Versioned/ordered canonical input | Partially satisfied | Thin `CanonicalChange` envelope added over canonical contracts |
| Rebuildable projection | Engineering required | Deterministic full rebuild implemented |
| Incremental replay | Engineering required | Contiguous, checkpoint-resuming replay implemented |
| Checkpoints | Engineering required | Tenant-bound sequence/hash/count checkpoint implemented |
| Reconciliation | Engineering required | Missing, unexpected, divergent, and hash evidence implemented |
| Canonical-no-bypass | Engineering required | Projection mutation requires controller capability; no reverse write API |
| Persistence/schema | Not required | In-memory reference implementation only |

WP-003 and WP-005 are closed. The catalog dependencies are therefore
satisfied. The implementation follows accepted ADR-003, ADR-008, ADR-009,
ADR-014, ADR-016, and ADR-017 without modifying any ADR.

## Architecture and Implementation

`KnowledgeProjectionController` is the only projection write coordinator. It
accepts ordered changes from a canonical change source and derives tenant-bound
graph projection state. The graph is never consulted to update canonical state.

The bounded implementation provides:

- `CanonicalChange` using existing `EnterpriseEntity` and
  `EnterpriseRelationship` payloads;
- strict, contiguous, tenant-bound canonical sequence validation;
- incremental replay from the last committed checkpoint;
- deterministic full rebuild from canonical history;
- checkpoints containing tenant scope, sequence, deterministic state hash, and
  applied-change count;
- reconciliation of authoritative canonical state against projection state,
  reporting missing, unexpected, and divergent records;
- relationship endpoint validation before a relationship enters the
  projection;
- transactional in-memory behavior: a failed batch does not replace state or
  advance its checkpoint;
- controller-capability enforcement for derived projection writes;
- no projection-to-canonical mutation interface.

This layer reuses:

- `TenantContext`;
- `EnterpriseEntity`;
- `EnterpriseRelationship`;
- the shared `DefaultDeterministicSerializer`;
- Data Fabric canonical authority and versioning principles.

It does not replace the Data Fabric, canonical registries, relationship
registry, identity resolution, ontology, or existing graph query services.
The existing legacy graph repositories are not adopted as WP-008 input or
authority.

## Changed Files

- `knowledge_projection/__init__.py`;
- `knowledge_projection/control.py`;
- `knowledge_projection/exceptions.py`;
- `knowledge_projection/models.py`;
- `knowledge_projection/stores.py`;
- `tests/knowledge_projection/test_projection_control.py`;
- `docs/program_g/WP_008_IMPLEMENTATION_EVIDENCE.md`.

## Acceptance Evidence

Focused deterministic tests cover:

- initial and incremental replay;
- checkpoint resume and idempotent replay;
- deterministic rebuild and drift repair;
- canonical removals;
- relationship endpoint integrity;
- ordered sequence gaps, duplicates, and out-of-order rejection;
- cross-tenant change and payload rejection;
- tenant-scope separation;
- missing, unexpected, and divergent reconciliation;
- failed-batch checkpoint non-advancement;
- rejected projection writes without controller authority;
- absence of a reverse graph-to-canonical write path.

Validation on the completed source state:

| Gate | Result |
| --- | --- |
| WP-008 focused | 12 passed, 0 failed |
| Program G combined focused regression | 109 passed, 0 failed |
| P3 non-secret release gate | 94 passed, 0 failed |
| Full repository suite | 485 passed, 5 expected skips, 0 failed |
| Governance/certification | 57 passed, 0 failed |
| Secret-gated integrations | 5 collected; 5 approved no-secret skips |
| Contract/event governance CLI | Passed; 3 providers, 3 consumers |
| Connector evidence certification CLI | Passed; 2 profiles, 4 pages, 4 observations |
| Ruff | Passed |
| Active-source compile/import | Passed; representative imports passed |
| Dependency validation | `pip check` passed |
| Git whitespace validation | Passed |
| Hosted CI | Pending draft PR |

The contracts are internal, persistence-neutral orchestration contracts. They
do not add a public event transport or released provider/consumer boundary, so
the WP-003 manifest remains unchanged.

## Boundaries, Security, and Operations

Migration required: **No**

Schema/database change: **No**

Database accessed: **No**

Runtime wiring, API, GraphQL, UI, dashboard, connector, AI, and query-contract
changes: **No**

The in-memory reference store is not a durable production adapter. Durable
projection storage and runtime adoption require a separately reviewed adapter
behind these controls; they are not needed to evidence the catalog's projection
control behavior.

Rollback before adoption consists of reverting this additive package, tests,
and evidence file. Rebuild from canonical changes is the recovery mechanism for
derived state; canonical records are never repaired from graph contents.

Merge and closure remain subject to Program G review, explicit Owner approval,
and exact-merge hosted and local validation.
