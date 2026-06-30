from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from core.digital_twin.technology import CostSignal, HealthSignal, InfrastructureLayer, RiskSignal, TechnologyTwin


DEFAULT_TECHNOLOGY_TWIN_STORE = Path("data/technology_digital_twins.json")


class TechnologyTwinRepository:
    def __init__(self, store_path: str | Path = DEFAULT_TECHNOLOGY_TWIN_STORE):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._twins: dict[UUID, TechnologyTwin] = {}
        self._health_signals: dict[UUID, list[HealthSignal]] = {}
        self._cost_signals: dict[UUID, list[CostSignal]] = {}
        self._risk_signals: dict[UUID, list[RiskSignal]] = {}
        self._load()

    def save(self, twin: TechnologyTwin) -> TechnologyTwin:
        self._twins[twin.id] = twin
        self._persist()
        return twin

    def get(self, twin_id: UUID | str) -> TechnologyTwin | None:
        return self._twins.get(UUID(str(twin_id)))

    def latest_for_organization(self, organization_id: UUID | str) -> TechnologyTwin | None:
        resolved_id = UUID(str(organization_id))
        twins = [twin for twin in self._twins.values() if twin.organization_id == resolved_id]
        if not twins:
            return None
        return sorted(twins, key=lambda twin: twin.generated_at, reverse=True)[0]

    def list_for_organization(self, organization_id: UUID | str) -> list[TechnologyTwin]:
        resolved_id = UUID(str(organization_id))
        return sorted(
            [twin for twin in self._twins.values() if twin.organization_id == resolved_id],
            key=lambda twin: twin.generated_at,
            reverse=True,
        )

    def get_infrastructure_layer(
        self,
        organization_id: UUID | str,
        technology_id: UUID | str,
    ) -> InfrastructureLayer | None:
        twin = self.latest_for_organization(organization_id)
        if not twin:
            return None
        node = twin.nodes.get(UUID(str(technology_id)))
        return node.infrastructure_layer if node else None

    def save_infrastructure_layer(
        self,
        organization_id: UUID | str,
        technology_id: UUID | str,
        layer: InfrastructureLayer,
    ) -> TechnologyTwin:
        twin = self.latest_for_organization(organization_id)
        if not twin:
            raise KeyError(f"Technology twin not found for organization: {organization_id}")
        node = twin.nodes.get(UUID(str(technology_id)))
        if not node:
            raise KeyError(f"Technology node not found: {technology_id}")
        node.infrastructure_layer = layer
        twin.refresh()
        return self.save(twin)

    def save_health_signal(self, signal: HealthSignal) -> HealthSignal:
        self._health_signals.setdefault(signal.technology_id, []).append(signal)
        self._persist()
        return signal

    def list_health_signals(self, technology_id: UUID | str | None = None) -> list[HealthSignal]:
        if technology_id is not None:
            return list(self._health_signals.get(UUID(str(technology_id)), []))
        signals: list[HealthSignal] = []
        for entries in self._health_signals.values():
            signals.extend(entries)
        return sorted(signals, key=lambda signal: signal.last_observed, reverse=True)

    def get_degraded_technologies(self, organization_id: UUID | str, threshold: float = 70.0) -> list[dict]:
        twin = self.latest_for_organization(organization_id)
        if not twin:
            return []
        return [
            {
                "technology_id": str(node.technology_id),
                "name": node.name,
                "status": node.status,
                "health": node.state.health_score if node.state else 100.0,
                "risk": node.risk,
            }
            for node in twin.nodes.values()
            if node.state and node.state.health_score < threshold
        ]

    def save_cost_signal(self, signal: CostSignal) -> CostSignal:
        self._cost_signals.setdefault(signal.technology_id, []).append(signal)
        self._persist()
        return signal

    def list_cost_signals(self, technology_id: UUID | str | None = None) -> list[CostSignal]:
        if technology_id is not None:
            return list(self._cost_signals.get(UUID(str(technology_id)), []))
        signals: list[CostSignal] = []
        for entries in self._cost_signals.values():
            signals.extend(entries)
        return sorted(signals, key=lambda signal: signal.observed_at, reverse=True)

    def save_risk_signal(self, signal: RiskSignal) -> RiskSignal:
        self._risk_signals.setdefault(signal.technology_id, []).append(signal)
        self._persist()
        return signal

    def list_risk_signals(self, technology_id: UUID | str | None = None) -> list[RiskSignal]:
        if technology_id is not None:
            return list(self._risk_signals.get(UUID(str(technology_id)), []))
        signals: list[RiskSignal] = []
        for entries in self._risk_signals.values():
            signals.extend(entries)
        return sorted(signals, key=lambda signal: signal.last_observed, reverse=True)

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        payload = json.loads(self.store_path.read_text(encoding="utf-8") or "{}")
        self._twins = {
            UUID(item["id"]): TechnologyTwin.from_dict(item)
            for item in payload.get("technology_twins", [])
        }
        self._health_signals = {}
        for item in payload.get("health_signals", []):
            signal = HealthSignal.from_dict(item)
            self._health_signals.setdefault(signal.technology_id, []).append(signal)
        self._cost_signals = {}
        for item in payload.get("cost_signals", []):
            signal = CostSignal.from_dict(item)
            self._cost_signals.setdefault(signal.technology_id, []).append(signal)
        self._risk_signals = {}
        for item in payload.get("risk_signals", []):
            signal = RiskSignal.from_dict(item)
            self._risk_signals.setdefault(signal.technology_id, []).append(signal)

    def _persist(self) -> None:
        payload = {
            "technology_twins": [
                twin.to_dict()
                for twin in sorted(self._twins.values(), key=lambda item: item.generated_at, reverse=True)
            ],
            "health_signals": [signal.to_dict() for signal in self.list_health_signals()],
            "cost_signals": [signal.to_dict() for signal in self.list_cost_signals()],
            "risk_signals": [signal.to_dict() for signal in self.list_risk_signals()],
        }
        self.store_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
