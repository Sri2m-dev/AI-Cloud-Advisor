# P4.3.5 Current Search Capabilities

| Capability | Classification | P4.3.5 treatment |
|---|---|---|
| Canonical Enterprise Registry `search_entities` | REUSE | Tenant-scoped source enumeration and identity fields |
| Enterprise Knowledge Graph `search_graph` | REUSE | Governed canonical projection; no new index |
| Relationship Intelligence search/traversal | REUSE | Optional governed relationship expansion |
| Enterprise Intelligence Query Engine | REUSE | Lazy result enrichment and persona/evidence policy |
| Enterprise Registry page search | ADAPT | Remains active; Enterprise Search becomes cross-domain entry point |
| Enterprise Graph page search | ADAPT | Remains graph-focused and is not replaced in this increment |
| Technology/Application/SaaS/Business Service page filters | DEPRECATE-LATER | Domain-local UX remains active pending consumer migration |
| Entity Registry legacy repository search | DEPRECATE-LATER | Parallel legacy surface is not used as search authority |
| Sidebar/topbar text input | ADAPT | Presentation control only; no governed retrieval contract today |
| Technology Copilot and AI lookup logic | OUT-OF-SCOPE | No LLM or copilot ranking is introduced |
| Digital Twin and incident search indexes | OUT-OF-SCOPE | Domain-specific operational projections |

No existing surface is deleted. The new search service enumerates canonical
entities through the existing Knowledge Graph/Registry projection and enriches
only bounded results through Enterprise Intelligence.
