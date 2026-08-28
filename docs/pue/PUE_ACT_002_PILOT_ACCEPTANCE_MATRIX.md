# PUE-ACT-002 Pilot Acceptance Matrix

| Scenario | Stage 1 discovery | Stage 2 capability | Numerical PUE result | Required behavior |
|---|---:|---:|---:|---|
| No activation config | Hidden | Hidden | Never | Preserve current prospect UI exactly |
| Stage 1 activation | Visible | Hidden | Never | Show governed evidence states only |
| Stage 2 activation | Visible | Visible | Never | Show registered capability states/reasons |
| Stage 3/4 configured | Visible | Visible | Never | ACT-002 caps presentation at Stage 2 |
| Global kill switch | Hidden | Hidden | Never | Immediate suppression; prospect unaffected |
| Expired activation | Hidden or less-specific effective stage | Governed by effective stage | Never | Resolver remains authoritative |
| Scope/fingerprint mismatch | Hidden | Hidden | Never | Reject stale or cross-analysis artifacts |
| Shadow failure | Safe unavailable state when enabled | No stale capability data | Never | Isolate failure from prospect flow |
| Fully governed service/cost/currency | Available concepts | Supported capabilities where certified | Never | Do not expose PUE calculation |
| 184 costs, currency absent | Cost evidenced; currency absent | Monetary total blocked | Never | May show 184 records; never show 861828 |
| Mixed currency | Currency conflicted | Single monetary total blocked | Never | No FX or combined total |
| Sparse/partial evidence | Partial/insufficient states | Partial/blocked as certified | Never | Preserve uncertainty |
| Ambiguous/rejected mapping | No effective governed evidence | Dependent capability unsupported/blocked | Never | Do not expose semantic candidates |
| Prospect-only evidence scope | Visible only under matching prospect/analysis | Same | Never | Do not enrich from logged-in tenant/org |
| Restart prospect journey | Cleared | Cleared | Never | Remove all page-level pilot artifacts |

## Certification assertions

- The accepted prospect pipeline remains authoritative and unmodified.
- Every visible pilot state is derived from PUE-C10 governed contracts.
- Page code does not calculate, classify, normalize, route, or answer.
- Stage 0 leaves no pilot markup or spacing.
- Stage 2 does not imply that every capability is supported.
- Unsupported security, criticality, SLA, optimization, and recommendation
  concepts remain explicitly not evidenced or outside the pilot.
- Telemetry and audit contain state transitions and counters, not source values.
- Existing malware, encryption, retention, RBAC, tenant isolation, connector,
  prospect isolation, and session-bridge behavior remain regression protected.

## Activation boundary after ACT-C2

Passing this matrix permits only a limited Stage 1/2 pilot. It does not authorize
Stage 3 answers, Stage 4 Ask Nexora routing, broader PUE authority, or replacement
of the current prospect analysis.
