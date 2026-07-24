# WP-010 Evidence Registry/Use Model Implementation Evidence

Status: Engineering complete; draft Program G review pending

Starting baseline: `97d86e6ddc3ddac72098e3e90c4c7a690caf9216`

Branch: `feature/wp-010-evidence-registry`

Governing decision: ADR-019

## Authoritative Scope

Catalog title: **Evidence registry/use model**

Objective: accept connector observations and P3 provenance inputs and expose
governed evidence references with explicit case roles.

Dependencies:

- WP-004 Connector Evidence Certification: closed;
- WP-005 Canonical Coverage and Stewardship: closed;
- ADR-019 Explainability and Evidence Disclosure: accepted.

Acceptance: immutable approved evidence packages plus explicit correction and
supersession behavior.

## Reuse and Gaps

| Requirement | Initial classification | Delivery |
| --- | --- | --- |
| Observation identity/hash/checkpoint semantics | Already satisfied | Reused from WP-004 |
| Lineage/provenance references | Already satisfied | Reused from P3 contracts |
| Tenant context | Already satisfied | Reused from WP-002/Data Fabric |
| Quality/trust metadata | Already satisfied | Reused as governed score/reference |
| Version/supersession principles | Partially satisfied | Applied to evidence/package history |
| Governed evidence references | Engineering required | Implemented |
| Case roles | Engineering required | Implemented |
| Immutable approved package | Engineering required | Implemented |
| Correction/supersession evidence | Engineering required | Implemented |

## Implementation

The persistence-neutral `InMemoryEvidenceRegistry` provides:

- immutable tenant-bound evidence references with source identity, content
  hash, observation/capture time, lineage, provenance, and quality metadata;
- semantic deduplication of identical source evidence;
- explicit conflict rejection when changed source evidence lacks a correction;
- correction records that preserve the original and record a successor;
- explicit case roles: supporting, contradicting, context, baseline, outcome;
- deterministic package entry ordering and per-case version history;
- draft creation followed by approval with a deterministic integrity hash;
- immutable approved packages;
- superseding packages that preserve approved predecessors;
- cross-tenant evidence, package, and history isolation;
- rejection of missing, duplicate, or already-superseded references.

The implementation does not create a second provenance, lineage, identity,
quality, or observation framework. It stores references to those governed
concepts and does not change WP-009 query contracts.

## Changed Files

- `evidence_registry/__init__.py`;
- `evidence_registry/models.py`;
- `evidence_registry/service.py`;
- `tests/evidence_registry/test_evidence_registry.py`;
- `docs/program_g/WP_010_IMPLEMENTATION_EVIDENCE.md`.

## Acceptance Tests

Focused tests cover governed references, source deduplication, conflict
handling, corrections, immutable evidence, case roles, missing/duplicate/
superseded reference rejection, deterministic approval hashes, approved-package
immutability, package supersession, history preservation, tenant isolation, and
absence of runtime/database/canonical-write interfaces.

## Validation

| Gate | Result |
| --- | --- |
| WP-010 focused | 16 passed |
| Program G combined | 145 passed |
| P3 non-secret | 94 passed |
| Full repository | 521 passed, 5 expected skips |
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

Runtime wiring, public API, REST, GraphQL, UI, dashboard, connector, AI,
Knowledge Graph, Data Fabric, identity, provenance, lineage, quality, and
existing service/repository behavior changed: **No**

The implementation is additive and unadopted. Rollback is a source revert with
no data rollback. Merge and closure remain subject to Program G review,
explicit Owner approval, and exact-main post-merge validation.
