# ADR-008: Enterprise Data Fabric

Status: Accepted — P3 foundation implemented and validated
Date: 2026-07-09
Program: P3 Enterprise Data Fabric & Intelligence Platform

## Context

Nexora has evolved beyond cloud cost optimization into an Enterprise Technology Intelligence Platform. Existing capabilities now include Technology Inventory, Business Services, Knowledge Graph, AI, SaaS Governance, Cost Optimization, and Universal Connectors.

If each capability continues to read connector-specific tables or page-specific repositories directly, the platform will accumulate duplicate entity definitions, inconsistent lineage, and provider-specific logic in places that should remain enterprise-neutral.

## Decision

Introduce an Enterprise Data Fabric as the canonical data foundation for all enterprise intelligence capabilities.

The Data Fabric will own:

- Canonical enterprise entities
- Canonical enterprise relationships
- Identity resolution
- Semantic normalization
- Lineage and provenance
- Versioning
- Data quality signals
- Provider-agnostic access APIs

Every enterprise concept should have exactly one canonical definition.

## Design Principles

- Provider-specific logic belongs in connectors and normalization adapters, not in the fabric core.
- Dashboards, AI, graph, and reporting consume canonical entities and relationships.
- Source records remain traceable through raw, normalized, canonical, graph, dashboard, recommendation, and decision layers.
- The fabric is additive and backward-compatible during migration.
- P1/P2 dashboards and connectors remain unchanged until fabric APIs are validated.

## Consequences

- New connector output must map to canonical entities before powering enterprise intelligence.
- Existing services may temporarily bridge legacy tables to fabric concepts.
- Knowledge Graph v2 becomes provider-agnostic.
- AI recommendations become explainable through entity, relationship, lineage, provenance, and quality evidence.

## Non-Goals

- No service implementation in Phase 1.
- No dashboard migration in Phase 1.
- No production sync path replacement in Phase 1.
