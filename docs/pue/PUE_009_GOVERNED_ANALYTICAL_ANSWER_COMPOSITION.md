# PUE-009 — Governed Analytical Answer Composition

## Composition authority

PUE-009 renders a factual answer from immutable PUE-008 interpretation,
PUE-007 analytical plan, and PUE-006 aggregation result objects. It does not
interpret the question again, plan a query, execute a request, inspect evidence
rows, recalculate values, or generate a new analytical claim.

The certified boundary is:

```text
PUE-008 interpretation
  + PUE-007 governed plan
  + PUE-006 governed result
  -> deterministic factual composition
```

No production Ask Nexora, Streamlit, report, executive, database, or prospect
path is changed by this package.

## Chain validation and freshness

Before rendering an analytical result, the composer requires:

- identical interpretation, plan, and result scope;
- the plan to reference the interpreted intent;
- immutable plan membership in the analytical plan repository;
- the plan's assessment to remain current;
- immutable result membership in the aggregation repository;
- the result request to reference the analytical plan ID;
- exact operation, measure, effective dimension, capability-assessment, and
  authorization identity agreement;
- the execution authorization to remain current.

Time dimensions are canonicalized from the PUE-007 `time_dimension_id` and
PUE-006 effective result dimension representation before comparison. Stale,
unregistered, cross-scope, or mismatched objects produce `FAILED`; they are not
rendered as current truth.

## Answer states

- `ANSWERED`: a complete governed result was rendered.
- `PARTIAL`: a governed partial result was rendered with certified exclusions.
- `BLOCKED`: upstream evidence governance refused the calculation.
- `UNSUPPORTED`: PUE-008 did not support the question.
- `AMBIGUOUS`: PUE-008 retained multiple interpretations.
- `FAILED`: the certified chain was absent, stale, or inconsistent.

Only `ANSWERED` and `PARTIAL` contain result values.

## Faithful structured values

The answer retains machine-readable scalar or grouped values copied directly
from PUE-006. Each displayed group retains its certified dimension values, value,
unit, record count, and source group ID. The composer does not sum, average,
calculate percentages, sort, rank, select top-N, or compare values.

Large group sets are sliced to the policy limit in upstream result order. The
answer discloses total and displayed group counts; truncation is not ranking.

## Numeric, currency, and unit formatting

Decimal formatting preserves the certified value without floating-point
conversion. USD, INR, EUR, and GBP use the symbols already configured by Nexora.
Other governed unit/currency codes use `<CODE> <amount>`. A missing unit is
displayed without fabricating currency.

Mixed-currency groups remain separate. PUE-009 never produces a combined total
or performs FX conversion.

## Partial and blocked answers

`PARTIAL` wording uses only PUE-006 statistics: included records and explicit
invalid, null, partial, unsupported, or filter exclusions. It does not decide
whether the remaining evidence is sufficient.

For the accepted 184-row currency-less case, PUE-008 may interpret total cost
while PUE-007 blocks planning. PUE-009 states that total cost cannot be
calculated because governed currency evidence is unavailable or incompatible.
It does not expose `861828` or any probable total.

## Provenance and determinism

Machine-readable provenance retains interpretation, plan, result, assessment,
capability, authorization, normalization-run, source-row, included-record,
composer, and policy identities. Detailed raw evidence is not exposed.

Question, immutable upstream fingerprints, rendered structured values, text,
limitations, provenance, and composition policy determine answer identity. The
composition timestamp does not affect the fingerprint. Policy drift creates a
new identity.

## Prohibited derivations

PUE-009 does not create percentages, rankings, trends, forecasts, anomalies,
causes, risk labels, savings, optimization advice, recommendations, entity
enrichment, or relationship claims. A future narrative provider may receive only
the governed structured answer and must remain subject to the same constraint;
no such provider is part of PUE-009.

## Known upstream boundary

C5A/PUE-006 can authorize currency-grouped execution, and PUE-009 can faithfully
render that result. The frozen PUE-007 registry does not yet expose a dedicated
currency-grouped natural-language planning route. PUE-009 does not alter PUE-007
to close that separate planning concern.
