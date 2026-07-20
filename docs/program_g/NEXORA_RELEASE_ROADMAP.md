# Nexora Release Roadmap

Status: Ratified Program G Planning Baseline  
Normative: Yes — for Program G planning, sequencing, and work-package scope  
Governance state: G1, G2, and G3 complete  
Implementation Authorization: Per-work-package authorization only  
Original planning date: 2026-07-19  
Owner ratification: Srikanth Mudaliar  
Ratification date: 2026-07-20  
Repository baseline: `02bae6453deddb4aaf605b81dedd0d1ee11cba17`  
Portfolio state: WP-001–WP-003 closed; WP-004–WP-020 inactive pending individual activation

## Roadmap model

Releases package validated increments; they do not drive architecture or force incomplete controls. Version names and dates require Product and Engineering Governance approval.

## Governance sequence

```text
G1 Architecture ratification
  -> G2 v1.2.0 release governance
  -> G3 merge/release certification
  -> G4 architecture branch and preserved-document restoration
  -> approved architecture completion
  -> implementation authorization
```

## Candidate release trains

| Release candidate | Capability outcome | WPs/increments | Required gate |
| --- | --- | --- | --- |
| v1.2.0 Data Fabric | certified canonical transactional foundation | existing P3 | G2/G3 only |
| Foundation follow-up | tenant/contract/connector evidence hardening | WP-001-005 / Increment 0-1 subset | architecture and engineering approval |
| Business Service Intelligence | trusted service registry and posture | WP-006-010 / Increments 1-2 | lighthouse acceptance and graph projection evidence |
| Governed Decisions | recommendation, approval, execution and outcome slice | WP-011-013 / Increment 3 | ADRs, security, rollback and outcome verification |
| Cross-domain Intelligence | financial, portfolio and risk decisions | WP-014/015/019 / Increment 4 | domain owner and value evidence |
| Enterprise Memory & AI | reviewed Learning and evaluated reasoning | WP-016/017 / Increment 5 | AI/data governance and evaluation gate |
| Governed Orchestration | bounded action plus enterprise operations | WP-018-020 / Increment 6 | autonomy authorization and platform certification |

These are planning containers, not promises. Product Governance may re-scope them while preserving DAG dependencies and architectural invariants.

## Release gate minimums

Approved scope/ADRs, backward compatibility, complete dependencies, security/tenant tests, contract/collection/full tests, performance/cost evidence, migration and rollback, observability/runbooks, documentation, recovery, known debt and named release authority.

## Rollout

Use tenant-safe feature exposure, internal/lighthouse cohorts, canary or phased rollout, explicit success/rollback thresholds and post-release outcome review. The same immutable artifact progresses across environments. Schema changes use expand/contract compatibility and rehearsed recovery.

## Versioning rule

Breaking public contract or canonical semantic changes require explicit version and migration governance. Internal deployment decomposition alone does not justify a major product version. Marketing names never override technical compatibility evidence.

## Baseline protection

The v1.2.0 release is not bundled with P5 planning or future architecture. No future work package may modify its historical certification evidence.

