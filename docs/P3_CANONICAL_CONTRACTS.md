# P3 Canonical Contracts

Status: Implemented P3 canonical contract baseline
Program: P3.2 Canonical Enterprise Model Contracts
Scope: Contracts only; no runtime, dashboard, connector, database, or Supabase behavior changes.

## Purpose

The P3 canonical contracts define the provider-neutral data model that future Enterprise Data Fabric services will consume. They are intentionally lightweight and inert so the existing P1/P2 platform remains unchanged while the canonical model is reviewed.

## Package

```text
data_fabric/
  contracts/
    entity.py
    relationship.py
    identity.py
    lineage.py
    provenance.py
    versioning.py
    quality.py
    ownership.py
    enums.py
```

## Contract Names

- `EnterpriseEntity`
- `EnterpriseRelationship`
- `EntityIdentity`
- `EntityLineage`
- `EntityProvenance`
- `EntityVersion`
- `EntityQuality`
- `EntityOwnership`
- `EntityType`
- `RelationshipType`

## Common Entity Fields

`EnterpriseEntity` includes the common P3 metadata required by ADR-009:

- `id`
- `canonical_id`
- `entity_type`
- `name`
- `source_system`
- `source_identifier`
- `organization_id`
- `tenant_id`
- `created_at`
- `updated_at`
- `version`
- `confidence_score`
- `quality_score`
- `tags`
- `metadata`

## Entity Types

The first canonical entity type set is:

```text
business_capability
business_service
application
technology
cloud_resource
saas_application
vendor
contract
cost_center
department
owner
project
environment
business_process
risk
recommendation
approval
policy
evidence
```

## Relationship Types

The first canonical relationship type set is:

```text
depends_on
runs_on
owned_by
supplied_by
funds
impacts
targets
monitors
governs
approves
evidences
associated_with
```

## Non-Goals

P3.2 does not introduce:

- Dashboard changes
- Connector runtime changes
- Database migrations
- Supabase writes
- Knowledge Graph v2 integration
- Identity resolution execution logic

Those will follow only after the contract baseline is reviewed.
