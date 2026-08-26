"""Immutable in-memory PUE-009 answer history."""

from universal_evidence.answers.models import GovernedAnalyticalAnswer


class InMemoryAnswerRepository:
    def __init__(self) -> None:
        self._answers: dict[str, GovernedAnalyticalAnswer] = {}
        self._history: dict[tuple[str | None, ...], list[str]] = {}

    def store(self, answer: GovernedAnalyticalAnswer) -> GovernedAnalyticalAnswer:
        existing = self._answers.get(answer.fingerprint)
        if existing is not None:
            return existing
        self._answers[answer.fingerprint] = answer
        self._history.setdefault(answer.scope.key, []).append(answer.fingerprint)
        return answer

    def get_versions(
        self, scope_key: tuple[str | None, ...]
    ) -> tuple[GovernedAnalyticalAnswer, ...]:
        return tuple(self._answers[item] for item in self._history.get(scope_key, ()))
