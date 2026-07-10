# P3 Semantic Model and Ontology Interfaces

P3.8 introduces provider-agnostic semantic model and ontology interfaces for mapping source-specific technology terms into canonical enterprise concepts. The implementation is deterministic and in-memory only.

## Architecture

The package is isolated under `data_fabric/semantic`:

- `OntologyRegistry` manages canonical concepts and concept relationships.
- `SemanticMapper` resolves source terms and canonical entities to semantic concepts.
- `TaxonomyService` manages hierarchical taxonomy nodes.
- `OntologyValidator` validates tenant-scoped ontology consistency.

Reference implementations are in-memory and tenant-partitioned. No persistence, connector/runtime integration, dashboard changes, Knowledge Graph v2 wiring, schedulers, or migrations are included.

## Concepts And Relationships

`SemanticConcept` models provider-agnostic concepts such as compute, storage, database, observability, managed services, vendors, capabilities, and business services. Concepts include canonical names, display names, descriptions, synonyms, aliases, attributes, organization and tenant context, version, and active state.

`ConceptRelationship` supports relationship types such as `is_a`, `part_of`, `equivalent_to`, `related_to`, `depends_on`, `provided_by`, `implemented_by`, `supports`, `supersedes`, and `conflicts_with`.

## Taxonomy Model

`TaxonomyNode` links concepts into tenant-scoped taxonomies. The in-memory service supports root/child listing, moves, removal, search, path lookup, and cycle detection.

## Semantic Mapping Lifecycle

`SemanticMapping` stores explicit source-system mappings. `InMemorySemanticMapper` can resolve terms through:

- explicit source-specific mappings
- exact canonical-name matches
- exact synonym and alias matches
- normalized-term matches
- attribute-assisted matches

Results include candidates, confidence, decision, and explanation. Ambiguous candidates are returned explicitly.

## Mapping Confidence And Ambiguity

Confidence is constrained to `0-100`. Candidate ordering is stable by confidence, canonical name, and concept id. Multiple top-scoring candidates produce an `ambiguous` result. No active candidates produce a `no_match` result.

## Inheritance Behavior

Concept attributes can be inherited from ancestors. Attribute inheritance walks ancestors from root to child, and child attributes override inherited values. The effective attribute view includes an explanation of where each attribute came from. Cycles are rejected or reported before traversal can loop indefinitely.

## Validation Rules

Validation and registry rules cover required ids and names, uniqueness within tenant, synonym collisions, parent existence, self-parent rejection, hierarchy cycles, endpoint validation, contradictory equivalent/conflicting relationships, confidence range validation, inactive concept exclusion, and tenant context preservation.

## Tenant Isolation

Concepts, mappings, relationships, and taxonomies are partitioned by `organization_id` and `tenant_id`. Identical concept names can exist in separate tenants. Cross-tenant lookup returns no result and candidate generation does not mix tenant data.

## Extension Model

Provider-specific mapping strategy should be injected as mappings or future provider rule packs. Core ontology concepts remain provider-agnostic and do not hardcode dashboard-specific interpretations.

## Reference Examples

The test/reference mapping set covers:

- AWS EC2, Azure Virtual Machines, and GCP Compute Engine to Virtual Machine
- AWS S3, Azure Blob Storage, and Google Cloud Storage to Object Storage
- Amazon RDS, Azure SQL Database, and Google Cloud SQL to Managed Relational Database
- Amazon EKS, Azure Kubernetes Service, and Google Kubernetes Engine to Managed Kubernetes
- Amazon CloudWatch, Azure Monitor, and Google Cloud Monitoring to Cloud Monitoring

These mappings are demonstration data only and are not wired into connectors.

## Limitations

- No persistence or Supabase/database writes.
- No migrations.
- No connector/runtime integration.
- No dashboard changes.
- No Knowledge Graph v2 wiring.
- No generation of `EnterpriseRelationship` records.
- No integration with identity resolution yet.
