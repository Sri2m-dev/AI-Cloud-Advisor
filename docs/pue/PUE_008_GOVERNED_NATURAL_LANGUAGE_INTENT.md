# PUE-008 — Governed Natural-Language Analytical Intent

## Authority boundary

PUE-008 interprets a bounded natural-language analytical question as a
structured PUE-007 `AnalyticalIntent`. It never decides whether that intent is
authorized, executable, or answerable.

The certified chain remains:

```text
NaturalLanguageQuestion
  -> PUE-008 interpretation candidate
  -> PUE-007 governed planning
  -> PUE-006 request, only when authorized
  -> separate explicit execution
```

PUE-008 does not emit an aggregation request, calculate a value, generate a
final answer, inspect raw evidence or normalized rows, call an LLM, modify Ask
Nexora, alter UI pages, or persist production data.

## Analysis-scoped governed catalog

`AnalyticalConceptCatalog` is built only from the current PUE-005 assessment for
the exact four-field evidence scope. It contains governed measure identities and
governed dimension identities with C7A value types, filterability, and operator
metadata. It contains no rows, headers, samples, uploaded bytes, or historical
cross-tenant mappings.

Catalog scope must exactly match question scope. Prospect-only absence of
organization and tenant remains absence.

## Deterministic interpretation model

The initial interpreter is deterministic and versioned. It uses:

- Unicode/whitespace canonicalization while preserving the original question;
- a bounded analytical alias registry;
- explicit intent patterns;
- a bounded unsupported-operation registry;
- C7A type-aware literal parsing;
- explicit candidate scoring and ambiguity states.

No external LLM, embeddings, fuzzy matching, customer-specific learning, or
hidden conversation context participates in interpretation.

The only target intents are the frozen PUE-007 vocabulary:

- `COUNT_RECORDS`
- `TOTAL_MEASURE`
- `GROUP_MEASURE_BY_DIMENSION`
- `TIME_SERIES_MEASURE`

Hybrid time-series/grouping, distinct-dimension count, ranking, average,
minimum, maximum, savings, optimization, risk, and relationship questions are
unsupported rather than approximated.

## Confidence and ambiguity

Every result carries an explicit status, numeric score, confidence band,
candidate set, bounded reason codes, supporting explanation, catalog identity,
interpreter/policy versions, provenance, and deterministic fingerprint.

Only `INTERPRETED` includes a primary `AnalyticalIntent`. `AMBIGUOUS`,
`UNSUPPORTED`, `INSUFFICIENT_CONTEXT`, and `REJECTED` contain no selected intent.
Multiple governed measures therefore remain alternatives rather than being
silently resolved by convenience.

Confidence is descriptive only. High confidence provides no analytical
authority and cannot bypass PUE-007.

## Typed literals

PUE-008 is the explicit natural-language typing boundary. It may produce a
typed value only after selecting a governed filterable dimension and consulting
its C7A value type/operator policy. Supported deterministic examples include:

- a bounded Boolean vocabulary (`true`, `false`, `enabled`, `disabled`);
- exact integer and decimal literals when the target type requires them;
- approved date formats for governed `DATE`/`DATETIME` dimensions;
- non-empty `IN` lists whose members all parse to the governed type;
- bounded literal aliases such as `EC2`, `RDS`, `AWS`, `Azure`, and `GCP`, only
  when their associated governed dimension is present in the current catalog.

Typed string filters remain literal strings. PUE-008 does not resolve `EC2` to
an AWS entity or infer relationships, vendors, or providers outside the bounded
analysis-specific catalog.

## Injection and governance bypass resistance

Phrases such as “ignore PUE-007,” “use the raw CSV,” “assume USD,” or “calculate
directly” grant no authority. A supported analytical fragment may still produce
an intent candidate, but the interpreter neither reads the referenced source nor
adopts the requested assumption. The resulting intent must still pass PUE-007.

Questions are bounded for empty input, binary/null content, contract version,
and maximum length.

## Certification examples

For the currency-less 184-row prospect case, “What is the total cost?” is
correctly interpreted as `TOTAL_MEASURE / financial.cost.total`. PUE-007 then
returns `BLOCKED`; PUE-008 contains no `861828` and performs no calculation.

For governed cost, currency, and service evidence, “Show cost by service” yields
a structured grouped intent and PUE-007 may produce a READY request. PUE-008
still stops before execution.

## Future provider boundary

A future probabilistic or LLM interpreter may only act as a candidate generator.
Its candidates must pass the same deterministic catalog, type, pattern, scope,
ambiguity, and downstream authorization checks. Such a provider is not part of
PUE-008 certification.
