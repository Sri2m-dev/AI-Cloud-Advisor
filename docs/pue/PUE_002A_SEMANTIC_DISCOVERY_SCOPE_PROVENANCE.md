# PUE-002A Semantic Discovery Scope Provenance Amendment

## Status

PUE-002A is a narrow amendment to the certified PUE-002 discovery provenance contract. It changes
no semantic taxonomy, alias, score, confidence, ambiguity, risk, explanation, candidate ranking,
production behavior, persistence, UI, session state, normalization, or aggregation.

## Why the amendment is required

The original `SemanticDiscoveryProvenance` carried analysis, source, file, sheet, and column
identifiers but omitted prospect, organization, and tenant identifiers. PUE-003 mapping decisions
must be locally governed for one source column in one analysis and must never inherit authority from
another prospect or tenant.

Reconstructing the missing scope later from session state, filenames, mutable globals, database
lookups, or caller overrides would make provenance dependent on external state. It could allow a
decision created for one prospect to be misapplied to structurally identical evidence elsewhere.

## Contract change

`SemanticDiscoveryProvenance` now explicitly carries:

```text
analysis_id
prospect_id
organization_id
tenant_id
source_id
file_id
sheet_id
column_id
```

`organization_id` and `tenant_id` remain separate even when a deployment assigns the same value.
They represent distinct governance concepts and neither may be inferred from the other. Optional
absence is preserved explicitly as `None`; it is not reconstructed.

## Authoritative scope source

All scope fields are copied directly from the PUE-001 `EvidenceColumn.context`, the immutable
`EvidenceAnalysisContext` attached during structural profiling. The classifier accepts no scope
override and performs no session, global, filename, or database lookup.

## Identity and fingerprint impact

Discovery IDs bind the complete provenance object, while semantic fingerprints bind the structural
profile and discovery results. PUE-001 structural contracts include the complete analysis context.
Changing prospect, organization, or tenant scope therefore changes the structural fingerprint,
column discovery ID, and semantic fingerprint. Identical source and complete scope replay to
identical identifiers and fingerprints.

## Compatibility

Candidate concepts, ordering, scores, confidence bands, signals, explanations, risks, and
confirmation requirements are unchanged. Existing prospect intake remains authoritative. Consumers
constructing `SemanticDiscoveryProvenance` directly must now provide complete explicit scope; the
repository classifier supplies it from `EvidenceAnalysisContext`.

## PUE-003 readiness boundary

This amendment makes discovery provenance self-contained for analysis/prospect/organization/tenant
isolation. It does not authorize or implement confirmation governance. PUE-003 may begin only after
this amendment is validated, reviewed, and frozen.
