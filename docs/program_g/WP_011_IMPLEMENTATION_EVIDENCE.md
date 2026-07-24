# WP-011 Recommendation and Decision Package Implementation Evidence

Status: Engineering complete; draft Program G review pending

Starting baseline: `2af1515da5f3fac6433e9f191f35dfc1b69730a4`

Branch: `feature/wp-011-recommendation-decision`

Governing decisions: ADR-018, ADR-019, ADR-020, ADR-024

## Scope and Reuse

WP-011 transforms findings, alternatives, and governed WP-010 evidence packages
into a tenant-bound Recommendation lifecycle and an explicitly authorized
Decision disposition.

It reuses:

- `TenantContext`;
- WP-010 immutable evidence packages, roles, hashes, correction, and
  supersession behavior;
- P3 lineage, provenance, and version-history semantics;
- WP-009 fact/inference disclosure principles;
- existing recommendation and governance/authority behavior through a thin
  authority adapter boundary.

It does not replace the existing AI recommendation, approval, evidence,
identity, lineage, provenance, or governance services and does not wire the new
contracts into runtime paths.

## Delivered Capability

- immutable Recommendation and Decision contracts;
- explicit human, AI, and governed-service actor types;
- required finding, action, outcome, alternatives, proposer, evidence package,
  timestamps, state, and version;
- explicit AI-proposed identification;
- deterministic DRAFT, PROPOSED, UNDER_REVIEW, APPROVED, REJECTED,
  REVISION_REQUIRED, WITHDRAWN, and SUPERSEDED transitions;
- append-only lifecycle event evidence;
- authority evaluation before Decision creation;
- proposer/approver segregation;
- absolute rejection of all AI Decision authority;
- approved WP-010 evidence-package binding;
- AVAILABLE, STALE, MISSING, CONFLICTING, and SUPERSEDED evidence evaluation;
- approval blocked for insufficient evidence;
- immutable Decisions and preserved prior Recommendation versions;
- correction and supersession with predecessor references;
- deterministic reconstruction containing Recommendation version/content,
  alternatives, evidence roles/hashes, proposer, approver, authority,
  disposition, timestamps, lineage/provenance, history, and fact/inference
  boundary;
- tenant isolation across access, evidence, Decisions, and reconstruction;
- no policy authorization or execution method.

## Changed Files

- `recommendation_decision/__init__.py`;
- `recommendation_decision/models.py`;
- `recommendation_decision/service.py`;
- `tests/recommendation_decision/test_recommendation_decision.py`;
- `docs/program_g/WP_011_IMPLEMENTATION_EVIDENCE.md`.

## Acceptance Coverage

Focused tests cover human and AI Recommendations, alternatives, evidence
binding, missing/stale/conflicting/superseded evidence, valid human approval,
rejection, revision request, withdrawal, correction, supersession,
proposer/approver segregation, AI self-approval, alternate-AI approval,
unauthorized approval, cross-tenant Recommendation/evidence/Decision/
reconstruction, invalid transitions, deterministic complete reconstruction,
immutable Decisions, preserved history, and absence of execution side effects.

## Validation

| Gate | Result |
| --- | --- |
| WP-011 focused | 21 passed |
| Program G combined | 166 passed |
| P3 non-secret | 94 passed |
| Full repository | 542 passed, 5 expected skips |
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

Runtime wiring, existing recommendation/decision/approval services, public API,
REST, GraphQL, UI, dashboard, connector, Knowledge Graph, AI execution, policy
authorization, and execution behavior changed: **No**

The implementation is additive and persistence-neutral. Rollback is a source
revert with no data rollback. WP-012 was not started. Merge and closure remain
subject to Program G review, explicit Owner approval, and exact-main validation.
