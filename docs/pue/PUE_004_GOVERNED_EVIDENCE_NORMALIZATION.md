# PUE-004 — Governed Evidence Normalization

Status: implementation candidate for PUE-C4 review

Authority: shadow and non-production

Baseline: PUE-C3 at `c05f5c78`

## Purpose and authority boundary

PUE-004 converts authorized source values into typed, row-level normalized
representations. It operates only when the PUE-003 decision repository confirms
that the supplied `EffectiveSemanticMapping` is still the current mapping for
the fully scoped source column.

```text
current effective PUE-003 mapping + authorized source row value
  → governed normalized evidence field
```

PUE-002 confidence is never normalization authority. Rejected, expired,
superseded, undecided, or forged mappings cannot normalize evidence.

## Source-value access

The service accepts an iterable of `AuthorizedSourceValue` objects. It does not
open filesystem paths, query databases, inspect session state, or retrieve raw
evidence from globals. Each value carries an `EvidenceRowReference`; its
analysis, prospect, organization, tenant, source, file, and sheet scope must
exactly match the effective mapping. The column comes from that mapping. Missing
organization or tenant identifiers remain missing for prospect-only evidence.

The source value and its lexical representation remain on every normalized
record. Errors reference machine-readable warnings and provenance rather than
logging unrestricted customer rows.

## Normalized evidence contract

`NormalizedEvidenceField` retains:

- all eight governed scope fields and the source row reference;
- semantic concept and mapping decision identity/state/version;
- original source value and typed normalized value;
- normalized type and explicit unit metadata where known;
- ontology, classifier, governance-policy, and normalization-policy versions;
- explicit status and machine-readable warnings;
- structural, semantic, row, formula, and decision provenance;
- creation time and deterministic fingerprint.

Statuses are `NORMALIZED`, `UNCHANGED`, `PARTIAL`, `INVALID`, `AMBIGUOUS`,
`UNSUPPORTED`, `SUPPRESSED`, and `SKIPPED`. Blank/null inputs are retained as
`SKIPPED`; malformed inputs remain visible as `INVALID`. Unsupported concepts do
not receive a generic string-success fallback.

`NormalizationRun` is an immutable collection with operational processed,
normalized, invalid, and skipped counts. Those counts are not evidence coverage
or query capability.

## Representation-only registry

`NormalizerRegistry` selects a representation normalizer from the concept that
PUE-003 already approved. It never chooses or reclassifies a concept.

- financial numeric concepts use `Decimal`, avoiding binary-float loss;
- integer-only concepts require an integral decimal;
- date and datetime concepts use bounded policy formats;
- boolean concepts use bounded true/false lexical sets;
- string concepts normalize Unicode and outer whitespace while preserving case;
- `financial.currency` uppercases only configured explicit ISO codes.

The registry does not map `EC2` to a provider entity, resolve people, translate
labels, deduplicate values, or canonicalize applications or business services.

## Currency and units

Currency normalization consumes only explicit values in a column governed as
`financial.currency`. It does not consult providers, filenames, regions,
accounts, runtime currency confirmation, or the accepted prospect resolver. It
does not perform FX conversion.

Monetary columns normalize each value independently. When no governed unit is
available, the normalized unit remains absent and `UNIT_UNKNOWN` is retained.
No totals, averages, groupings, or comparisons are produced.

## Formula, merged-cell, and duplicate policy

Formula expressions are never evaluated. The expression is preserved. A cached
value may be used only when the versioned normalization policy explicitly
permits it; otherwise the result is `PARTIAL` with
`FORMULA_VALUE_UNRESOLVED`. The implementation does not propagate merged parent
values. Duplicate rows are normalized independently and keep distinct row
fingerprints.

## Fingerprints, policy versions, and drift

Record fingerprints include full scope, row reference, canonical source value,
semantic concept, mapping decision, ontology version, governance-policy version,
normalization-policy version, and formula metadata. Equivalent inputs reproduce
the same identity. Analysis or tenant changes therefore create different
identities.

A changed effective mapping creates a new immutable run, links it to the prior
run with `supersedes_run_id`, adds `MAPPING_CHANGED`, and preserves all earlier
records. A normalization-policy version change also creates new run and record
fingerprints. Historical output is never overwritten.

## Repository and performance boundary

The certification adapter is an in-memory, append-only run repository with
analysis, column, row, mapping-decision, and version lookups. Input is iterable
and normalized once; configurable batching is reserved in policy for a future
persistent adapter. PUE-004 creates no database, migration, production cache, or
raw evidence dump.

## Explicit non-goals

PUE-004 grants no authority for:

- aggregation, grouping, trends, rankings, or forecasts;
- `EvidenceCoverage`, `GovernedMeasure`, or `GovernedDimension`;
- `AggregationCapability` or `QueryCapability`;
- canonical entities, identity resolution, or graph relationships;
- recommendations, decision intelligence, or Ask Nexora answers;
- production UI or persistence;
- replacing or modifying the current prospect intake and currency flow.

Those boundaries remain reserved for PUE-005 and later certification stages.
