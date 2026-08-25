# PUE-000 Provenance and Governance

## Provenance chain

```text
Derived result
  -> normalized evidence record(s)
  -> semantic mapping id/version
  -> classification method/version and confirmation reference
  -> original column(s) and row reference(s)
  -> source sheet/table
  -> source file
  -> immutable source/upload identity
  -> analysis/prospect/tenant scope
```

Aggregates use normalized record IDs plus explicit row sets, ranges, or lineage expressions. A
lineage reference points into protected raw evidence; it does not copy raw records into metadata.
Derivation rules are named/versioned before implementation. Unsupported dimensions and evidence
sufficiency travel with a derived result.

## Confidence is not confirmation

Confidence contains a score, band, method, evidence inputs, classifier version, threshold policy,
and decision time. Suggested bands are `HIGH`, `MEDIUM`, `LOW`, and `INSUFFICIENT`, but thresholds
remain configurable.

Classification supports `UNCLASSIFIED`, `CANDIDATE`, `AUTO_CLASSIFIED`,
`CONFIRMATION_REQUIRED`, `USER_CONFIRMED`, `REJECTED`, and `OVERRIDDEN`. Confirmation separately
supports `NOT_REQUIRED`, `REQUIRED`, `PENDING`, `CONFIRMED`, `REJECTED`, and `OVERRIDDEN`.
Confirmed/overridden mappings record actor, role, time, reason, previous/new mapping, analysis, and
audit reference. `USER_CONFIRMED` is an authority type, never source evidence.

## Coverage and query governance

Coverage states are `AVAILABLE`, `PARTIAL`, `AMBIGUOUS`, `CONFIRMATION_REQUIRED`,
`NOT_EVIDENCED`, and `UNSUPPORTED`. Coverage records concept, row coverage, confidence,
confirmation, source/file counts, and quality flags.

A measure is queryable only when mapping, unit/currency, ambiguity, coverage, and row linkage meet
policy. A dimension is queryable only when governed, structurally usable, and sufficiently covered.
Before answering, `QueryCapability` evaluates all required measures and dimensions.

For "What is EC2 spend?", support requires a governed cost measure, governed service dimension, a
governed EC2 value/filter, resolved currency, and preserved row-level linkage. Total spend alone is
insufficient. Query states are `SUPPORTED`, `PARTIALLY_SUPPORTED`, `CONFIRMATION_REQUIRED`,
`NOT_EVIDENCED`, and `NOT_SUPPORTED`.

Aggregation states are `SUPPORTED`, `SUPPORTED_WITH_LIMITATIONS`, `CONFIRMATION_REQUIRED`, and
`NOT_SUPPORTED`. Unresolved/mixed currency, conflicting units, ambiguous concepts, or unknown row
scope block support. No FX conversion is implied.

## Audit events

Future implementations emit tenant/prospect/analysis-scoped events for:

- `EVIDENCE_PROFILED`
- `SEMANTIC_CLASSIFICATION_CREATED`
- `MAPPING_CONFIRMATION_REQUESTED`
- `MAPPING_CONFIRMED`, `MAPPING_REJECTED`, `MAPPING_OVERRIDDEN`
- `NORMALIZATION_CREATED`
- `QUERY_CAPABILITY_EVALUATED`
- `DERIVED_RESULT_CREATED`
- `EVIDENCE_FUSION_CREATED`
- `EVIDENCE_PURGED`

Events avoid raw record content. PUE-000 adds no audit implementation.

## Multi-file extension

Source observation, semantic mapping, identity resolution, cross-source link, and derived
relationship remain distinct. Future match states are `MATCHED`, `POSSIBLE_MATCH`,
`CONFIRMATION_REQUIRED`, `UNMATCHED`, and `CONFLICT`. Similar names or values cannot establish a
fact. A `MATCHED` link cites a governed identity rule; later promotion reuses `data_fabric.identity`.
