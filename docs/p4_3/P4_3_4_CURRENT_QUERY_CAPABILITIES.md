# P4.3.4 Current Query Capabilities

Status: discovery completed before Query Engine implementation
Baseline HEAD: `301caaf2a4dff670eb82b04c81a2fc6729f81227`

| Capability | Active implementation | Classification | P4.3.4 treatment |
| --- | --- | --- | --- |
| Canonical entity search/detail | `EnterpriseRegistryService` | REUSE | Authoritative identity, classification, financial, lineage, provenance, versions |
| Evidence-backed traversal/impact | `RelationshipIntelligenceService` | REUSE | Authoritative dependency, dependent, owner, consumer, provider, impact paths |
| Canonical graph explanation/path | `EnterpriseKnowledgeGraphService` | REUSE | Projection/explanation boundary and financial-context reference |
| Financial posture/reconciliation | `EnterpriseSpendService` and Financial Data Fabric RPCs | REUSE | Authoritative facts; never recompute or persist |
| Business Service registry/posture | `BusinessServiceService` and registry contracts | ADAPT | Consume only when canonical references are available |
| Classification inference/current results | P4.2 repositories/services | REUSE | Preserve fact/inference/approval distinctions and evidence versions |
| P3 lineage/provenance/version stores | Data Fabric contracts/adapters | REUSE | Reconstructable answer references |
| Dependency Analysis page/service | legacy direct graph repositories | DEPRECATE-LATER | Future consumer of Query Engine; do not delete in P4.3.4 |
| Impact Analysis page/service | legacy multi-table impact repository | DEPRECATE-LATER | Future consumer; governed Query Engine replaces cross-domain reasoning |
| Legacy Knowledge Graph service/repository | name-based static/table graph | DEPRECATE-LATER | Not authoritative; governed page already uses P4.3.3 projection |
| Enterprise graph builder/cache | multi-table name projection | DEPRECATE-LATER | No longer used by governed Enterprise Knowledge Graph page |
| Technology Copilot / AI Copilot | prompt/model-oriented consumers | OUT-OF-SCOPE | P4.3.5+ may consume stable QueryResponse; no LLM in P4.3.4 |
| AI Reasoning service | recommendation/reasoning dashboard | OUT-OF-SCOPE | Authority chain remains separate from read-side query |
| Executive dashboard narratives | page/service-specific summaries | ADAPT | Later consume deterministic QueryResponse narratives |
| Technology health/risk services | domain-specific posture | ADAPT | Expose canonical references when available; otherwise explicit MISSING/UNSUPPORTED |
| Platform health | platform operations status | OUT-OF-SCOPE | Not automatically attributed to canonical enterprise entities |
| Approval/policy/execution services | governed authority services | OUT-OF-SCOPE | Query Engine may disclose permitted references only; no approve/authorize/execute API |

## Discovery conclusion

The active platform has many useful but overlapping query surfaces. P4.3.4 must not
wrap their direct table reads into another facade. The canonical Query Engine composes
P4.3.1 through P4.3.3 plus Financial Data Fabric and returns one bounded, tenant-scoped,
persona-filtered response contract. Older consumers remain intact for compatibility and
can migrate later.
