"""Immutable in-memory PUE-007 plan history."""

from universal_evidence.planning.models import AnalyticalPlan


class InMemoryAnalyticalPlanRepository:
    def __init__(self) -> None:
        self._plans: dict[str, AnalyticalPlan] = {}
        self._history: dict[tuple[str | None, ...], list[str]] = {}

    def store(self, plan: AnalyticalPlan) -> AnalyticalPlan:
        existing = self._plans.get(plan.plan_fingerprint)
        if existing is not None:
            return existing
        self._plans[plan.plan_fingerprint] = plan
        self._history.setdefault(plan.scope.key, []).append(plan.plan_fingerprint)
        return plan

    def get_versions(self, scope_key: tuple[str | None, ...]) -> tuple[AnalyticalPlan, ...]:
        return tuple(self._plans[item] for item in self._history.get(scope_key, ()))
