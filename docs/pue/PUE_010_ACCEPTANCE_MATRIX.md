# PUE-010 Acceptance Matrix

| Scenario | Structural/semantic outcome | Governed downstream outcome | Expected shadow state |
|---|---|---|---|
| Fully governed CSV | Complete | Grouped cost executes and composes certified values | `SHADOW_COMPLETE` |
| 184-row missing currency | 184 rows observed; cost candidate available | Total blocked; no execution; `861828` absent | `SHADOW_COMPLETE_WITH_BLOCKED_QUERY` |
| Mixed enterprise CSV | Multiple domain candidates retained | Only explicitly governed concepts progress | Bounded by supplied decisions |
| Multi-sheet XLSX | Sheets profiled independently | Only governed sheet/column values progress | Complete or partial per sheet |
| Irregular XLSX | Warnings for merged cells, duplicate/repeated headers, sparse regions, and formulas | Missing structure is not inferred | `PARTIAL` or `BLOCKED` |
| Missing currency | Cost may normalize | Monetary total blocked | `SHADOW_COMPLETE_WITH_BLOCKED_QUERY` |
| Mixed currency | Explicit currencies retained | Single total blocked; no FX | Blocked by design |
| Invalid values | Invalid row preserved | Capability policy decides; no zero coercion | `PARTIAL` or blocked |
| Ambiguous semantics | Candidates remain ambiguous | No effective mapping, normalization skipped | `SHADOW_BLOCKED` |
| Rejected mapping | Decision history retained | No normalization/capability from column | `SHADOW_BLOCKED` |
| Override mapping | Original ranking retained | Effective overridden concept alone progresses | Governed by override |
| Low coverage | Coverage partial/insufficient | Authorization follows PUE-005 policy | Partial or blocked |
| Unsupported question | PUE-008 unsupported | Planning/execution skipped; explanation only | `SHADOW_COMPLETE_WITH_UNSUPPORTED_QUERY` |
| Ambiguous question | PUE-008 ambiguous | Planning/execution skipped | `SHADOW_COMPLETE_WITH_AMBIGUOUS_QUERY` |
| Ranking question | Unsupported operation | No grouped-sum approximation | Unsupported |
| Stale authorization | Current assessment mismatch | Rejected before execution | Failed closed |
| Cross-analysis | Scope mismatch | No reuse | Failed closed |
| Cross-prospect | Distinct scope/fingerprint | No reuse | Isolated |
| Cross-tenant | Distinct scope/fingerprint | No reuse | Isolated |
| Prospect-only scope | Organization and tenant remain absent | No session enrichment | Preserved |
| Deterministic replay | Same certified inputs | Equivalent stage and shadow fingerprints | Identical |
| Purge / retention | Analysis expires | Local shadow artifacts unavailable | Purged |
| Injection question | Untrusted amount remains question text only | No injected factual value | Governed outcome only |
| Legacy comparison | Legacy reference is comparison evidence | No legacy learning or fallback | Non-authoritative comparison |

## Certification interpretation

A mismatch with legacy is not itself an error. For the 184-row case, legacy may expose `861828` while PUE correctly blocks monetary aggregation because governed currency evidence is absent. This is `PUE_BLOCKED` / different by design, never a reason to copy the legacy total into the shadow chain.
