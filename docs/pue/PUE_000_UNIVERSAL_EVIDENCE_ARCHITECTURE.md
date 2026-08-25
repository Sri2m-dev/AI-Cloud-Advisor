# PUE-000 Universal Evidence Architecture

## Status and authority

PUE-000 defines architecture and contract invariants only. It changes no production behavior,
storage, upload processing, UI, session state, connector, or canonical repository. The certified
prospect intake remains authoritative; PUE begins as an observational shadow pipeline.

## Governing boundary

Nexora preserves four non-interchangeable stages:

1. **Observed source structure** records reproducible physical facts.
2. **Interpreted semantics** records candidate meanings, confidence, method, and ambiguity.
3. **Governed normalized evidence** records values mapped through an approved mapping policy.
4. **Derived/query results** use only governed normalized evidence and retain input lineage.

The invariant is:

```text
RAW EVIDENCE
  -> PROFILE WHAT EXISTS
  -> DISCOVER POSSIBLE MEANING
  -> CLASSIFY WITH CONFIDENCE
  -> REQUIRE CONFIRMATION WHERE NEEDED
  -> NORMALIZE ONLY GOVERNED MAPPINGS
  -> DERIVE ONLY SUPPORTED RESULTS
  -> ANSWER ONLY EVIDENCE-SUPPORTED QUERIES
```

A raw header or value is never itself a business meaning. `Service Name`, for example, may be
observed as a string header in Layer 1, but `technology.service` may appear only as a Layer 2
candidate. Provider or service conclusions are outside PUE-000.

## Layers

### Layer 0: source boundary

`EvidenceSource`, `EvidenceFile`, `EvidenceSheet`, `EvidenceColumn`, and
`EvidenceRowReference` identify the authorized source without semantics. Identity includes a
content hash and immutable source reference; it is distinct from prospect, organization, tenant,
and analysis identities. Raw evidence remains under the existing encryption and retention boundary.

### Layer 1: structural observation

`PrimitiveProfile` and `StructuralObservation` contain reproducible facts only: shape, headers,
primitive-type candidates, coverage, cardinality, lengths, mixed types, structural warnings, and
bounded safe samples. Future PUE-001 profiling includes duplicate headers/records, hidden sheets,
formulas, merged cells, suspicious headers, empty leading rows, encoding/delimiter warnings, and
sensitive-looking flags. It makes no semantic assignments.

### Layer 2: semantic interpretation

`SemanticCandidate` permits multiple meanings per source column. Each candidate carries a
`MappingConfidence`; `SemanticClassificationResult` carries a separate classification and
confirmation state. Policy, rather than a numeric score alone, decides whether an automatic mapping
is permitted. Ambiguity remains explicit.

### Layer 3: governed normalization

`SemanticMapping` identifies the concept/version, mapping/version, authority, confidence, and
confirmation record. `NormalizedEvidenceField` retains both source and normalized values plus
row-level provenance. Multiple source columns may map to one concept; a column may remain unmapped
or unresolved. No normalized field may exist without provenance.

### Layer 4: derived intelligence

`DerivedEvidenceResult`, `AggregationCapability`, and `QueryCapability` require governed inputs,
derivation rules, row scope, sufficiency, limitations, and provenance. Raw values cannot bypass
normalization. Recommendations, risks, relationships, decisions, and AI answers are future consumers,
not PUE-000 implementations.

## Isolation and lifecycle

Every PUE artifact has an `EvidenceAnalysisContext` containing distinct analysis, source, and
prospect identifiers plus optional organization and tenant identifiers. Authorization inherits the
current prospect boundary. No PUE artifact automatically enters canonical production stores.

PUE artifacts inherit source expiry. Purge must cover raw source, profiles, candidates,
confirmations, normalized temporary evidence, coverage, derived results, provenance references, and
analysis query history. Only an explicitly governed minimal audit tombstone may outlive source data.

## Security and privacy

- Raw values remain within the existing encrypted prospect boundary.
- Representative samples are bounded, access-controlled, and omitted or masked for sensitive fields.
- Logs and telemetry must never dump customer records or classifier inputs.
- Semantic engines receive an authorized analysis context only.
- Cross-tenant semantic memory is prohibited unless anonymized and separately governed.
- Purge includes all temporary derived artifacts.

## Coexistence architecture

```text
Authorized upload
  +-> existing validation/normalization/analysis/workspace (AUTHORITATIVE)
  +-> PUE source identity/profile (OBSERVATIONAL SHADOW)
```

PUE may compare results but cannot mutate, replace, or feed the existing analysis until a later
certification gate explicitly approves selected authority. The validated 184-row, 861,828-cost,
currency-provenance flow remains unchanged.

## Architectural decisions

1. Raw identity is the immutable authorized source reference plus content hash, file identity, and
   analysis-scoped source identity; tenant, prospect, and analysis IDs are not aliases.
2. Structural facts must be reproducible from source bytes; any possible meaning begins in Layer 2.
3. Concepts use hierarchical, versioned identifiers with definitions, primitive types, units, and
   cardinality expectations; customer aliases remain separate.
4. Candidate meanings coexist as an ordered collection; no single winner is required.
5. Confidence describes an engine signal; confirmation records a governed human/policy decision.
6. Automatic mapping is allowed only when configurable policy accepts the confidence band, method,
   classifier version, evidence inputs, concept risk, and ambiguity state.
7. Normalized evidence is governed only when mapping identity/version, authority, scope,
   confirmation, original value, and provenance are present.
8. Row provenance uses references or lineage expressions, not duplicated raw records.
9. Aggregates cite normalized record sets, source row sets, and a versioned derivation rule.
10. Query capability is evaluated before execution against governed measures, dimensions, linkage,
    units/currency, coverage, and confirmation.
11. Unresolved or mixed currency makes financial aggregation unsupported or confirmation-required.
12. Every object is analysis-scoped and inherits prospect/tenant authorization and demo isolation.
13. Retention cascades from source identity; dependent artifacts cannot become orphans.
14. Multi-file links require a separate identity-resolution result and never arise from similarity
    alone.
15. Existing prospect intake remains authoritative while PUE operates in staged shadow modes.
16. Only PUE-C7 may approve workflow authority migration, after all preceding capabilities certify.

## Non-goals

PUE-000 implements no parsing, classification, normalization engine, aggregation, FX, identity
resolution, repository, migration, UI, session integration, entity creation, or derived intelligence.
