# Architecture Snapshot

## Release boundary

The v1.3.0 baseline combines the Enterprise Foundation, Universal Connector Framework,
Enterprise Data Fabric, Cloud Account Registry, governed account resolution, and the
Enterprise Classification Engine. Accepted architectural decisions remain indexed by
`docs/ARCHITECTURE_DECISION_INDEX.md`; the tagged tree contains ADR-001 through ADR-020
(except ADR-021), ADR-022, ADR-023, and ADR-024.

The active layers are:

1. Streamlit persona workspaces and API surfaces.
2. Authentication, normalized RBAC, and authenticated tenant context.
3. Domain services and runtime repository composition.
4. Canonical registries, classification, account resolution, and financial services.
5. Enterprise Data Fabric identity, registry, semantic, lineage, provenance, quality,
   versioning, and persistence packages.
6. SQLite development persistence and tenant-scoped Supabase production persistence.

## Canonical enterprise registry

The release contains one governed registry direction rather than parallel frameworks:

- `enterprise_registry/` provides the enterprise metadata registry contracts, models,
  repository, service, and EMRP closure behavior.
- `data_fabric/registry/entity_registry.py` provides canonical entity registration in
  the Data Fabric.
- FG-001 Cloud Account Registry preserves provider/account identity, tenant scope,
  lifecycle, uniqueness, CRUD, import/export, and RBAC.
- FG-002 Account Resolution extends that registry with governed mapping changes,
  explicit reasons, version/audit preservation, reversibility, duplicate protection,
  financial posture propagation, and unchanged raw CUR facts.

P4.3 may expand asset types only through these canonical boundaries. It must not create
a second registry, relationship graph, allocation model, or identity scheme.

## Enterprise Classification Engine

`classification_engine/` owns models, source extraction, evidence, confidence scoring,
policy, persistence, and orchestration. The engine records field-level value,
confidence, method, evidence, and approval state; detects conflicts; supports governed
approval; and integrates with account resolution and the existing registry.

Automatic classification is evidence-driven. Low-confidence or conflicting values stay
governed and reviewable. Owner is optional where the released policy permits it. No
hardcoded tenant mappings or authentication bypasses exist.

## Stable data and financial invariants

- Raw CUR facts are immutable inputs.
- Account resolution changes governed mappings and derived posture, not raw facts.
- Total cloud spend and reconciliation remain exact across classification changes.
- Tenant/provider/account identity is unique within the released constraints.
- Version, evidence, lineage, audit, and rollback semantics remain first-class.

This snapshot is descriptive only; it introduces no P4.3 functionality.
