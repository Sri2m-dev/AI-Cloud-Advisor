"""Non-authoritative legacy/shadow comparison contract."""

from universal_evidence.answers import AnswerState
from universal_evidence.shadow.fingerprint import fingerprint
from universal_evidence.shadow.models import ComparisonState, ShadowComparisonResult


def compare_with_legacy(*, legacy_reference, shadow_question):
    answer = shadow_question.answer
    if legacy_reference is None and answer is None:
        state = ComparisonState.NOT_COMPARABLE
    elif legacy_reference is None:
        state = ComparisonState.PUE_ONLY
    elif answer is None:
        state = ComparisonState.LEGACY_ONLY
    elif answer.answer_state is AnswerState.BLOCKED:
        state = ComparisonState.PUE_BLOCKED
    else:
        state = ComparisonState.NOT_COMPARABLE
    explanation = "Legacy output is comparison evidence only; no value was copied into PUE."
    identity = fingerprint(legacy_reference, shadow_question.fingerprint, state, explanation)
    return ShadowComparisonResult(
        "shadow-comparison-" + identity[:24],
        state,
        legacy_reference,
        answer.answer_id if answer is not None else None,
        explanation,
        identity,
    )
