# PUE-ACT-001 Rollback and Kill Switch

Rollback appends a lower-stage configuration and preserves the prior configuration as superseded history. It requires `TRIGGER_PUE_ROLLBACK`, an administrative actor, and a reason. It requires no migration rollback, deployment, branch reset, or session mutation.

The global kill switch is append-only, actor-attributed, audited, and resolved before all scoped configuration. When enabled:

- effective stage becomes `SHADOW_ONLY`;
- all PUE-visible flags and production routing are disabled;
- shadow execution may continue only when the kill-switch policy permits it;
- fallback is explicit, normally `LEGACY_AUTHORITATIVE`.

Turning the kill switch off restores ordinary scope resolution; it does not erase history.

## Fallback policies

- `LEGACY_AUTHORITATIVE`: select legacy when available, otherwise block.
- `PUE_IF_CERTIFIED_ELSE_LEGACY`: select PUE only after all certified gates; otherwise legacy when available.
- `PUE_IF_CERTIFIED_ELSE_BLOCKED`: never fall back to legacy for the governed route.
- `SHADOW_COMPARE_ONLY`: never surface PUE; retain separate comparison telemetry.

Failures, ambiguity, blocked capabilities, and unsupported questions apply the configured policy. Legacy and PUE values are never merged.

## Immediate rollback triggers

Any scope-isolation defect, wrong factual answer, missing provenance, retention/audit failure, or session impact requires the kill switch and immediate rollback. Error, fallback, or latency threshold breaches require at least stage reduction and investigation under the pilot policy.
