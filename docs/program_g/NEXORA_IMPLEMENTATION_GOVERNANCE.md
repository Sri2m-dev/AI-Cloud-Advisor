# Nexora Implementation Governance

Status: Ratified Program G Planning Baseline
Normative: Yes — for Program G planning, sequencing, and work-package scope
Governance state: G1, G2, and G3 complete
Implementation Authorization: Per-work-package authorization only
Original planning date: 2026-07-19
Owner ratification: Srikanth Mudaliar
Ratification date: 2026-07-20
Repository baseline: `02bae6453deddb4aaf605b81dedd0d1ee11cba17`
Portfolio state: WP-001–WP-003 closed; WP-004–WP-020 inactive pending individual activation

## Purpose

Define the gates that would translate approved architecture into engineering without allowing planning artifacts to authorize work.

## Governance hierarchy

```text
Architecture Constitution and accepted ADRs
  -> ratified architecture baseline
  -> product outcome and funded roadmap
  -> implementation blueprint/work package readiness
  -> increment authorization
  -> engineering delivery and release certification
  -> outcome review and governed Learning
```

## Permanent streams

### Architecture Governance

Owns ADR lifecycle, baseline, capability/domain ownership, principles, compatibility and architecture exceptions.

### Engineering Governance

Owns work-package readiness, sequencing, quality/security gates, dependency and release management, migration, deployment, operations and rollback.

### Product Governance

Owns persona outcomes, priority, commercial/customer value, funding, adoption and realized-value review.

Material conflicts require a recorded joint disposition. Product urgency cannot waive architectural/security invariants; architecture cannot create unfunded scope; engineering convenience cannot redefine product outcomes.

## Work-package state model

```text
Proposed -> Discovery -> Ready for Governance
  -> Authorized -> In Delivery -> Validating
  -> Release Ready -> Released -> Outcome Review -> Closed
```

`Deferred`, `Returned`, and `Cancelled` are explicit terminal/intermediate states with rationale. Only authorized governance roles move a WP to Authorized.

## Readiness checklist

- accepted ADRs and no unresolved dependency;
- named accountable, product, architecture, security and operational owners;
- persona decision/outcome and measurable acceptance;
- source authority/canonical stewardship/lifecycle ownership;
- API/event/data-product boundary and compatibility;
- tenant, privacy, threat and evidence model;
- NFR budgets and representative validation plan;
- migration, coexistence, rollback/compensation;
- delivery estimate, capacity and dependency commitment;
- documentation/runbook/release requirements.

## Change policy

Every future architectural change references an ADR, identifies affected domains, assesses backward compatibility, documents migration/operational impact and preserves or explicitly revises invariants through governance.

Scope changes inside an authorized WP are allowed only if acceptance, risk, dependencies and architecture remain intact. Otherwise the WP returns to governance.

## Quality gates

Compile/static/import, unit/contract, collection, full regression, tenant/authorization negatives, integration with controlled dependencies, migration/rollback, performance/capacity, security/privacy, observability/recovery and user/outcome acceptance as applicable. Test totals are evidence, not a substitute for coverage of required risks.

## Exceptions

An exception names requirement, rationale, risk owner, controls, scope, expiry, monitoring and remediation. It cannot weaken tenant isolation, fabricate evidence, bypass decision authority or rewrite durable history. Expired exceptions block release.

## Audit record

Retain authorization, reviewed scope, ADRs, test/release evidence, approvers, artifact/commit, deployment, exceptions, rollback decision and outcome. Planning documents remain clearly distinguishable from approved execution records.

## Current gate

G1, G2, and G3 are complete. WP-001 through WP-003 are closed. WP-004 through WP-020 remain inactive and may enter `Authorized` only through an explicit, package-specific owner decision after their readiness evidence is complete.
