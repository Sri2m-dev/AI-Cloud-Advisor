# Architecture Decision Index

Status: Active architecture governance index  
Owner: Nexora Architecture Governance  
Purpose: Maintain the authoritative index of Architecture Decision Records for Nexora platform releases.

## Purpose

This document is the release-level index for Nexora Architecture Decision Records (ADRs). It helps engineers, architects, and stakeholders understand which architectural decisions are accepted, which release introduced them, and where to find the decision record.

ADRs remain the source of truth for the detailed decision, context, consequences, and future implications. This index is a navigation and governance artifact only.

## ADR Index

| ADR | Title | Status | Release / Program | Location |
| --- | --- | --- | --- | --- |
| ADR-001 | Shared Platform Framework | Accepted | v1.0.0 Enterprise Foundation | `docs/architecture/ADR-001-Shared-Platform-Framework.md` |
| ADR-002 | Enterprise Financial Model | Accepted | v1.0.0 Enterprise Foundation | `docs/architecture/ADR-002-Enterprise-Financial-Model.md` |
| ADR-003 | Knowledge Graph | Accepted | v1.0.0 Enterprise Foundation | `docs/architecture/ADR-003-Knowledge-Graph.md` |
| ADR-004 | Digital Twin | Accepted | v1.0.0 Enterprise Foundation | `docs/architecture/ADR-004-Digital-Twin.md` |
| ADR-005 | Certification Framework | Accepted | v1.0.0 Enterprise Foundation | `docs/architecture/ADR-005-Certification-Framework.md` |
| ADR-006 | Caching Strategy | Accepted | v1.0.0 Enterprise Foundation | `docs/architecture/ADR-006-Caching-Strategy.md` |
| ADR-007 | Universal Connector Framework | Accepted | v1.1.0 Universal Connectors | `docs/architecture/ADR-007-Universal-Connector-Framework.md` |
| ADR-008 | Enterprise Data Fabric | Accepted | P3 Enterprise Data Fabric | `docs/architecture/ADR-008-Enterprise-Data-Fabric.md` |
| ADR-009 | Canonical Entity Model | Accepted | P3 Enterprise Data Fabric | `docs/architecture/ADR-009-Canonical-Entity-Model.md` |
| ADR-010 | Enterprise Semantic Layer | Accepted | P3 Enterprise Data Fabric | `docs/architecture/ADR-010-Enterprise-Semantic-Layer.md` |
| ADR-011 | Identity Resolution | Accepted | P3 Enterprise Data Fabric | `docs/architecture/ADR-011-Identity-Resolution.md` |
| ADR-012 | Data Lineage | Accepted | P3 Enterprise Data Fabric | `docs/architecture/ADR-012-Data-Lineage.md` |
| ADR-013 | Provenance Framework | Accepted | P3 Enterprise Data Fabric | `docs/architecture/ADR-013-Provenance-Framework.md` |
| ADR-014 | Versioning Strategy | Accepted | P3 Enterprise Data Fabric | `docs/architecture/ADR-014-Versioning-Strategy.md` |
| ADR-015 | Data Quality Framework | Accepted | P3 Enterprise Data Fabric | `docs/architecture/ADR-015-Data-Quality-Framework.md` |
| ADR-016 | Data Fabric Persistence Architecture | Accepted | P3 Enterprise Data Fabric | `docs/architecture/ADR-016-Data-Fabric-Persistence-Architecture.md` |
| ADR-017 | Production Data Fabric Persistence Adapter | Accepted | P3 Enterprise Data Fabric | `docs/architecture/ADR-017-Production-Data-Fabric-Persistence-Adapter.md` |

## Release Mapping

### v1.0.0 Enterprise Foundation

Foundational platform decisions:

- Shared Platform Framework
- Enterprise Financial Model
- Knowledge Graph
- Digital Twin
- Certification Framework
- Caching Strategy

### v1.1.0 Universal Connectors

Integration platform decision:

- Universal Connector Framework

### P3 Enterprise Data Fabric

Architecture-only decision package:

- Enterprise Data Fabric
- Canonical Entity Model
- Enterprise Semantic Layer
- Identity Resolution
- Data Lineage
- Provenance Framework
- Versioning Strategy
- Data Quality Framework
- Data Fabric Persistence Architecture
- Production Data Fabric Persistence Adapter

## Governance Rules

1. Every major architectural decision must have an ADR.
2. Every accepted ADR must be listed in this index.
3. Proposed ADRs may be listed before implementation when they define an approved architecture review package.
4. ADR status must be one of: `Proposed`, `Accepted`, `Superseded`, or `Rejected`.
5. Release notes and release manifests should reference accepted ADRs introduced by that release.
6. Implementation should not proceed for a major platform program until its governing ADR is accepted.

## Current Release Boundary

Current release-candidate state:

```text
v1.2.0 Data Fabric candidate
Branch: feature/p3-supabase-live-validation
Status: P3.10 certification; unmerged and untagged
Engineering: Frozen outside certification work
```

ADR-008 through ADR-017 are accepted and their P3 foundation scope is implemented and live validated. Broader runtime adoption and intelligence evolution remain blocked pending the post-release architecture review.

## P3 Architecture Boundary

The P3 architecture package is:

```text
ADR-008 through ADR-017
Status: Accepted for the implemented P3 foundation contract
Program: P3 Enterprise Data Fabric
Scope: Foundation implemented; relationship-version history deferred under migration 0018
```

ADR-008 should include the locked architectural invariant:

```text
Every enterprise concept should have exactly one canonical definition.
```

This invariant should govern the Enterprise Semantic Model, Enterprise Ontology, Canonical Models, Enterprise Data Fabric, Knowledge Graph, Digital Twin, Enterprise Financial Model, AI Reasoning, APIs, dashboards, and future AI agents.




