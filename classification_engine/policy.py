"""Classification, approval, financial-release, and allocation boundaries."""

from classification_engine.models import ApprovalStatus, ClassificationPolicy, InferenceStatus


def inference_outcome(*, confidence: float, conflict: bool, policy: ClassificationPolicy):
    if conflict or confidence < policy.minimum_inference_confidence:
        return InferenceStatus.NEEDS_REVIEW, ApprovalStatus.NEEDS_APPROVAL
    if policy.auto_approval_enabled and confidence >= policy.minimum_auto_approval_confidence:
        return InferenceStatus.RESOLVED_APPROVED, ApprovalStatus.AUTO_APPROVED
    return InferenceStatus.RESOLVED_INFERRED, ApprovalStatus.NEEDS_APPROVAL


def may_release_spend(status: InferenceStatus, policy: ClassificationPolicy) -> bool:
    return status is InferenceStatus.RESOLVED_APPROVED or (
        status is InferenceStatus.RESOLVED_INFERRED and policy.allow_provisional_spend_release
    )


def may_allocate(status: InferenceStatus, policy: ClassificationPolicy) -> bool:
    return status is InferenceStatus.RESOLVED_APPROVED or (
        status is InferenceStatus.RESOLVED_INFERRED and policy.allow_allocation_before_approval
    )
