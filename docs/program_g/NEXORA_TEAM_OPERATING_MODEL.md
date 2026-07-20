# Nexora Team Operating Model

Status: Ratified Program G Planning Baseline  
Normative: Yes — for Program G planning, sequencing, and work-package scope  
Governance state: G1, G2, and G3 complete  
Implementation Authorization: Per-work-package authorization only  
Original planning date: 2026-07-19  
Owner ratification: Srikanth Mudaliar  
Ratification date: 2026-07-20  
Repository baseline: `02bae6453deddb4aaf605b81dedd0d1ee11cba17`  
Portfolio state: WP-001–WP-003 closed; WP-004–WP-020 inactive pending individual activation

## Principles

Teams align to enduring capabilities and outcomes, not pages. Platform teams provide paved roads; domain teams retain business meaning. Team names are proposed ownership roles, not approved organization changes.

## Proposed teams

| Team | Accountabilities | Initial WPs |
| --- | --- | --- |
| Platform Security & Tenancy | identity, authorization, secrets, tenant context, audit mechanisms | WP-002 |
| Developer Platform & SRE | delivery standards, observability, environments, recovery, contract tooling | WP-001/003/020 |
| Enterprise Integration | connector SDK, collection, observations, checkpoints, actions | WP-004, part WP-013 |
| Data Fabric & Governance | canonical registry, identity, ontology, provenance, quality, stewardship | WP-005/010 |
| Portfolio Intelligence | business services, applications, technology lifecycle | WP-006/007/015 |
| Enterprise Knowledge | projections, dependency/impact and explainable queries | WP-008/009 |
| Financial Intelligence | allocation, reconciliation, forecast, savings outcomes | WP-014 |
| Decision Intelligence | Recommendation, Decision, Outcome and Memory lifecycle | WP-011/013/016 |
| Governance Platform | policy evaluation, approval, exceptions, controls | WP-012 |
| AI Platform | model gateway, evaluation, grounded analysis, agent controls | WP-017/018 |
| Enterprise Experience | role journeys, BFF composition, reporting/accessibility | WP-019 |

## Permanent governance streams

- **Architecture Governance:** ADRs, baseline, capabilities and invariants.
- **Engineering Governance:** sequencing, quality, compatibility, deployment and release.
- **Product Governance:** persona value, priorities, roadmap and market/customer outcomes.

A cross-stream decision forum resolves conflicts; no stream unilaterally weakens another's mandatory controls.

## Accountabilities

Each WP names one accountable owner, product/value owner, architecture reviewer, security/privacy reviewer and operational owner. Contributors may span teams, but accountability is singular. Data products additionally name a steward and quality/freshness objectives.

## Interaction modes

- Team APIs/events/data products are versioned contracts.
- Enabling teams embed temporarily to establish patterns, then return ownership.
- Complicated-subsystem experts support graph, finance and AI evaluation without becoming approval bottlenecks.
- Communities of practice align ontology, testing, security, SRE and explainability.

## Capacity guidance

Do not form every proposed team immediately. Begin with stable ownership cells around the first slice, then split when cognitive load, release cadence, scaling or security boundaries justify it. Avoid one “architecture team” implementing every domain or one “AI team” owning Recommendations and Decisions.

## Operating cadence

- Product discovery/value review: frequent, tied to lighthouse decisions.
- Architecture/ADR review: at material boundaries and increment gates.
- Engineering readiness: before work enters delivery.
- Security/data-governance review: continuous with formal gates.
- Operational review: SLOs, incidents, capacity, cost and recovery evidence.
- Outcome review: compare expected and realized value, feed reviewed Learning.

## Team health measures

Decision lead time, contract change failure, cross-team blocking time, operational toil, SLO attainment, escaped tenant/security defects, rework from unclear ownership and realized-value adoption. Feature volume is not a sufficient team success measure.

