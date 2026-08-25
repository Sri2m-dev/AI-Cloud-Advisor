"""Immutable in-memory PUE-005 assessment repository."""

from universal_evidence.capability.models import (
    AssessmentState,
    CapabilityAssessment,
    ExecutionAuthorization,
)


class InMemoryCapabilityRepository:
    def __init__(self) -> None:
        self._by_fingerprint: dict[str, CapabilityAssessment] = {}
        self._by_scope: dict[tuple[str | None, ...], list[str]] = {}
        self._by_id: dict[str, CapabilityAssessment] = {}
        self._current_by_scope: dict[tuple[str | None, ...], str] = {}

    def store(self, assessment: CapabilityAssessment) -> CapabilityAssessment:
        existing = self._by_fingerprint.get(assessment.fingerprint)
        if existing is not None:
            return existing
        self._by_fingerprint[assessment.fingerprint] = assessment
        self._by_id[assessment.assessment_id] = assessment
        self._by_scope.setdefault(assessment.scope.key, []).append(assessment.fingerprint)
        self._current_by_scope[assessment.scope.key] = assessment.assessment_id
        return assessment

    def get_versions(self, scope_key: tuple[str | None, ...]) -> tuple[CapabilityAssessment, ...]:
        return tuple(self._by_fingerprint[item] for item in self._by_scope.get(scope_key, ()))

    def get_current_assessment(
        self, scope_key: tuple[str | None, ...], capability_id: str | None = None
    ) -> CapabilityAssessment | None:
        assessment_id = self._current_by_scope.get(scope_key)
        if assessment_id is None:
            return None
        assessment = self._by_id[assessment_id]
        if capability_id is not None and not any(
            item.capability_id == capability_id for item in assessment.capabilities
        ):
            return None
        return assessment

    def get_assessment_state(self, assessment_id: str) -> AssessmentState:
        assessment = self._by_id.get(assessment_id)
        if assessment is None:
            return AssessmentState.STALE
        current_id = self._current_by_scope.get(assessment.scope.key)
        return (
            AssessmentState.CURRENT if current_id == assessment_id else AssessmentState.SUPERSEDED
        )

    def is_authorization_current(self, authorization: ExecutionAuthorization) -> bool:
        current = self.get_current_assessment(authorization.scope.key, authorization.capability_id)
        return bool(
            current
            and current.assessment_id == authorization.capability_assessment_id
            and current.fingerprint == authorization.assessment_fingerprint
            and authorization in current.execution_authorizations
        )
