# PUE-ACT-001 Pilot Acceptance and Readiness Report

## Recommended pilot

One internal, time-limited prospect or analysis at Stage 1, promotable by explicit approval to Stage 2. Visible surfaces are evidence discovery and capability status only. No production PUE answer and no Ask Nexora routing are authorized.

Recommended future selected-answer allowlist:

- `COUNT_RECORDS`
- `TOTAL_MEASURE`
- `GROUP_MEASURE_BY_DIMENSION`

This recommendation grants no Stage 3 authority. `TIME_SERIES_MEASURE` remains excluded initially.

## Entry criteria

- PUE-C10 and full regression certification remain green.
- Exact scope, expiry, actor, stage, surfaces, fallback, and rollback are approved.
- Kill switch and fallback are exercised in the deployment environment.
- Audit integration and observability dashboards/alerts are connected.
- Confirmation strategy and retention/purge ownership are accepted.
- Known limitations are explicitly accepted by pilot owners.

## Exit and rollback criteria

Immediate rollback: isolation defect, wrong factual answer, missing provenance, retention failure, audit failure, or prospect/session impact.

Stage reduction/investigation: error or fallback rate threshold breach, persistent degraded health, latency above the agreed pilot threshold, or unexplained legacy/PUE comparison distribution.

## Control-plane readiness

| Area | ACT-001 result |
|---|---|
| Default deny | Ready |
| Scope precedence/isolation | Ready in-memory |
| Kill switch | Ready in-memory |
| Configuration rollback | Ready in-memory |
| Question allowlist/routing decision | Ready as isolated contract only |
| Audit vocabulary/events | Ready in-memory; production sink blocked |
| Health/metrics contract | Ready; production exporter blocked |
| Persistence | Architecture classified; production implementation blocked |
| Confirmation UX | Requirements defined; implementation blocked |
| Ask Nexora | Not modified; production routing blocked |

## Go/no-go

`GO` for a separately approved Stage 1/2 pilot design and deployment-readiness package.

`NO-GO` for Stage 3 selected production answers or Stage 4 Ask Nexora routing until persistence/purge, confirmation UX, observability/alerting, production rollback, and routing integration are separately certified.
