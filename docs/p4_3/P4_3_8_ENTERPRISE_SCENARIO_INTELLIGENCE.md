# P4.3.8 Enterprise Scenario & Simulation Intelligence

P4.3.8 adds tenant-scoped, deterministic what-if analysis without changing authoritative state. `ScenarioRequest` carries the tenant, canonical subject, scenario type, explicit change, horizon, assumptions, bounded depth, financial parameters, policy context, and requested impact dimensions. `ScenarioResult` is permanently `authoritative = false` and records baseline, ephemeral simulated state, changed dimensions, governed paths, impacts, assumptions, unknowns, confidence, evidence, partial status, and timestamp.

## Baseline and isolation

Every run reads canonical identity/version, relationship checkpoint, classification/version, Financial Data Fabric period/spend, risk/health references, and evidence references before applying a change to a new in-memory mapping. Depth is capped at five. There is no persistence port and no provider, Decision, Approval, Authorization, or Execution mutation path.

## Supported scenarios

`ACCOUNT_SUSPENSION`, `APPLICATION_RETIREMENT`, `TECHNOLOGY_RETIREMENT`, `VENDOR_FAILURE`, `BUSINESS_SERVICE_DEGRADATION`, `COST_GROWTH`, `COST_REDUCTION`, `OWNERSHIP_CHANGE`, `CLASSIFICATION_CHANGE`, `RECOMMENDATION_ACCEPTANCE`, and `POLICY_CHANGE_PREVIEW`.

Blast radius uses only governed inbound relationships. Zero paths produce `topology_state = INCOMPLETE`, `INCOMPLETE_TOPOLOGY`, an `UNKNOWN` disruptive conclusion, and no safe-to-terminate assertion.

## Financial and risk rules

Calculations preserve the exact distinction between baseline spend, simulated spend, potential savings, approved savings, executed savings, and verified realized savings. The latter three remain zero in simulation. Enterprise simulated spend is baseline enterprise spend plus the entity delta; Financial Data Fabric is unchanged. Risk is `UNKNOWN` without supporting evidence and is never invented.

## Policy, recommendation, Copilot, and authority

WP-012 preview can be injected as an optional non-authoritative result. It cannot create policy evaluation or authorization state. Recommendation alternatives can be simulated and compared without selecting a winner. Scenario results may later be packaged through WP-010 as supporting evidence, but are not approval evidence by themselves. The UI exposes explicit inputs and assumptions and labels all results `SIMULATION — NOT AUTHORIZATION`.

Persona scope is read-only: Executive receives business/financial types, CIO all analysis types, Finance financial analysis, Operations change-impact types, Auditor all read-only evidence, and Super Admin all simulation types. No persona gains execution authority.

## Performance and limitations

The service enforces a 1.5 second single-run budget and comparisons are bounded to three scenarios. Exact P50/P95 results belong to certification output. Horizons do not imply a forecast: no future projection is produced without a valid forecast model. Legacy Simulation Center remains for compatibility and should be deprecated after consumer migration. Browser certification may remain deferred under the authorized manual gate when no defect is known.

### DEV performance certification — 2026-08-13

Each operation used one excluded warm-up followed by 100 measured samples on the
local DEV certification environment. Times are milliseconds.

| Operation | Min | P50 | P95 | Max | Target | Result |
|---|---:|---:|---:|---:|---:|---|
| COST_GROWTH +20% | 0.0983 | 0.1053 | 0.1655 | 0.3385 | 500 | PASS |
| ACCOUNT_SUSPENSION, zero-edge | 0.0972 | 0.1024 | 0.1117 | 0.1275 | 1,000 | PASS |
| Three-scenario comparison | 0.3035 | 0.3214 | 0.4007 | 0.5050 | 2,500 | PASS |
| Copilot scenario explanation preparation | 0.1096 | 0.1142 | 0.1752 | 0.1959 | 1,500 | PASS |

The test preserves tenant, evidence, and authority controls and runs through the
same public service methods as application integration.

## DEV financial and authority evidence

For AWS account `727482365532`, the immutable fixture baseline is
`37143.2080151701 USD`, enterprise spend is `127678.2170275708 USD`, and the
20% simulation returns `44571.84961820412 USD`, delta
`7428.64160303402 USD`, and simulated enterprise spend
`135106.85863060484 USD`. The test snapshots and rechecks the authoritative
financial provider after simulation. Approved, executed, and verified realized
savings remain zero. Scenario results expose `authoritative = false`,
`execution_permitted = false`, `decision_created = false`, and
`authorization_created = false`; WP-012 preview fixtures also remain
non-authoritative.

## Manual browser certification matrix

Status: **MANUAL_RELEASE_GATE_PENDING**.

| Gate | Expected evidence |
|---|---|
| Overview | Page loads for an authorized persona and displays the simulation-only banner. |
| ACCOUNT_SUSPENSION | Canonical baseline is present; no action or authorization control is offered. |
| COST_GROWTH +20% | Exact baseline, simulated spend, delta, and non-authoritative enterprise total display. |
| Scenario comparison | Up to three results display side-by-side without automatic winner selection. |
| Policy preview | Preview is visibly non-authoritative and creates no Approval or Authorization. |
| INCOMPLETE_TOPOLOGY | Zero-edge subject shows explicit unknown/warning and no destructive conclusion. |
| Persona restriction | Out-of-scope scenario is rejected for the selected persona. |
| Copilot explanation | Explicit inputs, assumptions, unknowns, and simulation-only label remain visible. |
