# WP-015 Portfolio/Risk Decision Products — Implementation Evidence

Status: Engineering complete; Program G review pending
Work package: WP-015 — Portfolio/risk decision products
Baseline: `c82cc9faa0996581e7d5808540cd9782428dcce9`
Branch: `feature/wp-015-portfolio-risk-decision-products`
Dependencies: WP-007, WP-009, WP-011, and WP-012 — satisfied
Migration/schema required: **No**

## Scope and architecture reuse

WP-015 adds two bounded, persistence-neutral domain profiles over the existing
canonical Recommendation and Decision contracts:

- portfolio rationalization cases;
- risk-priority cases.

The product reuses, rather than duplicates:

- WP-007 versioned Business Service posture;
- WP-009 governed graph query results, checkpointed projection state, paths,
  partial-result disclosure, evidence, lineage, and provenance;
- WP-011 exact Recommendation/version and approved Decision/version;
- WP-012 exact ALLOW policy evaluation and active Approval/Exception;
- existing Digital Twin/simulation outputs through immutable scenario
  references;
- existing `TenantContext`, deterministic Data Fabric hashing, and canonical
  serialization.

It introduces no second Decision, graph, simulation, evidence, policy, or
portfolio registry framework. No REST, GraphQL, UI, connector, persistence,
schema, migration, database access, or runtime wiring is included.

## Implemented behavior

- Immutable tenant-bound lifecycle, risk, scenario, evidence, and case
  contracts.
- One Decision contract is retained across both profiles; cases reference an
  exact Recommendation/version and approved Decision/version.
- Creation requires the exact ALLOW policy evaluation and exact active
  Approval/Exception, with matching scope bound to the case entity.
- Governed graph attribution must include both the evaluated entity and the
  attributed Business Service.
- Portfolio outcomes are deterministic: `RETAIN`, `MODERNIZE`,
  `CONSOLIDATE`, `RETIRE`, or `INDETERMINATE`.
- Risk priority is deterministic: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, or
  `INDETERMINATE`, using explicit risk score and bounded graph blast radius.
- Missing/stale lifecycle or risk, partial/no-path graph results, and missing
  graph evidence remain explicit and produce an indeterminate profile.
- Scenario output retains engine/version/hash/time, affected entities,
  assumptions, lineage, and provenance, but never substitutes for approval.
- Tenant boundaries are enforced for Recommendation, Decision, policy
  evaluation, authority, posture, lifecycle/risk and nested evidence, graph
  metadata/evidence, and scenario references.
- Case revisions preserve the original governed Decision chain and immutable
  history.
- Bounded queries support Decision, Business Service, prioritized risk,
  version/history, and deterministic reconstruction.

## Deterministic reconstruction

The reconstruction retains:

```text
TenantContext
→ domain profile and version
→ Recommendation/version
→ Decision/version
→ policy evaluation/version
→ active Approval/Exception
→ Business Service posture/version
→ lifecycle and risk observations
→ graph checkpoint/hash/path/partial disclosure
→ scenario engine/version/hash/assumptions
→ evidence + lineage + provenance
→ immutable case history
```

## Acceptance coverage

Focused tests cover:

- retain, modernize, consolidate, and retire rationalization;
- critical, high, medium, and low deterministic risk priority;
- incomplete, stale, partial, pathless, and missing-evidence inputs;
- exact approved Decision, ALLOW evaluation, active authority, and scope;
- inactive approvals and exceptions;
- graph/entity/Business Service attribution;
- cross-tenant rejection for every input boundary;
- scenario attribution without authority confusion;
- deterministic bounded queries, reconstruction, hashes, and revision history.

## Changed files

- `portfolio_risk_decision_product/__init__.py`
- `portfolio_risk_decision_product/models.py`
- `portfolio_risk_decision_product/service.py`
- `tests/portfolio_risk_decision_product/test_portfolio_risk_decision_product.py`
- `docs/program_g/WP_015_IMPLEMENTATION_EVIDENCE.md`

## Validation

| Gate | Result |
| --- | --- |
| WP-015 focused | 29 passed |
| Program G combined | 283 passed |
| P3 non-secret release gate | 94 passed |
| Full repository | 675 passed, 5 expected skips |
| Governance/security/certification | 68 passed |
| Contract/event governance CLI | Passed; 3 providers, 3 consumers |
| Connector certification CLI | Passed; 2 profiles, 4 pages, 4 observations |
| Ruff | WP-015 and CI critical active-source checks passed |
| Compile/import | Passed; 1,166 active Python files |
| `pip check` | Passed |
| `git diff --check` | Passed |
| Hosted CI | Pending draft PR |

## Operational boundary

Database touched: **No**
Migration created: **No**
Production/external system touched: **No**
WP-016 started: **No**
