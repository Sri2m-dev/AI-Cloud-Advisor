# Nexora Product Decision Record Process and Template

Status: **ADOPTED — PRODUCT GOVERNANCE v2.0**

## 1. Purpose

A Product Decision Record (PDR) is the durable record of a decision that changes or
resolves Nexora product behavior. It preserves why the decision was made, which
alternatives were considered, which evidence supports it, who approved it, and how
engineering and customers are affected.

PDRs complement Architecture Decision Records (ADRs):

- PDR: what the product means and how it behaves;
- ADR: how the architecture safely realizes that behavior;
- both: required when a product decision changes an architectural boundary.

## 2. Numbering and location

Approved records use:

```text
docs/product/decisions/PDR-NNN-short-title.md
```

Numbers are sequential and never reused. Superseded or rejected records remain in
history. The Product Decision Register maps P5-Dxx discovery items to PDR numbers.

## 3. Lifecycle

```text
PROPOSED → IN DISCOVERY → IN REVIEW → APPROVED
                              ├→ REJECTED
                              └→ DEFERRED
APPROVED → IMPLEMENTING → VERIFIED → ACTIVE
ACTIVE → AMENDED or SUPERSEDED or RETIRED
```

Only `APPROVED` decisions authorize engineering semantics. `ACTIVE` means the
approved behavior is released and certified; approval alone does not imply release.

## 4. Required evidence by decision type

| Decision type | Minimum evidence |
|---|---|
| Persona/KPI | Sponsor interviews, real decisions, prototype/usability evidence |
| Score/model | Domain rationale, representative cases, sensitivity/calibration plan |
| Materiality/ranking | Historical examples, false-positive/negative analysis |
| Financial | Reconciliation and invariant analysis, Finance approval |
| AI/narrative | Claim controls, evaluation set, human-review and safety plan |
| Evidence/entitlement | Data classification, purpose, security/privacy analysis |
| Workflow/authority | Segregation, policy, audit, abuse/failure analysis |
| UX/component | Wireframes, accessibility and responsive evidence |
| Board/export | Audience, confidentiality, sign-off, retention, native render review |
| Positioning | Customer research and sourced competitive evidence |

## 5. Impact classification

- **Minor:** additive clarification with no changed behavior or entitlement.
- **Material:** changes user-visible meaning, formula, threshold, workflow, or output.
- **Critical:** changes authority, tenant/security boundary, financial authority,
  evidence semantics, or external contractual behavior.

Material and critical decisions create a new Product Freeze version/amendment.

## 6. Review questions

Every reviewer answers:

1. What user decision does this support?
2. Is the behavior deterministic and explainable?
3. Which facts are authoritative and which outputs are derived?
4. What happens when data is missing, stale, conflicted, or unsupported?
5. Does it change tenant, persona, evidence, financial, or authority semantics?
6. Can an LLM alter the result?
7. How will it be validated, monitored, rolled back, and versioned?
8. Which documents, contracts, components, reports, and training change?

## 7. PDR template

```markdown
# PDR-NNN — Decision title

Status: PROPOSED
Impact: MINOR | MATERIAL | CRITICAL
Product decision reference: P5-Dxx (if applicable)
Owner:
Authors:
Required reviewers:
Created:
Decision date:
Effective date:
Review date:
Supersedes:
Related ADRs:
Related contracts/documents:

## Context and business question

What customer/executive decision requires a product rule? Why now?

## Decision

Precise chosen behavior. Include vocabulary, scope, grain, formula/rule,
thresholds, model/version, user-visible labels, and authority classification.

## Users and decisions supported

Personas, jobs, and decisions affected.

## Authoritative inputs and evidence

Sources, canonical subjects, versions/checkpoints, quality/freshness requirements,
lineage, and evidence.

## Derived behavior

Factors, normalization, weighting, aggregation, ranking, confidence, coverage,
materiality, narrative selection, or UI behavior.

## Missing and exceptional states

Behavior for PARTIAL, STALE, CONFLICTED, UNKNOWN, UNSUPPORTED, unauthorized,
unreconciled, and incomplete topology.

## Authority and safety

What this output permits and explicitly does not permit. Tenant, persona,
financial, evidence, policy, approval, execution, privacy, and security impact.

## Alternatives considered

Alternatives, advantages, disadvantages, and why rejected/deferred.

## Consequences and trade-offs

Positive, negative, operational, customer, support, and migration consequences.

## UX and content

Screens/components, labels, drill-downs, narratives, evidence display,
accessibility, responsive, and Board/export impact.

## Validation and calibration

Golden cases, boundary/sensitivity tests, usability, accessibility, security,
model-risk, financial invariants, authority tests, and success criteria.

## Telemetry and monitoring

Approved measures, privacy constraints, alert/review triggers, and drift/change
indicators.

## Implementation and migration

Work packages, contracts, feature/shadow mode, backfill/migration, compatibility,
release plan, and owner. Approval does not itself authorize implementation.

## Rollback and retirement

Safe rollback, historical reproducibility, customer communication, and retention.

## Documentation changes

Product Freeze, PDS, Decision Framework, UX Specification, ADRs, user guidance,
sales/marketing, and report methodology.

## Approval

| Role | Name | Decision | Date |
|---|---|---|---|
| Accountable Product Owner | | | |
| Domain owner | | | |
| Product | | | |
| Architecture | | | |
| Security/Governance | | | |
| Data/Model Risk | | | |
| UX/Accessibility | | | |
```

## 8. Engineering traceability

Approved PDR IDs appear in:

- requirements and acceptance tests;
- model/policy metadata and version output;
- relevant code documentation/configuration;
- UX component stories;
- audit/release evidence;
- Board methodology where material;
- release notes and Product Freeze amendments.

Tests must prove both the approved behavior and prohibited alternatives.

## 9. Emergency changes

Security or legal containment may temporarily disable behavior before a full PDR,
but cannot introduce new product semantics. The change must be fail-closed,
audited, owner-approved under incident procedure, and followed by a PDR/ADR review
within the approved incident timeframe.

## 10. Governance anti-patterns

Prohibited:

- embedding thresholds or weights in UI code without a PDR;
- changing a formula through prompt edits or configuration without review;
- using feature flags to bypass product approval;
- interpreting missing data as safe because it improves a score;
- renaming Recommendation to Decision for presentation;
- altering evidence visibility after AI context assembly;
- manually editing Board facts instead of regenerating from a checkpoint;
- treating an approved PDR as Production/release authorization.
