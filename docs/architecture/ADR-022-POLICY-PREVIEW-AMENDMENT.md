# ADR-022 Amendment: Non-authoritative Policy Preview

WP-012 exposes `PolicyApprovalService.preview()` as a pre-Decision simulation.
It reuses the exact deterministic rule evaluator used by authoritative
`evaluate()`, but returns the structurally distinct `PolicyPreviewResult` whose
`authoritative` field is permanently false.

Preview requires an exact tenant-scoped Proposed/Under Review Recommendation,
immutable approved evidence package and hash, policy version, scope, actor, and
inputs. Missing, stale, conflicting, or superseded evidence fails closed.

Preview creates no Decision, PolicyEvaluation, Approval, Exception,
Authorization, or Execution state. WP-013 cannot consume a preview result.
Authoritative evaluation remains post-Decision and unchanged in purpose.
