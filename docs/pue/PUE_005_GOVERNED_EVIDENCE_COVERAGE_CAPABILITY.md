# PUE-005 — Governed Evidence Coverage & Capability

Status: implementation candidate for PUE-C5 review

Authority: shadow and non-production

Baseline: PUE-C4 at `96ba6644`

## Purpose

PUE-005 consumes immutable PUE-004 normalization runs and determines what
governed evidence exists, whether it is usable, whether concepts qualify as
dimensions or measures, and which bounded analytical capabilities satisfy their
prerequisites. It never executes those capabilities.

The mandatory distinction is:

```text
field exists
  ≠ governed semantic mapping
  ≠ usable normalized evidence
  ≠ governed dimension or measure
  ≠ safe aggregation
  ≠ executed or answered question
```

## Input and isolation boundary

The evaluator accepts only `NormalizationRun` and its governed records. It does
not open CSV/XLSX files, inspect raw source paths, access Streamlit state, query
databases, or rerun semantic discovery. All records must share the same
analysis, prospect, organization, and tenant scope. Mixed-scope input is
rejected rather than merged. Legitimately absent organization or tenant scope
remains absent.

Capability fingerprints include the full scope, normalized record identities,
mapping decisions, policy versions, and registry version. Identical files in
different analyses, prospects, or tenants therefore cannot share authority.

## Evidence coverage

`EvidenceCoverage` records observed, normalized/valid, null, invalid, partial,
and unsupported counts; coverage and validity ratios; bounded distinct count;
normalization runs; mapping decisions; source references; reason codes; policy;
and a deterministic fingerprint.

Coverage states are:

- `NOT_EVIDENCED`: no governed normalized evidence exists.
- `OBSERVED`: governed records exist but no usable values remain.
- `PARTIAL`: some values are usable but policy thresholds are not satisfied.
- `EVIDENCED`: coverage, validity, and invalid-ratio thresholds are satisfied.
- `INSUFFICIENT`: evidence cannot satisfy a specific sufficiency policy.
- `CONFLICTED`: incompatible governed evidence prevents one interpretation.
- `BLOCKED`: another governance requirement prevents use.

The initial evaluator uses `PARTIAL` for below-threshold concept inventories and
expresses capability-specific insufficiency as `BLOCKED` or `NOT_SUPPORTED`.
Thresholds are centralized in versioned `CoveragePolicy`; ratios alone do not
grant authority.

## Governed dimensions

A governed string is not automatically a dimension. `GovernedDimension`
requires governed semantic provenance, evidenced normalization coverage,
dimension validity policy, and isolated scope. Monetary values and explicit
currency/unit concepts are excluded from generic dimension qualification.

Dimension qualification preserves semantic concept and cardinality metadata but
does not create provider, service, person, application, resource, or contract
entities. It creates no relationships.

## Governed measures and currency binding

`GovernedMeasure` separates value sufficiency from aggregation eligibility. A
financial cost column can contain evidenced values while aggregation remains
blocked.

Monetary qualification checks:

- governed cost-value coverage and validity;
- governed `financial.currency` coverage;
- exact source/file/sheet/row binding between amount and currency;
- currency consistency;
- versioned measure and binding thresholds.

Missing currency yields `UNIT_NOT_EVIDENCED`. Partial row binding yields
`ROW_BINDING_INCOMPLETE`. Multiple currencies yield `MIXED_CURRENCY` and block a
single-currency total. No FX conversion is available. A bounded
`CURRENCY_GROUPED_TOTAL` capability may be supported when every amount is bound
to explicit governed currency, but PUE-005 still does not execute that grouping.

`permitted_aggregation_functions` is policy metadata describing what a later
engine may plan after certification; it is not an aggregation result.

## Capability registry

Registration means only that Nexora recognizes a capability type. The versioned
initial registry includes evidence description/counting, dimension filtering,
time-range analysis, monetary total and dimension grouping, currency grouping,
FX-normalized total, and bounded inventory capabilities.

Capability states are:

- `SUPPORTED`: all declared prerequisites are governed and sufficient.
- `PARTIALLY_SUPPORTED`: only a documented subset is sufficient.
- `NOT_SUPPORTED`: required governed evidence is absent or the operation is not
  implemented, such as FX.
- `BLOCKED`: relevant evidence exists but governance or compatibility prevents
  safe use.
- `UNKNOWN`: the registry cannot make a governed determination.

Every determination carries deterministic reason codes and provenance back to
coverage, normalized fields, normalization runs, mapping decisions, and source
references. Unsupported determinations retain assessment-input provenance where
evidence exists.

## Determinism and repository

Coverage, dimension, measure, capability, and assessment identities are derived
from governed input fingerprints plus versioned coverage policy, capability
policy, and capability registry. Policy changes create new immutable identities.
The certification repository is in-memory and idempotent; it stores assessment
versions by complete scope and introduces no database or migration.

## Explicit non-goals

PUE-005 does not:

- sum, average, rank, group, filter, trend, or forecast evidence;
- calculate savings or perform FX conversion;
- execute query plans;
- create canonical entities, resolve identities, or write graph relationships;
- generate recommendations or AI answers;
- modify Ask Nexora, prospect analysis, demo data, or production UI;
- reopen source evidence or persist production capability authority.

PUE-006 remains unauthorized. It may later execute only aggregations explicitly
permitted by a certified PUE-005 capability model.

## PUE-C5 review focus

Certification should verify that presence remains distinct from sufficiency,
dimensions remain distinct from measures, measure eligibility remains distinct
from aggregation eligibility, currency is row-bound and governed, mixed currency
is safely blocked, poor-quality evidence prevents capability, provenance remains
complete, and no analytical value is produced.
