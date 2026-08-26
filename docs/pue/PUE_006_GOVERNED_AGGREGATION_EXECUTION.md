# PUE-006 — Governed Aggregation Execution

## Certification boundary

PUE-006 executes only a current, immutable `ExecutionAuthorization` produced by
PUE-C5A. It does not infer authority from normalized records or from runtime
context. Planning rejects stale, absent, superseded, cross-scope, mismatched, or
incomplete authorization before any record is processed.

The implementation remains shadow-only and in memory. It does not integrate
with prospect analysis, production persistence, UI pages, Ask Nexora, entity
resolution, graphs, recommendations, or natural-language interpretation.

## Authorized execution flow

1. A machine-readable `AggregationRequest` names an assessment,
   authorization, operation, measure, dimensions, optional time bucket, exact
   scope, and execution-policy version.
2. The planner verifies the assessment and authorization are current in the
   capability repository.
3. The requested operation, measure, dimensions, time dimension, count basis,
   alignment, currency requirement, policy version, and exact normalization-run
   set must match the authorization.
4. Only then may the executor read the supplied immutable normalization runs.
5. The result retains the plan, authorization, capability, normalization,
   mapping-decision, normalized-field, and source-row provenance.

No source file is reopened. No missing execution metadata is reconstructed from
filenames, sessions, databases, globals, or normalized column names.

## Operation vocabulary

The bounded execution registry supports:

- `COUNT` for distinct certified `SOURCE_ROW` evidence records;
- `SUM` for one governed compatible currency/unit;
- `GROUPED_SUM` for one explicitly aligned governed dimension;
- `TIME_BUCKETED_SUM` for an explicitly aligned governed time dimension using
  authorized day, month, quarter, or year buckets.

Average, minimum, maximum, FX conversion, joins between files, formulas,
arbitrary SQL, arbitrary code, and user-defined aggregators are unsupported.

## Currency and numeric governance

Numeric execution uses `Decimal` with a versioned precision and rounding policy.
Single totals consume the certified currency set on the governed measure and
validate row-level currency records against it. Mixed currency never produces a
single scalar total. It may execute only through the separately authorized
currency-grouped capability, with no FX conversion.

The executor's inclusion/exclusion statistics expose invalid, null, partial,
unsupported, and filter-excluded records. Exclusions produce a `PARTIAL` result
rather than being hidden.

## Filters and security

Filters are structured data, never executable expressions. They are limited to
dimensions explicitly named by the selected authorization and to the bounded
operators `EQUALS`, `NOT_EQUALS`, `IN`, `DATE_FROM`, and `DATE_TO`. Injection-like
strings and dimensions not carried by the authorization are rejected before
execution.

## Result states

- `COMPLETED`: authorized execution included all eligible records.
- `PARTIAL`: authorized execution completed with explicit exclusions.
- `BLOCKED`: the upstream capability did not authorize the calculation.
- `REJECTED`: the request, scope, policy, run set, or authorization failed
  governance validation.

Blocked and rejected results contain no scalar or grouped numeric answer and
report zero processed records.

## Compatibility example

For the accepted 184-row prospect shape without governed currency, PUE-006
returns `BLOCKED` before aggregation. It does not calculate or expose `861828`.
The existing prospect pipeline remains authoritative and unchanged.
