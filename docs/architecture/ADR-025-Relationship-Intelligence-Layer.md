# ADR-025: Relationship Intelligence Layer

Status: Accepted by P4.3 Master Engineering Program
Date: 2026-08-12
Program: P4.3.2 Relationship Intelligence

## Decision

Relationship Intelligence composes the released P3 `EnterpriseRelationship`,
`RelationshipRegistry`, canonical entity identity, and Data Fabric persistence. It
does not create a parallel graph or relationship table. The existing
`data_fabric.enterprise_relationships` store remains authoritative in Supabase;
SQLite supplies the development fallback.

Every relationship requires tenant scope and evidence. Source, confidence, evidence,
discovery time, last validation, lineage, provenance, and version are exposed through
the P3 contract. Flexible evidence remains in the existing governed metadata column.
No migration is required.

## Query model

The intelligence service supplies direct inbound/outbound queries, bounded or
unbounded breadth-first traversal with cycle protection, dependency, owner, consumer,
provider, impact, and blast-radius operations. Rule-based executive narratives are
derived only from traversed governed edges.

```text
AuthenticatedTenantContext
        -> runtime composition
        -> canonical Enterprise Registry entities
        -> P3 enterprise_relationships repository
        -> Relationship Intelligence Service
        -> Relationship Explorer / future intelligence consumers
```

## Security and consequences

- Both organization and tenant predicates are mandatory.
- Production fails closed without valid Supabase configuration.
- Read-only personas cannot mutate relationships.
- An edge without evidence is rejected rather than inferred.
- Missing endpoints and relationships remain explicit unknowns.
- Dashboards consume the service and do not implement graph logic.
