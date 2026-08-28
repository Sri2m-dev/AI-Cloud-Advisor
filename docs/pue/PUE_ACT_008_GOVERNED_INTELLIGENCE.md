# PUE-ACT-008 Governed Intelligence / Ask Nexora

## Authority boundary

ACT-008 introduces a deterministic governed answer boundary. It does not create
a second natural-language engine and does not allow raw language, model output,
or conversation history to become execution authority.

The certified route is:

```text
question + authenticated scope
  -> PUE-008 deterministic interpretation
  -> PUE-007 current capability and authorization planning
  -> ACT-005/PUE-006 execution when ready
  -> ACT-006 canonical registry and graph lookup when appropriate
  -> ACT-007 source-binding/provenance lookup when appropriate
  -> bounded answer with provenance and deterministic fingerprint
```

Unsupported, ambiguous, blocked, stale, and insufficient states are preserved
through the answer contract. No arithmetic, SQL, `eval`, free-form repository
query, forecasting, optimization, FX conversion, or autonomous action is added.

## Supported routes

Measurement questions use the existing PUE-008 interpreter and ACT-005
measurement service. Current capability, normalization, mapping, currency, and
execution authorization must all pass before SUM or GROUPED_SUM runs. Entity,
ownership, cost-centre, and dependency questions use canonical registry and
relationship intelligence services. Cross-source questions use ACT-007 binding
records and retain each source identity.

The answer includes a bounded question class, state, citations, provenance,
execution/plan references where applicable, and an answer fingerprint derived
from authoritative inputs rather than rendering timestamps.

## Safety boundaries

The service requires caller scope for every request and filters canonical entity
lookups by organization and tenant. It does not consult legacy demo data,
predictive services, or the old broad Copilot fallback. Prospect evidence cannot
be supplemented by another tenant. Uploaded text is data; injection-like phrases
cannot bypass governance.

Same-name canonical entities remain ambiguous. Missing graph relationships return
explicit governed insufficiency. Forecasting, optimization, termination, FX,
and similar requests return `UNSUPPORTED / NOT AUTHORIZED`.

## Acceptance evidence

The controlled ACT-006/007 fixture answers ownership, cost centre, dependency,
and fused-source questions through the existing canonical graph and binding
contracts. Existing single-currency ACT-005 fixtures answer total and grouped
cost through the certified executor. Missing currency remains blocked without a
number. The real CUR workbook remains subject to ACT-006 limitations: record
count can be governed, but cost cannot be answered without governed currency,
and applications are never invented from Service values.

ACT-C8 is backend-certified by automated tests. Browser acceptance is deferred
to ACT-013 unless a supported browser environment becomes available for the
existing Ask Nexora page; no browser pass is claimed here.