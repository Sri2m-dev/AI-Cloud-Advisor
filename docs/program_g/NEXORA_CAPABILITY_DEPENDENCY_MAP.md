# Nexora Capability Dependency Map

Status: Ratified Program G Planning Baseline
Normative: Yes — for Program G planning, sequencing, and work-package scope
Governance state: G1, G2, and G3 complete
Implementation Authorization: Per-work-package authorization only
Original planning date: 2026-07-19
Owner ratification: Srikanth Mudaliar
Ratification date: 2026-07-20
Repository baseline: `02bae6453deddb4aaf605b81dedd0d1ee11cba17`
Portfolio state: WP-001–WP-003 closed; WP-004–WP-020 inactive pending individual activation

## Implementation DAG

```text
G1/G2/G3 governance and released baseline
  |
  +-> WP-002 Tenant identity/authorization
  +-> WP-003 Contract/event governance
         |
         +-> WP-004 Connector evidence certification
         |      |
         |      +-> WP-005 Canonical coverage/stewardship
         |             |
         |             +-> WP-006 Business Service registry
         |             |      |
         |             |      +-> WP-007 Service posture
         |             |
         |             +-> WP-008 Knowledge projection
         |                    |
         |                    +-> WP-009 Query/explainability
         |                           |
         +--------------------> WP-010 Evidence model
                                      |
                         WP-009 + WP-010
                                      |
                                WP-011 Decision package
                                      |
                                WP-012 Policy/approval
                                      |
                    WP-004 + WP-012 -> WP-013 Execution/outcome
                                      |
                    +-----------------+------------------+
                    |                                    |
             WP-014 Financial                    WP-015 Portfolio/risk
                    |                                    |
                    +-----------------+------------------+
                                      |
                                WP-016 Memory
                                      |
                                WP-017 AI reasoning
                                      |
                      WP-013 + WP-017 -> WP-018 Agents

WP-007/009/011/014/015 --------------------------> WP-019 Experiences
Delivered slices --------------------------------> WP-020 Scale/operations
```

## Critical path

Governance -> baseline -> tenant/contract controls -> connector evidence -> canonical coverage -> Business Service/knowledge projection -> explainability/evidence -> Decision package -> policy/approval -> execution/outcome -> Memory -> evaluated AI.

AI is deliberately downstream of governed retrieval and Decision ownership. Experience migration can begin per validated data product rather than waiting for every later capability.

## Hard dependencies

| Consumer | Must have first | Reason |
| --- | --- | --- |
| Canonical coverage | connector evidence and tenant context | identity without source fidelity is unreliable |
| Business Service posture | registry plus owned domain inputs | posture must not duplicate authority |
| Knowledge queries | canonical coverage and projection controls | graph cannot become source of truth |
| Recommendation | evidence and alternatives | accountability requires inspectable basis |
| Decision | recommendation/alternatives plus authority | proposal cannot self-authorize |
| Execution | decision, policy, approval and connector action | least privilege and exact scope |
| Outcome | execution plus measurement plan/baseline | completion is not realized value |
| Learning | reviewed outcomes | Memory cannot ingest unverified claims |
| AI/agents | governed queries, confidence and policy | safe analysis/action boundary |

## Parallelizable streams

- WP-002 and WP-003 after release baseline.
- Connector certification and authority/stewardship discovery overlap after contract standards.
- Financial and risk/portfolio profiles run in parallel after the core Decision package.
- Experience work proceeds slice by slice once its data products are stable.
- Operations/security testing is continuous, not a final-stage activity.

## Dependency risks

- G1 deferral of an ADR can block multiple downstream packages.
- Relationship-history deferral constrains temporal graph queries.
- Source authority ambiguity blocks canonical stewardship and outcomes.
- Finance reconciliation can become a critical path for value claims.
- Premature AI/UI work creates rework if evidence and decision contracts move.

## Change control

Any proposed edge removal or reorder must document affected acceptance criteria, architectural invariant, migration risk and value impact. Calendar pressure alone is not justification for bypassing a hard dependency.
