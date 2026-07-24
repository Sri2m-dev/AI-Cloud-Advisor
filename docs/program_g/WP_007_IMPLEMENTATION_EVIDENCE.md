# WP-007 Business Service Posture Product Implementation Evidence

Status: Engineering complete; draft Program G review pending

Work package: WP-007 — Business Service posture product

Catalog outcome: Versioned service-posture query/data product

Starting baseline: `ace1e9141ee015e810739f7ae9fc0f6f49ef88a2`

Branch: `feature/wp-007`

Dependencies:

- WP-006 Enterprise Metadata & Registry Platform: closed;
- owned cost, risk, and health domain inputs: reused from existing platform
  signal contracts;
- WP-002 tenant boundary and WP-003/WP-004 contract/evidence controls:
  preserved.

## Implementation

WP-007 provides a persistence-neutral, tenant-bound Business Service posture
data product with three explicit dimensions:

- cost;
- risk;
- health.

Each dimension reports exactly one of:

- `AVAILABLE`;
- `STALE`;
- `MISSING`.

Missing inputs retain `score=None`; they are never converted to zero. The
product deliberately has no overall/composite score.

The implementation includes:

- thin adapters over the existing `CostSignal`, `RiskSignal`, and
  `HealthSignal` contracts;
- deterministic Technology-to-Business-Service attribution through canonical
  entity and relationship contracts;
- rejection of missing, ambiguous, unsupported, invalid, and cross-tenant
  attribution;
- tenant-scoped evidence references with source identity and optional
  lineage/provenance references;
- explicit observation time, evaluation time, age, freshness threshold, and
  freshness result;
- semantic idempotency for identical inputs;
- new versions for dimension changes or freshness-state transitions;
- latest, history, and exact-version query methods;
- an in-memory reference repository with no runtime or database adoption.

## Architecture Reuse

The implementation reuses:

- `enterprise_registry.BusinessServiceRegistry`;
- `TenantContext`;
- `EntityRegistry`;
- `RelationshipRegistry`;
- canonical `EnterpriseEntity` and `EnterpriseRelationship`;
- `CostSignal`, `RiskSignal`, and `HealthSignal`;
- existing lineage/provenance reference semantics.

It does not introduce a replacement cost, risk, health, identity, relationship,
registry, or evidence engine.

## Changed Files

- `business_service_posture/__init__.py`;
- `business_service_posture/models.py`;
- `business_service_posture/repository.py`;
- `business_service_posture/service.py`;
- `business_service_posture/attribution.py`;
- `business_service_posture/adapters.py`;
- `tests/business_service_posture/test_service_posture.py`;
- `tests/business_service_posture/test_domain_adapters.py`;
- `docs/program_g/WP_007_IMPLEMENTATION_EVIDENCE.md`.

Engineering commits:

- `71aa1fa2` — initial versioned dimensional posture data product;
- `45d467fe` — canonical attribution, domain adapters, scoped evidence, and
  complete acceptance coverage.

## Acceptance Evidence

Focused tests cover:

- complete posture;
- partial posture;
- completely missing posture;
- stale cost, risk, and health;
- exact freshness boundaries and one-second stale transitions;
- identical-input semantic idempotency;
- changed cost, risk, and health versioning;
- cost, risk, and health attribution;
- missing, ambiguous, and unsupported attribution;
- invalid and cross-tenant Business Service access;
- cross-tenant domain inputs, relationships, and evidence;
- source/evidence/timestamp/freshness traceability;
- latest, history, and exact-version queries;
- prohibition of hidden missing values and composite scoring.

Validation on the completed local source state:

| Gate | Result |
| --- | --- |
| WP-007 focused | 18 passed, 0 failed |
| Program G combined focused regression | 126 passed, 0 failed |
| P3 non-secret release gate | 94 passed, 0 failed |
| Full repository suite | 472 passed, 5 expected skips, 0 failed |
| Governance/certification tests | 38 passed, 0 failed |
| Contract/event governance CLI | Passed; 3 providers, 3 consumers |
| Connector evidence certification CLI | Passed; 2 profiles, 4 pages, 4 observations |
| Ruff | Passed |
| Active-source compile/import | 1,132 files; representative imports passed |
| Dependency validation | `pip check` passed |
| Git whitespace validation | `git diff --check` passed |

The five skips remain the approved opt-in Supabase integrations. The three
warnings remain existing Pydantic v2 deprecations.

## Boundaries and Operations

Migration required: **No**

Schema/database change: **No**

Database access: **No**

Runtime wiring, API, GraphQL, UI, dashboard, connector, AI, and Knowledge Graph
changes: **No**

Rollback before adoption consists of reverting the additive package and tests.
The reference repository is in-memory, and no durable state requires rollback,
replay, repair, or reconciliation.

Hosted CI, Program G review, explicit merge approval, post-merge validation,
and explicit closure remain pending. This evidence does not authorize merge or
WP-008.
