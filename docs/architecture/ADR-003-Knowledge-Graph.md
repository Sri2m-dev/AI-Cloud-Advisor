# ADR-003: Knowledge Graph

Status: Accepted
Date: 2026-07-05
Release: v1.0.0-enterprise-foundation

## Context

Nexora needed to connect business units, capabilities, services, applications, technologies, costs, risks, owners, and recommendations. Isolated dashboards could not support impact analysis, dependency reasoning, or business-aware technology decisions.

## Decision

Treat the Knowledge Graph as a core intelligence engine rather than a single page feature.

P4.3.3 clarification: the Enterprise Knowledge Graph is a read-only projection over
canonical P3 entities, P4.2 classifications, P3 relationships/P4.3.2 traversal, and
Financial Data Fabric references. It must not own or cache duplicate nodes, edges, or
financial facts. Canonical IDs are graph node identities; P3 relationship IDs are edge
identities. Legacy name-based graph services are not authoritative for the governed
Enterprise Knowledge Graph route.

The Knowledge Graph supports:

- Business-to-technology relationships
- Dependency exploration
- Blast-radius analysis
- Impact analysis
- Relationship coverage
- Evidence-backed intelligence across workspaces

## Options Considered

1. Keep relationships embedded in page-specific queries.
2. Add relationship tables but no dedicated graph service.
3. Establish a Knowledge Graph service and certification layer.

## Rationale

Relationship intelligence is foundational to executive decision support, digital twins, AI reasoning, and enterprise architecture. Centralizing the graph prevents each page from inventing its own relationship model.

## Consequences

- Pages should consume graph intelligence through services.
- Business Architecture, Technology Digital Twin, Application Inventory, and CIO Dashboard can all build on the same relationship base.
- Graph confidence and relationship coverage become platform-level quality indicators.

## Future Considerations

- Expand graph relationships through E8 Data Fabric connectors.
- Add graph-based AI reasoning.
- Add historical relationship changes and confidence scoring.

## P4.3.3 Sequence

```text
Authenticated persona
  -> Enterprise Knowledge Graph page
  -> Knowledge Graph composition
  -> Canonical Enterprise Registry
  -> Relationship Intelligence traversal
  -> Classification + financial context references
  -> evidence-bearing explanation/path/impact response
```
