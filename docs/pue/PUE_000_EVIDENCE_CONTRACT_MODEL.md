# PUE-000 Evidence Contract Model

## Contract map

| Stage | Contracts | Responsibility |
| --- | --- | --- |
| Scope | `EvidenceAnalysisContext` | Mandatory analysis/source/prospect isolation |
| Source | `EvidenceSource`, `EvidenceFile`, `EvidenceSheet`, `EvidenceColumn`, `EvidenceRowReference` | Immutable source identity and addressability |
| Observation | `PrimitiveProfile`, `StructuralObservation` | Reproducible physical facts only |
| Interpretation | `SemanticConcept`, `SemanticCandidate`, `SemanticClassificationResult`, `MappingConfidence` | Possible meaning and ambiguity |
| Governance | `ConfirmationRecord`, `SemanticMapping` | Mapping authority and confirmation provenance |
| Normalization | `NormalizedEvidenceField`, `EvidenceProvenance` | Governed value with original value and lineage |
| Coverage | `EvidenceCoverage` | Availability, quality, ambiguity, and record coverage |
| Query | `GovernedMeasure`, `GovernedDimension`, `AggregationCapability`, `QueryCapability` | Pre-execution support decisions |
| Derivation | `DerivedEvidenceResult` | Governed output linked to normalized inputs |
| Fusion | `EvidenceFusionReference` | Future cross-source identity-governed links |

The frozen dataclasses in `universal_evidence/contracts/` are executable architecture contracts,
not production services. They perform validation only and have no I/O.

## PUE-001 structural output

Future file observations cover filename, size, MIME type, encoding, workbook/table shape, warnings,
hidden sheets, formula/merged-cell indicators, row and column counts, header candidates, and empty
leading/trailing rows. Column profiles cover original header/ordinal, primitive candidates, null and
distinct counts, coverage/uniqueness, safe extrema, string lengths, structural candidate flags,
mixed types, bounded safe samples, sensitivity flags, and warnings.

Words such as `candidate_identifier` and `candidate_numeric_measure` describe structural behavior
only. They do not assign an enterprise semantic concept.

## Required invariants

- Scope requires `analysis_id`, `source_id`, and `prospect_id`.
- Source retention expiry follows receipt time.
- A row reference uses exactly one of explicit rows, a range, or a lineage expression.
- Safe representative samples contain at most five values; policy may impose a lower bound or zero.
- A `USER_CONFIRMED` classification requires a confirmed actor/timestamp record.
- User authority is never represented as engine/source authority.
- Mapping IDs and versions align in provenance.
- A normalized field's provenance belongs to the same analysis.
- A derived result references normalized records and a derivation rule.
- A supported query evidences every required governed measure and dimension.
- A supported aggregation has a governed measure, row scope, rule, and resolved non-mixed currency.
- A matched fusion reference cites an identity-governance rule.

## Existing contracts reused

PUE references rather than duplicates these established concepts:

- `data_fabric.semantic.models.SemanticConcept` supplies the canonical ontology destination once a
  PUE concept is approved for canonical use.
- `data_fabric.semantic.models.SemanticMapping` and mapping services inform later promotion, but do
  not model column ambiguity, confirmation, or temporary analysis scope sufficiently for PUE.
- `data_fabric.contracts.EntityLineage` and `EntityProvenance`, plus
  `data_fabric.lineage.ProvenanceRecord`, remain the canonical entity/relationship lineage target.
- `data_fabric.identity` remains the future canonical identity resolution authority.
- `enterprise_intelligence.QueryResponse` remains the canonical enterprise query response after
  data is authoritative.
- Existing prospect intake owns authorization, encryption, audit, retention, currency confirmation,
  and purge behavior.

## Intentional new abstractions

PUE contracts are new because existing contracts start at canonical entities, source terms, or
enterprise queries. They do not address pre-canonical file/sheet/column/row structure, multiple
column candidates, analysis-scoped user confirmation, temporary normalized cells, coverage matrices,
or pre-query evidence sufficiency. PUE objects must not be persisted through canonical repositories
until an explicit promotion contract is designed and certified.
