"""Immutable in-memory PUE-006 result repository."""

from universal_evidence.aggregation.models import GovernedAggregationResult


class InMemoryAggregationRepository:
    def __init__(self) -> None:
        self._results: dict[str, GovernedAggregationResult] = {}
        self._history: dict[tuple[str | None, ...], list[str]] = {}

    def store(self, result: GovernedAggregationResult) -> GovernedAggregationResult:
        existing = self._results.get(result.result_fingerprint)
        if existing is not None:
            return existing
        self._results[result.result_fingerprint] = result
        self._history.setdefault(result.scope.key, []).append(result.result_fingerprint)
        return result

    def get_versions(
        self, scope_key: tuple[str | None, ...]
    ) -> tuple[GovernedAggregationResult, ...]:
        return tuple(self._results[item] for item in self._history.get(scope_key, ()))
