"""Immutable in-memory PUE-005 assessment repository."""

from universal_evidence.capability.models import CapabilityAssessment


class InMemoryCapabilityRepository:
    def __init__(self) -> None:
        self._by_fingerprint: dict[str, CapabilityAssessment] = {}
        self._by_scope: dict[tuple[str | None, ...], list[str]] = {}

    def store(self, assessment: CapabilityAssessment) -> CapabilityAssessment:
        existing = self._by_fingerprint.get(assessment.fingerprint)
        if existing is not None:
            return existing
        self._by_fingerprint[assessment.fingerprint] = assessment
        self._by_scope.setdefault(assessment.scope.key, []).append(assessment.fingerprint)
        return assessment

    def get_versions(self, scope_key: tuple[str | None, ...]) -> tuple[CapabilityAssessment, ...]:
        return tuple(self._by_fingerprint[item] for item in self._by_scope.get(scope_key, ()))
