# ADR-012: Data Lineage

Status: Proposed
Date: 2026-07-09
Program: P3 Enterprise Data Fabric & Intelligence Platform

## Context

Nexora decisions must be explainable. Leaders need to understand where a KPI, graph relationship, recommendation, or risk signal came from and how it moved through the platform.

## Decision

Track lineage across the full enterprise intelligence path:

```text
Connector
  -> Raw Record
  -> Normalized Record
  -> Canonical Entity
  -> Knowledge Graph
  -> Dashboard
  -> AI Recommendation
  -> Executive Decision
```

## Rules

- Every canonical entity links to its source records.
- Every relationship links to evidence and derivation method.
- Every AI recommendation identifies consumed entities, relationships, and quality posture.
- Every dashboard metric can identify its upstream data products.

## Consequences

Dashboards become auditable, AI becomes explainable, and governance can review not only the answer but the path that produced it.
