"""Append-only, analysis-partitioned in-memory decision repository."""

from universal_evidence.governance.models import (
    ConfirmationRequest,
    DecisionScope,
    MappingDecision,
    MappingDecisionHistory,
    MappingDecisionState,
)


class InMemoryMappingDecisionRepository:
    def __init__(self) -> None:
        self._history: dict[tuple[str | None, ...], list[MappingDecision]] = {}
        self._effective: dict[tuple[str | None, ...], str] = {}
        self._requests: dict[str, ConfirmationRequest] = {}

    def save_request(self, request: ConfirmationRequest) -> ConfirmationRequest:
        existing = self._requests.get(request.request_fingerprint)
        if existing is not None:
            return existing
        self._requests[request.request_fingerprint] = request
        return request

    def find_request(self, fingerprint_value: str) -> ConfirmationRequest | None:
        return self._requests.get(fingerprint_value)

    def append(self, decision: MappingDecision) -> MappingDecision:
        rows = self._history.setdefault(decision.scope.key, [])
        existing = next(
            (
                item
                for item in rows
                if item.decision_fingerprint == decision.decision_fingerprint
            ),
            None,
        )
        if existing is not None:
            return existing
        rows.append(decision)
        if decision.decision_state in {
            MappingDecisionState.AUTO_ACCEPTED,
            MappingDecisionState.CONFIRMED,
            MappingDecisionState.OVERRIDDEN,
        }:
            self._effective[decision.scope.key] = decision.decision_id
        elif decision.decision_state in {
            MappingDecisionState.REJECTED,
            MappingDecisionState.EXPIRED,
        }:
            self._effective.pop(decision.scope.key, None)
        return decision

    def history(self, scope: DecisionScope) -> MappingDecisionHistory:
        return MappingDecisionHistory(scope, tuple(self._history.get(scope.key, ())))

    def effective(self, scope: DecisionScope) -> MappingDecision | None:
        decision_id = self._effective.get(scope.key)
        if decision_id is None:
            return None
        return next(
            item
            for item in self._history.get(scope.key, ())
            if item.decision_id == decision_id
        )
