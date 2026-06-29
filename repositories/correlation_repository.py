from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from core.correlation.correlation_event import CorrelationEvent
from core.correlation.correlation_result import CorrelationResult
from core.correlation.correlation_rule import CorrelationRule


DEFAULT_CORRELATION_STORE = Path("data/correlation_engine.json")


class CorrelationRepository:
    def __init__(self, store_path: str | Path = DEFAULT_CORRELATION_STORE):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._events: dict[UUID, CorrelationEvent] = {}
        self._rules: dict[UUID, CorrelationRule] = {}
        self._results: dict[UUID, CorrelationResult] = {}
        self._load()

    def save_event(self, event: CorrelationEvent) -> CorrelationEvent:
        self._events[event.id] = event
        self._persist()
        return event

    def get_event(self, event_id: UUID | str) -> CorrelationEvent | None:
        return self._events.get(UUID(str(event_id)))

    def list_events(
        self,
        organization_id: UUID | str | None = None,
        event_type: str | None = None,
    ) -> list[CorrelationEvent]:
        events = list(self._events.values())
        if organization_id:
            resolved_org_id = UUID(str(organization_id))
            events = [event for event in events if event.organization_id == resolved_org_id]
        if event_type:
            events = [event for event in events if event.event_type == event_type]
        return sorted(events, key=lambda event: event.occurred_at, reverse=True)

    def link_event_to_entity(self, event_id: UUID | str, entity_id: UUID | str) -> CorrelationEvent:
        event = self.get_event(event_id)
        if not event:
            raise KeyError(f"Correlation event not found: {event_id}")
        event.link_entity(entity_id)
        self._persist()
        return event

    def find_events_for_entity(self, entity_id: UUID | str) -> list[CorrelationEvent]:
        resolved_id = UUID(str(entity_id))
        return sorted(
            [event for event in self._events.values() if resolved_id in event.entity_ids],
            key=lambda event: event.occurred_at,
            reverse=True,
        )

    def find_related_events(self, event_id: UUID | str) -> list[CorrelationEvent]:
        event = self.get_event(event_id)
        if not event:
            raise KeyError(f"Correlation event not found: {event_id}")
        related_entity_ids = set(event.entity_ids)
        return sorted(
            [
                candidate
                for candidate in self._events.values()
                if candidate.id != event.id and related_entity_ids.intersection(candidate.entity_ids)
            ],
            key=lambda candidate: candidate.occurred_at,
            reverse=True,
        )

    def save_rule(self, rule: CorrelationRule) -> CorrelationRule:
        self._rules[rule.id] = rule
        self._persist()
        return rule

    def list_rules(self, active_only: bool = True) -> list[CorrelationRule]:
        rules = list(self._rules.values())
        if active_only:
            rules = [rule for rule in rules if rule.active]
        return sorted(rules, key=lambda rule: rule.name.lower())

    def save_result(self, result: CorrelationResult) -> CorrelationResult:
        self._results[result.id] = result
        self._persist()
        return result

    def list_results(self, entity_id: UUID | str | None = None) -> list[CorrelationResult]:
        results = list(self._results.values())
        if entity_id:
            resolved_id = UUID(str(entity_id))
            results = [result for result in results if resolved_id in result.entity_ids]
        return sorted(results, key=lambda result: result.created_at, reverse=True)

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        payload = json.loads(self.store_path.read_text(encoding="utf-8") or "{}")
        self._events = {
            UUID(item["id"]): CorrelationEvent.from_dict(item)
            for item in payload.get("events", [])
        }
        self._rules = {
            UUID(item["id"]): CorrelationRule.from_dict(item)
            for item in payload.get("rules", [])
        }
        self._results = {
            UUID(item["id"]): CorrelationResult.from_dict(item)
            for item in payload.get("results", [])
        }

    def _persist(self) -> None:
        payload = {
            "events": [event.to_dict() for event in self.list_events()],
            "rules": [rule.to_dict() for rule in self.list_rules(active_only=False)],
            "results": [result.to_dict() for result in self.list_results()],
        }
        self.store_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
