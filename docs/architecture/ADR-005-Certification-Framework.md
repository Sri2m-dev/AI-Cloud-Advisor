# ADR-005: Certification Framework

Status: Accepted
Date: 2026-07-05
Release: v1.0.0-enterprise-foundation

## Context

Nexora needed a way to distinguish functional pages from enterprise-grade pages. Early pages could work technically while still lacking evidence, reconciliation, executive narrative, or engineering separation.

## Decision

Adopt a certification model for pages and workspaces.

Certification evaluates:

- Executive experience
- Design system compliance
- Data integrity
- Engineering quality
- Enterprise architecture traceability
- Governance and evidence
- Performance posture where applicable

Certification services orchestrate page-specific certification payloads while domain services retain business logic.

## Options Considered

1. Mark pages complete once they loaded.
2. Track informal polish items.
3. Use explicit scoring and certification gates.

## Rationale

Certification creates an objective quality bar and keeps the platform from accumulating inconsistent experiences. It also supports release readiness and enterprise governance.

## Consequences

- New pages should target certification patterns from the beginning.
- Certification services should not own core business logic.
- Certified pages should expose executive summary, reconciliation where relevant, business context, AI narrative, and evidence.

## Future Considerations

- Automate certification checks where possible.
- Add visual regression tests.
- Add performance and accessibility gates to certification.
