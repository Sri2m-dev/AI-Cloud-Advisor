# PUE-ACT-001 — Controlled Activation Readiness

## Authority

PUE-ACT-001 defines a control plane; it activates no production behavior. The existing prospect pipeline remains authoritative. The activation package imports no page, Streamlit state, prospect service, database client, aggregation executor, or answer composer.

Default behavior is `SHADOW_ONLY` with `LEGACY_AUTHORITATIVE` fallback. Code availability never enables visibility or routing.

## Governed configuration

Each configuration is immutable and append-only, actor-attributed, reasoned, versioned, optionally time-bounded, and scoped to global, organization, tenant, prospect, or analysis identity. Resolution uses evidence/capability scope fields only. Specificity is deterministic:

`GLOBAL → ORGANIZATION → TENANT → PROSPECT → ANALYSIS`

The most specific unexpired matching configuration wins. The global kill switch precedes every configuration and reduces effective behavior to `SHADOW_ONLY` immediately.

Administrative permissions are isolated:

- `VIEW_PUE_ACTIVATION`
- `CHANGE_PUE_STAGE`
- `TRIGGER_PUE_ROLLBACK`
- `TRIGGER_PUE_KILL_SWITCH`

End users cannot self-activate PUE.

## Routing boundary

`PueQuestionRouter` produces a `RoutingDecision` only. It does not interpret, plan, execute, compose, inspect evidence, or read legacy values. Inputs are explicit question/scope identity, resolved activation, already-known interpretation status, capability eligibility, failure state, and legacy availability.

Routes are `ROUTE_PUE`, `ROUTE_LEGACY`, `BLOCK`, or `SHADOW_ONLY`. Stage 4 is the first stage where `ROUTE_PUE` can be selected, and only for an explicitly allowlisted intent with interpreted status and certified capability. Stage 4 is defined and tested but is not production-activated.

No contract contains both legacy and PUE values, preventing result blending.

## Persistence and retention readiness

ACT-001 remains in-memory. Future production persistence must distinguish:

- `CONFIGURATION`: activation policy and kill-switch history.
- `AUDIT_REQUIRED`: mapping/activation/rollback decisions.
- `RETENTION_BOUND`: discoveries, normalization metadata, capability assessments, and authorizations.
- `EPHEMERAL`: ordinary plans and interpretations unless incident policy retains references.
- `OPTIONAL_HISTORY`: selected surfaced answers under an approved policy.

All evidence-derived metadata must share the prospect analysis retention ceiling. Purging evidence must purge or tombstone dependent PUE artifacts without orphan cross-analysis references.

## Confirmation UX readiness

A future confirmation experience must show the candidate concept, confidence, explanation, original source column, policy-safe samples, and evidence scope. Confirm, reject, and override require an authenticated actor, reason where policy requires it, immutable audit history, and explicit expiry/drift behavior. Pending mappings remain unavailable downstream. ACT-001 implements no UI and no production auto-confirmation.

## Audit and observability

Required events include activation and kill-switch changes, routes/fallbacks, mapping decisions, blocked/completed execution, surfaced answers, and rollback. Required metrics include run visibility, routes, fallbacks, blocked/ambiguous queries, stage failures, per-stage latency, and comparison distribution.

Health is objectively classified as `HEALTHY`, `DEGRADED`, `UNHEALTHY`, or `PAUSED`. Health never auto-promotes activation.

## Readiness decision

Recommendation: `READY_FOR_STAGE_2_PILOT` for one internal, time-limited prospect or analysis, exposing evidence discovery and capability status only.

Stage 3/4 remain NO-GO pending production persistence/purge, confirmation UX, observability/alerting, deployed rollback operations, and separate routing certification.
