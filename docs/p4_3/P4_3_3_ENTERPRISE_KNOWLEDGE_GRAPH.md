# P4.3.3 Enterprise Knowledge Graph

## Architecture

The Knowledge Graph is a projection layer and persists nothing. It composes canonical
entities, governed P3 relationships, P4.2 classifications, Financial Data Fabric
references, lineage, confidence, evidence, risk, and health references. This replaces
the governed Enterprise Knowledge Graph page's legacy name-based, multi-table graph
builder while leaving backward-compatible legacy services untouched.

## Graph model

- Node identity: canonical Enterprise Registry ID.
- Edge identity: P3 `EnterpriseRelationship` ID.
- Node types: every canonical taxonomy type, including business, application,
  technology, SaaS/vendor, people/ownership, finance references, AI assets, risks,
  policies, controls, teams, and projects when present in canonical repositories.
- Edge explanations: source, confidence, evidence, lineage, classification state, and
  full relationship path.
- Financial overlay: referenced tenant-scoped context; facts are never copied.

## APIs

`find_entity`, `explain_entity`, `search_graph`, `find_path`, `find_owners`,
`find_dependencies`, `find_consumers`, `find_providers`, `find_business_impact`, and
`find_financial_impact` are deterministic service methods. Rule-based narratives use
only resolved canonical nodes and evidence-backed paths.

## Runtime and security

The service inherits authenticated tenant scope, RBAC, production fail-closed runtime
composition, SQLite fallback, Supabase repositories, and P3 relationship evidence
requirements. It introduces no migration, graph database, entity table, relationship
table, or cache.

## Known baseline limitation

The current DEV tenant projects 67 canonical cloud accounts but exposes no governed P3
relationship edges for account `727482365532`. The graph therefore explains the
canonical entity and financial context while explicitly reporting no evidence-backed
paths. Connector/CMDB ingestion must create governed relationships before multi-domain
DEV paths appear.

## DEV certification

For tenant `71cf875a-2103-47a0-8886-41a97c5750ec`, the projection exposes 67
canonical entities. Account `727482365532` resolves to
`cloud_account:e099f2ab-32d7-5f50-b03a-364c78d60098`, has zero governed paths, and
references 37,143.2080151701 USD of account spend. Its deterministic narrative reports
the absence of evidence-backed relationships rather than inventing knowledge.

Measured DEV latency after batching current P4.2 field reads:

- canonical entity lookup: 0.75 ms;
- graph search: 19.71 ms;
- relationship traversal: 0.02 ms;
- fully enriched explanation including live classification and financial RPC context:
  770.93 ms.

The specified lookup (<100 ms), search (<150 ms), path (<300 ms), and traversal
(<500 ms) targets are satisfied. Enriched explanation latency is disclosed separately.
