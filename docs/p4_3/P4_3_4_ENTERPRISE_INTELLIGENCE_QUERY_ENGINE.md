# P4.3.4 Enterprise Intelligence Query Engine

## Architecture

The engine is the tenant-scoped read-side boundary above the Canonical Enterprise
Registry, Relationship Intelligence, Enterprise Knowledge Graph, Classification
Engine, and Financial Data Fabric. It performs deterministic READ / REASON /
EXPLAIN operations only. It has no write, approval, policy authorization, or
execution interface and does not persist a parallel graph or financial model.

`UI / future API / future AI -> EnterpriseIntelligenceService -> governed domain services`

## Contracts and query taxonomy

`QueryRequest` carries tenant context, a named query type, canonical entity
reference, filters, temporal context, depth/result bounds, and inclusion flags.
`QueryResponse` keeps facts separate from derived findings and returns context,
paths, evidence, lineage, provenance, confidence, freshness, partial-result
reasons, version references, and a deterministic narrative.

Named queries cover enterprise context, explanation, dependencies, dependents,
business and financial impact, ownership, technology, application, service,
risk, health, governance, and read-only change impact. Bounded inventory queries
cover unowned, unclassified, conflicted, high-cost, high-risk, and
business-critical entities.

## Explainability and temporal semantics

Facts cite their authoritative source and canonical version. Classification
findings are labelled `DERIVED` and carry method, confidence, evidence IDs, and
classification version. Context dimensions explicitly report `AVAILABLE`,
`STALE`, `MISSING`, or `UNSUPPORTED`. Historical reconstruction is not claimed:
an `as_of` request currently returns an explicit unsupported partial response.

## Limits and security

Default bounds are depth 5, 100 results, fan-out 50, work budget 1,000, and a
2-second timeout disclosure. Truncation is explicit. Underlying relationship
traversal remains cycle-safe. `TenantContext` is mandatory and cross-tenant
requests are rejected before data access. Existing read personas are enforced;
raw evidence is limited to administrators and auditors. The response contains no
secrets or raw database rows. No cache is introduced, so cross-tenant cache
isolation is not applicable.

## Financial invariants

Financial context is reused from the Financial Data Fabric. The engine performs
no mutation or recomputation of CUR facts, total spend, allocations, quarantine,
or reconciliation. Therefore querying cannot change the financial posture.

## DEV certification target

The controlled DEV acceptance entity remains AWS account `727482365532`,
canonical ID `cloud_account:e099f2ab-32d7-5f50-b03a-364c78d60098`.
Expected evidence is identity and financial context, classification findings only
when present in the authoritative classification repository, unknown business
dimensions where absent, and zero relationship-derived impact while no governed
edges exist. Reference financial posture is account spend 37,143.2080151701 USD,
enterprise spend 127,678.2170275708 USD, 786,745 CUR facts, and zero USD
reconciliation variance. These values are certification assertions, not seeded
or fabricated query data.

## Browser acceptance matrix

Manual release evidence must capture Overview, the DEV account context,
explainability/evidence, Financial Impact, zero-path Dependency/Business Impact,
missing/unknown context, and a read-only persona. Automated Streamlit testing
certifies safe local empty-state rendering without Supabase.

## Known limitations

- Historical reconstruction is unsupported until every contributing domain has
  governed temporal snapshots.
- Risk, operations, budget, forecast, and savings context remains missing when no
  authoritative provider supplies it.
- Topology answers are intentionally incomplete where governed relationships are
  absent.
- Natural-language/LLM interpretation is deferred; deterministic contracts remain
  the source of truth.
