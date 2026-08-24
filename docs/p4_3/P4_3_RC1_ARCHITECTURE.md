# P4.3 Enterprise Intelligence RC1 Architecture

```mermaid
flowchart LR
    Sources[Authoritative domain stores] --> Registry[Enterprise Registry]
    Sources --> Financial[Financial Data Fabric]
    Sources --> Classification[Classification Engine]
    Registry --> Relationships[Relationship Intelligence]
    Relationships --> Graph[Enterprise Knowledge Graph]
    Registry --> Graph
    Financial --> Graph
    Classification --> Graph
    Graph --> Query[Intelligence Query Engine]
    Query --> Search[Enterprise Search]
    Query --> Copilot[Enterprise AI Copilot]
    Query --> Decision[Decision Intelligence]
    Registry --> Scenario[Scenario Intelligence]
    Relationships --> Scenario
    Financial --> Scenario
    Scenario --> Copilot
    Scenario -. non-authoritative evidence .-> Decision
    Decision -. WP-010 package required .-> WP11[WP-011 Human Decision]
    WP11 --> WP12[WP-012 Policy Evaluation / Authorization]
    WP12 --> WP13[WP-013 Execution / Verified Outcome]
```

All solid P4.3 edges through Scenario and Copilot are reads. The dotted scenario
edge cannot create a Decision; explicit WP-010 packaging is required. No P4.3
presentation or reasoning service owns provider-write credentials or an execution
interface.

## Evidence flow

```mermaid
flowchart TD
    Fact[Authoritative fact + tenant] --> Canonical[Canonical identity/version]
    Canonical --> Edge[Governed relationship + evidence]
    Edge --> Context[Query/search/graph context]
    Context --> Derived[Finding or scenario result]
    Derived --> Explain[Copilot/executive explanation]
    Derived -. explicit packaging .-> Package[WP-010 evidence package]
```

At every derivation boundary the platform preserves tenant, canonical reference,
confidence, evidence or source reference, partial state, unknowns, and freshness
where supported.

## Runtime composition

Composition roots construct registry, relationships, graph, query, search, scenario,
and Copilot services. RC1 closes the previous optional-wiring gap by supplying
`ScenarioService` through the standard Copilot composition. This does not broaden
Copilot authority; it exposes only `simulate()` and deterministic explanation.
