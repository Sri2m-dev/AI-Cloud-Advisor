# CMP-P4 Multi-Source Enterprise Intelligence — Implementation Report

## Decision

- Implementation: **PASS**
- Automated certification: **PASS**
- Browser acceptance: **DEFERRED_ENVIRONMENT**
- CMP-P3 browser acceptance: **DEFERRED_ENVIRONMENT**
- CMP-P2B browser acceptance: **DEFERRED_ENVIRONMENT**
- REL-C1: **HOLD — EXTERNAL REMEDIATION**

The browser environment lacked required sandbox capability metadata. This is recorded as an
acceptance-environment limitation, not a demonstrated Nexora defect.

## Architecture

CMP-P4 establishes a single publication boundary beneath `connector_sdk` and
`connector_runtime`. Existing provider and Universal Evidence paths adapt into this boundary;
CMP-P4 does not introduce another connector framework.

External assertions remain immutable source facts. Connector success never establishes canonical
truth. Only fact-specific authority policy and governed reconciliation may create decisions for
CMP-P1, CMP-P2, or CMP-P3 authority.

## Source authority contracts

`SourceInstance` distinguishes tenant-scoped source installations, connector and configuration
identity, connector version, enabled state, and opaque credential reference. Raw credentials are
rejected and never persisted.

`SourceFact` separates a stable observation key from immutable fact-version identity. Scope,
source record, predicate, and effective identity determine the observation stream. Changed content
appends the next version; identical replay publishes no semantic duplicate. Facts retain source
instance, run, schema and connector versions, quality, freshness, lifecycle, evidence, lineage,
provenance, and fingerprint.

Fact types are controlled through an explicit enum covering identity, application membership and
ownership, team membership, cost center, lifecycle, cost, license, utilization, dependency, and
contract assertions.

## Sync, checkpoint, and schema governance

Sync runs record mode, status, counters, errors, checkpoints, schema fingerprint, and correlation
ID. Fact publication, run completion, source state, and checkpoint movement share one transaction.
Only successful publication advances a checkpoint. Partial, failed, or quarantined execution
retains the previous checkpoint.

Deterministic fingerprints make repeated pages, files, API responses, and checkpoints idempotent.
Schema snapshots classify unchanged, compatible-additive, mapping-required, incompatible, and
unknown changes. Additive changes continue explicitly; missing required fields and semantic type
changes quarantine facts before publication.

Errors are bounded and secret-looking errors are redacted.

## Freshness and lifecycle

Fact freshness (`FRESH`, `AGING`, `STALE`, `UNKNOWN`) is independent of connector health. A healthy
connector can report stale records, and connector failure does not invalidate earlier canonical
truth.

One-run absence does not delete or deactivate a fact. Lifecycle distinguishes active,
temporarily absent, source tombstone, decommissioned, source disabled/replaced, and connector
failure. Explicit tombstones append versions; history remains reconstructable. Source deactivation
is tenant-scoped and retains immutable fact history.

## Authority, conflicts, and explanation

Authority policies are tenant-scoped, fact-specific, versioned, and effective-dated. They define
source priority, permitted sources, confirmation requirements, and optional freshness expectation.
There is no global trusted-source switch.

General reconciliation compares facts only after tenant partitioning and returns explicit
consistent, priority-resolved, candidate-conflict, ambiguous, human-review, stale-source, or
unresolved outcomes. Equal-authority disagreement cannot use last-write-wins. Human selection
requires actor, role, and reason and is persisted as reconciliation authority.

Explanation reconstructs the decision, contributing fact IDs and versions, source instances,
policy/version, freshness, evidence references, fingerprints, and human attribution.

## Representative ingestion classes

Cloud/API, CMDB/enterprise inventory, telemetry, and Universal Evidence CSV/XLSX adapters all emit
the same `SourceFactInput` contract. Directory/HR, finance/cost-center, and SaaS assertions use the
same explicit identifier and fact-type model. Provider adapters fetch and interpret source records;
they do not decide canonical identity, ownership, cost center, monetary, or savings truth.

## Frozen-phase integration

CMP-P1 remains monetary authority, CMP-P2 remains opportunity/savings authority, and CMP-P3
remains canonical relationship authority. CMP-P4 contributes source evidence and governed
decisions without duplicating spend, savings, or graph authority. Registry and consumers receive
only governed canonical output.

CMP-P4 changes no CMP-P1, CMP-P2, or CMP-P3 implementation file.

## Persistence, restart, replay, and purge

Migration `migrations/data_fabric/0022_create_source_fact_authority.sql` is ordered after 0021,
additive, RLS-enabled, and contains no customer or environment identifiers. It uses four cohesive
tables for source instances, immutable facts, runtime state, and source authority rather than one
table per logical feature. Source facts have a mutation-prevention trigger, tenant-aware lookup
indexes, stable-version uniqueness, and no cascading foreign keys that could erase retained
evidence when a source is disabled.

Tenant scope participates in deterministic IDs, including same-key cross-tenant collision tests.
Restart restores fact versions and checkpoints. Replay converges without duplication. Source purge
or deactivation cannot affect another tenant or destroy retained facts.

The migration was not applied to an external production database; production execution remains a
deployment certification gate.

## Synthetic and failure acceptance

Synthetic A–L coverage exercises multi-source cost/context composition, telemetry evidence,
SaaS/directory-compatible facts, conflicting ownership, freshness, same-name identity safety,
absence, tombstones, schema quarantine, cross-tenant isolation, file/API convergence, and governed
cost-center conflict behavior.

Negative coverage includes repeated evidence, replayed checkpoints, partial execution, incompatible
schema, missing required fields, source absence, explicit tombstone, stale/equal-authority
conflicts, attributed human decisions, tenant collisions, disabled sources, secret-like errors, and
static/demo records failing to bypass the typed publication boundary.

## Certification

- CMP-P4 focused: **9 passed** after tenant-collision hardening
- CMP-P4 persistence/migration gate: **24 passed**
- Progressive connector/evidence/frozen-phase suite: **1,088 passed**
- Full repository: **1,759 passed, 2 skipped**
- Active-source compileall: **PASS**
- Scoped Ruff: **PASS**
- Migration structural validation: **PASS**
- Persistence/restart/replay validation: **PASS**
- `git diff --check`: **PASS**
- Secret scan: **PASS**
- Runtime-artifact scan: **PASS**

The final tenant-ID hardening changed only the CMP-P4 source-fact package and its focused tests; its
focused and persistence suites passed afterward. Existing warnings are legacy dependency
deprecations and do not affect exit codes.

## Deferred gates

- `CMP-P4_BROWSER = DEFERRED_ENVIRONMENT`
- `CMP-P3_BROWSER = DEFERRED_ENVIRONMENT`
- `CMP-P2B_BROWSER = DEFERRED_ENVIRONMENT`
- External migration execution and operational lock/rollback validation belong to deployment
  certification.
- Release acceptance remains open.
