# PUE-C5A — Execution Authorization Metadata Amendment

Status: implementation candidate for PUE-C5A review

Authority: shadow metadata only; no execution

Baseline: PUE-C5 at `c368b0fd`

## Why PUE-C5 was insufficient

PUE-C5 established evidence coverage and analytical capability, but it did not
fully specify the executable shape. A future executor could otherwise infer an
operation from independently eligible measures and dimensions, count normalized
fields instead of source rows, reuse `TIME_RANGE_ANALYSIS` as monetary-trend
authority, or accept a historical assessment after its evidence changed.

PUE-C5A closes those gaps without calculating anything.

## Explicit operations and authorizations

`AuthorizedOperation` is bounded to `COUNT`, `SUM`, `GROUPED_COUNT`,
`GROUPED_SUM`, and `TIME_BUCKETED_SUM`. Registration does not itself grant an
operation. An immutable `ExecutionAuthorization` is emitted only from a
supported capability whose exact prerequisites are certified.

Each authorization binds:

- assessment and capability identity;
- complete analysis/prospect/organization/tenant scope;
- exact operation, measure, dimension, or time-dimension identities;
- alignment or canonical record-basis identity;
- normalization runs;
- currency and unit requirements;
- allowed time buckets;
- policy and assessment fingerprints.

Current financial measures retain `SUM` only. Decimal representation never
implies `MIN`, `MAX`, or `AVERAGE` authority.

## Capability execution shapes

- `COUNT_EVIDENCE_RECORDS` may authorize `COUNT` over a certified
  `SOURCE_ROW` basis.
- `MONETARY_TOTAL` may authorize `SUM` only for an aggregation-eligible,
  single-currency governed measure.
- `MONETARY_TOTAL_BY_DIMENSION` may authorize `GROUPED_SUM` only for an exact
  aligned measure/dimension pair. Currency is excluded from this generic
  business-dimension path.
- `MONETARY_TREND` is separate from `TIME_RANGE_ANALYSIS`. It may authorize
  `TIME_BUCKETED_SUM` only for an aligned monetary measure/time dimension and
  explicitly allows `DAY`, `MONTH`, `QUARTER`, and `YEAR` buckets.
- `CURRENCY_GROUPED_TOTAL` may authorize `GROUPED_SUM` for mixed monetary
  evidence only when amount and explicit governed currency are row-aligned.
- No FX authorization exists.

## Canonical record count basis

`RecordCountBasis` uses `SOURCE_ROW`, identified by a deterministic fingerprint
of analysis, prospect, organization, tenant, source, file, sheet, and
`EvidenceRowReference`. Multiple normalized fields from one source row collapse
to one count-basis identity. PUE-C5A records the distinct count as assessment
metadata but does not execute `COUNT` or return an aggregation result.

Full row sets participate in deterministic set fingerprints. Materialized row
references are bounded by policy and accompanied by a lineage expression, so
large assessments do not require unbounded authorization metadata.

## Provenance-driven alignment

`EvidenceAlignment` compares certified normalized fields through the same
`SOURCE_ROW` key. It never zips arrays, joins by values, reopens files, performs
fuzzy/entity joins, or crosses files through inferred identity.

Alignment states are `ALIGNED`, `PARTIALLY_ALIGNED`, `NOT_ALIGNED`,
`CONFLICTED`, and `BLOCKED`. Grouped and time-bucketed authorization requires
`ALIGNED`. The contract retains measure and related normalization runs, row
counts, deterministic aligned-row fingerprints, reason codes, and policy.

## Currency binding

Currency binding remains row-level evidence. Single-total authorization requires
one governed compatible currency across all measure rows. Mixed currency blocks
that authorization. A dedicated currency-grouped authorization can reference
the governed currency dimension and row alignment without authorizing FX or an
implicit cross-currency total.

Analysis-level or session-confirmed currency is not converted into row binding.
PUE-C5A consumes only PUE-004 normalized evidence and PUE-005 provenance.

## Current, superseded, and stale assessments

`InMemoryCapabilityRepository` maintains immutable assessment history and an
explicit current pointer per complete capability scope. A new assessment for the
same scope supersedes the prior assessment without mutation or deletion.

`get_current_assessment` optionally verifies that a capability belongs to the
current assessment. `get_assessment_state` reports `CURRENT`, `SUPERSEDED`, or
`STALE` for unknown/out-of-context identity. `is_authorization_current` verifies
assessment ID, assessment fingerprint, capability identity, scope, and exact
authorization membership.

Normalization, coverage, alignment, measure, dimension, capability-policy, or
authorization-policy drift changes deterministic fingerprints. Authorizations
from a superseded assessment therefore fail the current check.

## Determinism and provenance

Record basis, alignment, assessment, and authorization fingerprints contain
scope and certified upstream identities. Authorization provenance therefore
traces through assessment, capability, alignment, measure/dimension/time,
coverage, normalization runs and records, mapping decisions, and the prior PUE
chain without source reconstruction.

## Explicit non-goals

PUE-C5A does not count, sum, group, bucket, filter, average, or calculate a
trend. It creates no aggregation planner or executor, accepts no query language,
opens no source evidence, and changes no production UI, persistence, prospect
behavior, or Ask Nexora behavior.

PUE-006 remains blocked until this amendment is reviewed, validated, and frozen
as a separate checkpoint.
