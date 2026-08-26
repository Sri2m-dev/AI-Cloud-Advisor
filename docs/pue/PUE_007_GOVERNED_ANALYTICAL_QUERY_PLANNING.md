# PUE-007 — Governed Analytical Query Planning

## Certification boundary

PUE-007 deterministically translates an explicit structured analytical intent
into a PUE-006 `AggregationRequest`. It creates that request only when the exact
current PUE-005 capability and C5A `ExecutionAuthorization` support the intent.

PUE-007 does not execute aggregation, inspect normalized rows, reopen evidence,
interpret natural language, resolve aliases or entities, call AI services, alter
prospect behavior, change UI pages, or persist production data.

## Structured intent

`AnalyticalIntent` carries immutable scope, a bounded intent type, canonical
semantic concept identifiers, structured filters, an optional governed time
bucket, caller metadata, intent version, and optional expected assessment and
authorization identities.

The initial intent vocabulary is deliberately narrow:

- `COUNT_RECORDS`
- `TOTAL_MEASURE`
- `GROUP_MEASURE_BY_DIMENSION`
- `TIME_SERIES_MEASURE`

These map only to the registered capability/operation pairs:

| Intent | Capability | Operation |
|---|---|---|
| `COUNT_RECORDS` | `COUNT_EVIDENCE_RECORDS` | `COUNT` |
| `TOTAL_MEASURE` | `MONETARY_TOTAL` | `SUM` |
| `GROUP_MEASURE_BY_DIMENSION` | `MONETARY_TOTAL_BY_DIMENSION` | `GROUPED_SUM` |
| `TIME_SERIES_MEASURE` | `MONETARY_TREND` | `TIME_BUCKETED_SUM` |

Average, minimum, maximum, FX conversion, recommendations, risk discovery, and
generic query operations are not part of the registry.

## Resolution and authority

Planning performs the following sequence without shortcuts:

1. Look up the current assessment using the exact four-field evidence scope.
2. Validate the bounded intent shape and canonical concept identifiers.
3. Resolve a unique governed measure and requested dimensions from that current
   assessment.
4. Select the explicitly registered capability.
5. Require that capability to be `SUPPORTED`.
6. Resolve exactly one current execution authorization matching the operation,
   measure, dimensions, time dimension, currency rule, alignment, and policy.
7. Resolve structured filters only against dimensions carried by that
   authorization.
8. Construct an immutable analytical plan and exact PUE-006 request.

No authorization is reconstructed from coverage, normalization records, source
headers, filenames, sample values, session state, or caller overrides.

## Planning states

- `READY`: the only state that includes an `AggregationRequest`.
- `BLOCKED`: the registered upstream capability exists but does not support the
  requested calculation.
- `REJECTED`: intent shape, governed concepts, filters, currency behavior, or
  authorization matching failed.
- `AMBIGUOUS`: more than one certified resolution remained and no policy could
  select one.
- `STALE`: an assessment or authorization is no longer current.

Every non-READY result has `aggregation_request = None`.

## Filters and time buckets

Intent filters refer to canonical governed dimension concepts and use the PUE-006
bounded filter operators. Planning converts them to immutable dimension-ID
filters only when the selected authorization carries that dimension. Filter
values remain normalized scalar values; no entity resolution occurs.

Time-series planning requires an exact governed time concept, certified
alignment, and a bucket explicitly permitted by the authorization.

## Provenance and determinism

Every plan retains the assessment, capability, authorization, measure,
dimensions, time dimension, alignment/count basis, normalization runs, coverage,
and policy versions. This extends the existing upstream lineage without scanning
source rows.

Plan identity excludes the planning timestamp. Equivalent intent, current
assessment, authorization, scope, and policy therefore produce the same plan
fingerprint and PUE-006 request. Plans remain immutable in an in-memory history.
PUE-006 still revalidates authorization at execution time.

## Mandatory negative boundaries

Inputs such as `cost`, `spend`, `Service`, or `What is EC2 cost?` are rejected.
PUE-007 accepts canonical concepts such as `financial.cost.total` and
`technology.service`; it resolves governed identities but never discovers their
meaning.

For the 184-row prospect shape with valid cost values but no governed currency,
`TOTAL_MEASURE financial.cost.total` returns `BLOCKED`, produces no request, and
does not calculate `861828`. Existing prospect analysis remains unchanged and
authoritative.
