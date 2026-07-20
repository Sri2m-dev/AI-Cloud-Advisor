# Nexora P5 Planning Risk Register

Status: Ratified Program G Planning Baseline  
Normative: Yes — for Program G planning, sequencing, and work-package scope  
Governance state: G1, G2, and G3 complete  
Implementation Authorization: Per-work-package authorization only  
Original planning date: 2026-07-19  
Owner ratification: Srikanth Mudaliar  
Ratification date: 2026-07-20  
Repository baseline: `02bae6453deddb4aaf605b81dedd0d1ee11cba17`  
Portfolio state: WP-001–WP-003 closed; WP-004–WP-020 inactive pending individual activation

## Scale

Impact and likelihood: Low, Medium, High. Owners are proposed accountable teams, not named individuals.

| ID | Risk | Likelihood | Impact | Proposed owner | Mitigation / gate |
| --- | --- | --- | --- | --- | --- |
| R-001 | G1 rejects or modifies foundational ADRs | Medium | High | Architecture Governance | keep P4/P5 conditional; re-plan affected DAG |
| R-002 | P5 plan is mistaken for implementation approval | Medium | High | Program Governance | banners, readiness gates, no repository work |
| R-003 | Source authority remains ambiguous | High | High | Data Governance/domain owners | attribute authority matrix before WP-005/006 |
| R-004 | Business Service becomes mega-aggregate | Medium | High | Portfolio/Architecture | federated posture data product and bounded root |
| R-005 | Graph becomes alternate source of truth | Medium | High | Knowledge/Data Fabric | projection-only writes, rebuild/reconciliation tests |
| R-006 | Relationship history deferral blocks temporal use cases | High | Medium | Architecture/Data Fabric | constrain claims; separate ADR/migration later |
| R-007 | Cross-tenant leakage through cache/graph/events/AI | Medium | Critical | Platform Security | negative gates across every data path |
| R-008 | Evidence duplication or retention conflict | Medium | High | Data Governance/Security | governed references, immutable packages, correction rules |
| R-009 | Decision Intelligence becomes central monolith | Medium | High | Decision Intelligence/Architecture | retain domain calculations and contract profiles |
| R-010 | AI candidates mistaken for official Recommendations | Medium | High | AI/Decision teams | artifact labeling and ownership contract |
| R-011 | Confidence used as authority | Low | Critical | Governance/Risk | deterministic policy, mandatory floors, indeterminate block |
| R-012 | Execution success claimed as realized value | High | High | Decision/Finance/domain verifier | independent outcome plan and reconciliation |
| R-013 | Enterprise Memory preserves bias/stale data | Medium | High | Memory/Data Governance | admission, expiry, contradiction, applicability review |
| R-014 | Premature microservices increase operations cost | Medium | Medium | Platform Architecture/SRE | modular-first extraction criteria |
| R-015 | Connector coverage/freshness limits decision quality | High | High | Integration | certification, reconciliation and visible abstention |
| R-016 | Finance models fail authoritative reconciliation | Medium | High | Financial Intelligence | ledger reconciliation and approved measures |
| R-017 | Legacy migration creates divergent behavior | High | High | Engineering Governance | side-by-side parity, strangler and rollback |
| R-018 | Scope exceeds available team capacity | High | High | Product/Engineering Governance | vertical slice, WIP limits, staged team formation |
| R-019 | Enterprise-scale claims lack benchmarks | Medium | High | SRE/Architecture | representative workloads before technology choice |
| R-020 | Policy emergency path becomes bypass | Low | High | Governance/Security | expiry, independent review and monitoring |

## Top gate risks

R-001, R-003, R-007, R-011, R-012 and R-018 prevent safe execution planning from becoming delivery authorization.

## Review cadence

Review at G1 disposition, each increment readiness gate, material ADR change, security incident, failed outcome or major scope/capacity change. Closed risks retain evidence and may create reviewed Learning.

