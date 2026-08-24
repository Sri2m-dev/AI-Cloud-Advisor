# P4.3 RC1 Contract Freeze

Release candidate: **v1.4.0 Enterprise Intelligence RC1**
Freeze baseline: `0a3247144bbcf82fcd96afbd5ac0dc67fd24b4bc`

The following public contracts are frozen for the v1.4.0 release candidate.
Additive, backward-compatible changes require tests and release-note updates.
Renames, field removals, semantic changes, authority expansion, and persistence
ownership changes require an ADR and a new release authorization.

| Layer | Frozen public contracts | Ownership |
|---|---|---|
| Registry | `EnterpriseEntity`, `EnterpriseRegistryService`, canonical adapters | Canonical identity/read projection; domain stores remain authoritative. |
| Relationships | `RelationshipPath`, `ImpactSummary`, `RelationshipIntelligenceService` | Evidence-backed traversal only. |
| Knowledge | `KnowledgeNode`, `KnowledgeAnswer`, `EnterpriseKnowledgeGraphService` | Read-only composition over registry and relationships. |
| Query | `QueryRequest`, `QueryResponse`, `QueryType`, `EnterpriseContext` | Bounded deterministic read/reason/explain. |
| Search | `SearchRequest`, `SearchResult`, `SearchResponse` | Ranked discovery with persona-filtered dimensions. |
| Copilot | `CopilotRequest`, `CopilotContext`, `CopilotResponse`, `EnterpriseAIOrchestrator` | Explanation only; no decision or authority. |
| Decision intelligence | `IntelligenceFinding`, `RecommendationProposal`, `DecisionIntelligenceService` | Findings and proposals; WP-011 owns Decisions. |
| Scenario | `ScenarioRequest`, `ScenarioResult`, `ScenarioComparison`, `ScenarioService` | Ephemeral, non-authoritative analysis; no execution port. |

## Stability rules

- `TenantContext` remains mandatory at every public request/service boundary.
- Canonical IDs and version/checkpoint references remain the cross-layer identity.
- Evidence, confidence, freshness, partial state, and unknowns may not be silently dropped.
- Empty governed topology must remain explicit; no layer may infer a blast radius.
- Potential value may not be presented as approved, executed, or verified realized value.
- Scenario, Copilot, Finding, and Recommendation Proposal outputs provide no authority.
- Production composition remains fail-closed when authoritative configuration is absent.

## Compatibility surfaces

The Business Service registry and canonical Enterprise Registry are not duplicate
authorities: the former owns its domain lifecycle and the latter projects canonical
identity. Legacy Simulation Center and governed Scenario Intelligence temporarily
coexist; new consumers use Scenario Intelligence, while removal of the legacy page
is deferred to a separately authorized breaking release.
