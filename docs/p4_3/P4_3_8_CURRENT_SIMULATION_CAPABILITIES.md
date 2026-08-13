# P4.3.8 Current Simulation Capabilities

| Capability | Classification | P4.3.8 treatment |
|---|---|---|
| `services/simulation_service.py` deterministic calculation and exports | ADAPT | Calculation/reporting concepts reused; persistence, synthetic approvals, and action-oriented conclusions are excluded from the canonical service. |
| `pages/simulation_center.py` | DEPRECATE-LATER | Remains available for compatibility; Scenario Intelligence is the governed entry point. |
| `services/impact_analysis_service.py` and graph impact scoring | ADAPT | Presentation/scoring concepts retained, but blast radius comes only from governed P4.3.2 relationships. |
| Enterprise Registry and Relationship Intelligence | REUSE | Canonical baseline, versions, classification, evidence, and bounded paths. |
| Enterprise Knowledge Graph / Intelligence Query | REUSE | Existing read models remain the source of governed enterprise context. |
| Financial Data Fabric | REUSE | Authoritative baseline provider; simulated totals remain ephemeral and non-authoritative. |
| WP-011 Recommendation/Decision | REUSE | Recommendation alternatives may be simulated; no Decision is created or mutated. |
| WP-012 Policy Preview | REUSE | Optional injected preview result only; no evaluation, approval, or authorization is persisted. |
| WP-013 execution/outcome contracts | OUT-OF-SCOPE | Used only to preserve naming boundaries for executed and verified realized savings. |
| Predictive, forecasting, and capacity services | OUT-OF-SCOPE | Horizons are accepted only as context; P4.3.8 does not fabricate unsupported forecasts. |
| Legacy simulation persistence repository | DEPRECATE-LATER | Not called by the governed service. |

The canonical P4.3.8 service exposes no persistence, connector-write, approval, decision, authorization, or execution interface.
