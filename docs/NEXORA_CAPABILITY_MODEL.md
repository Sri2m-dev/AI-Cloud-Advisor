# Nexora Capability Model

Status: Current capability map; implementation depth varies by capability
Program: P3 Enterprise Data Fabric & Intelligence Platform
Date: 2026-07-09

## Capability Groups

| Capability Group | Capabilities |
| --- | --- |
| Enterprise Data Fabric | Entity registry, relationship registry, identity resolution, lineage, provenance, versioning, data quality |
| Enterprise Architecture | Business capabilities, business services, applications, technologies, vendors, contracts, ownership |
| Knowledge Graph | Provider-agnostic graph, dependency analysis, impact analysis, relationship confidence |
| Semantic Layer | Ontology, source-to-enterprise mapping, aliases, taxonomy, provider-neutral resource classes |
| Connectors | AWS, Azure, GCP, ServiceNow, Jira, Microsoft 365, Datadog, GitHub, Salesforce, SAP, FinOps sources |
| Financial Intelligence | Cost centers, spend allocation, chargeback, forecasting, optimization, savings governance |
| SaaS Governance | SaaS inventory, utilization, license optimization, vendor risk, contract intelligence |
| AI Intelligence | Root cause analysis, impact analysis, what-if simulation, prediction, recommendations, executive narratives |
| Governance | Policies, approvals, evidence, risk, controls, audit posture |
| Operations | Connector health, scheduler operations, observability, incident timeline, execution center |

## Capability Dependencies

```text
Connectors
  -> Data Fabric
  -> Semantic Layer
  -> Knowledge Graph
  -> Data Quality
  -> AI Intelligence
  -> Dashboards and Decisions
```

## P3 Foundation Delivery

Implemented and validated in P3: architecture and ADRs, canonical entity and relationship contracts, identity resolution, lineage, provenance, semantic ontology, data quality, versioning, persistence, and atomic Supabase RPC behavior.

Knowledge Graph v2, enterprise-wide API adoption, and the broader AI intelligence layer are roadmap capabilities, not implied P3 runtime deliverables.

## Guardrails

- No direct dashboard dependency on source-specific connector payloads after migration.
- No provider-specific logic in the core fabric.
- No AI recommendation without entity, relationship, lineage, provenance, and quality context.
- No new implementation before the post-release architecture review.
