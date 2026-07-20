# Nexora Work Package Catalog

Status: Ratified Program G Planning Baseline  
Normative: Yes — for Program G planning, sequencing, and work-package scope  
Governance state: G1, G2, and G3 complete  
Implementation Authorization: Per-work-package authorization only  
Original planning date: 2026-07-19  
Owner ratification: Srikanth Mudaliar  
Ratification date: 2026-07-20  
Repository baseline: `02bae6453deddb4aaf605b81dedd0d1ee11cba17`  
Portfolio state: WP-001–WP-003 closed; WP-004–WP-020 inactive pending individual activation

## Estimation model

Effort uses team-sprint ranges for comparative planning only: S `1-2`, M `3-5`, L `6-10`, XL `11-18+`. Ranges exclude procurement, governance wait time and unknown legacy remediation.

| WP | Work package | Inputs | Outputs | Dependencies | Key risk | Acceptance summary | Effort |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WP-001 | Release baseline and compatibility harness | certified P3 branch/evidence | released baseline, golden contracts/fixtures | G2/G3 | baseline drift | post-merge certification and reproducible fixtures | M |
| WP-002 | Tenant identity and authorization foundation | identity/RBAC, ADRs | verified context envelope, domain authorization patterns | WP-001, G1 | cross-tenant leakage | negative tests across API/cache/jobs/events/AI | L |
| WP-003 | Contract and event governance toolkit | ADR baseline, P3 contracts | versioning, schema checks, compatibility policy | WP-001, G1 | accidental breaking change | consumer/provider contract gates and deprecation evidence | M |
| WP-004 | Connector evidence certification | connector framework | observation envelope, checkpoint/reconciliation certification | WP-002/003 | incomplete source data | replay, duplicate, pagination, deletion, secret tests | L |
| WP-005 | Canonical coverage and stewardship | Data Fabric, ontology | authority matrix, identity/quality queues, coverage data product | WP-002/004 | unresolved identities | scoped quality/freshness and steward workflow accepted | L |
| WP-006 | Business Service registry | business architecture, canonical registry | governed service aggregate and ownership lifecycle | WP-002/005, ADR-024 | mega-aggregate | lifecycle, authority, conflict and tenant tests | L |
| WP-007 | Business Service posture product | service registry, cost/risk/health inputs | versioned service posture query/data product | WP-006, domain products | misleading composite | dimensional evidence, freshness and no-hidden-missing-data tests | L |
| WP-008 | Knowledge projection control | canonical changes | rebuildable projection, checkpoints, reconciliation | WP-003/005, graph ADRs | graph becomes authority | replay/rebuild and canonical-no-bypass tests | XL |
| WP-009 | Governed query/explainability contracts | projection, evidence | named dependency/impact/evidence query APIs | WP-008, ADR-018/019/024 | authorization path leakage | reproducible paths, cost limits, temporal/freshness disclosure | L |
| WP-010 | Evidence registry/use model | observations, P3 provenance | governed evidence references and case roles | WP-004/005, ADR-019 | duplicate evidence truth | immutable approved package and correction/supersession tests | L |
| WP-011 | Recommendation and Decision package | findings/alternatives/evidence | governed lifecycle, authority and audit | WP-009/010, ADR-020/024 | AI self-authority | proposer/approver separation and decision reconstruction | XL |
| WP-012 | Policy and approval integration | decision package, policies | deterministic evaluation, approvals, exceptions | WP-002/011, ADR-022/023 | ambiguous policy authorization | indeterminate blocks, expiry and segregation tests | L |
| WP-013 | Execution authorization/outcome verification | approved decision, connectors | bounded action, compensation, outcome plan/results | WP-004/012 | command success mistaken for value | exact authorization, rollback and independent verification | XL |
| WP-014 | Financial decision product | billing/allocation/service posture | cost alternatives, forecast and realized savings | WP-007/011/013 | unreconciled economics | finance reconciliation and attribution acceptance | XL |
| WP-015 | Portfolio/risk decision products | lifecycle, risk, graph | rationalization and risk-priority cases | WP-007/009/011/012 | generic decision model gaps | domain profiles retain one Decision contract | L |
| WP-016 | Enterprise Memory | verified outcomes | reviewed Learning and governed retrieval | WP-013, ADR-021 | stale/bias/privacy | admission, expiry, contradiction, access and provenance tests | L |
| WP-017 | AI evaluation and grounded reasoning | authorized queries, memory | evaluated analysis/candidates and abstention | WP-009/016, ADR-020/023 | hallucination/injection/cost | task metrics, red-team, tenant isolation and budget controls | XL |
| WP-018 | Agent execution controls | AI plans, policy, action APIs | tool registry, delegated identity, checkpoints/kill switch | WP-012/013/017 | unsafe autonomy | dry-run, approval, limits, compensation and audit | XL |
| WP-019 | Role experience migration | governed data products | executive/CIO/architect/FinOps/service-owner journeys | WP-007/009/011/014/015 | UI reimplements logic | evidence drill-through and legacy parity | L |
| WP-020 | Platform scale and operations certification | all deployed slices | SLOs, capacity, recovery, cost and support evidence | preceding packages | operational overload | representative load, restore, chaos and runbooks | XL |

## Packaging rules

- Each WP owns a bounded outcome and may be split only while preserving vertical acceptance.
- Conditional P4 packages cannot enter delivery before their ADRs are accepted.
- Effort is re-estimated after discovery and representative benchmarks.
- A WP cannot close with only mocks where live contract behavior is material.

