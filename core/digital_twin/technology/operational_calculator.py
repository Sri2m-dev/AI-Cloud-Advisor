from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from core.digital_twin.technology.operational_policy import OperationalPolicy
from core.digital_twin.technology.operational_signal import OperationalSignal, OperationalSignalType, OperationalStatus
from core.digital_twin.technology.technology_node import TechnologyNode


@dataclass(frozen=True, slots=True)
class OperationalCalculationResult:
    technology_id: str
    operational_health: float
    status: str
    dimensions: dict[str, Any]
    active_incidents: list[dict[str, Any]]
    active_alerts: list[dict[str, Any]]
    recent_deployments: list[dict[str, Any]]
    open_changes: list[dict[str, Any]]
    maintenance_windows: list[dict[str, Any]]
    signals: list[dict[str, Any]]
    policy: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "technology_id": self.technology_id,
            "operational_health": self.operational_health,
            "status": self.status,
            "dimensions": self.dimensions,
            "active_incidents": self.active_incidents,
            "active_alerts": self.active_alerts,
            "recent_deployments": self.recent_deployments,
            "open_changes": self.open_changes,
            "maintenance_windows": self.maintenance_windows,
            "signals": self.signals,
            "policy": self.policy,
        }


class OperationalCalculator:
    def __init__(self, policy: OperationalPolicy | None = None):
        self.policy = policy or OperationalPolicy()

    def calculate(
        self,
        node: TechnologyNode,
        signals: list[OperationalSignal] | None = None,
    ) -> OperationalCalculationResult:
        all_signals = list(signals or [])
        active_incidents = [
            signal for signal in all_signals if signal.signal_type == OperationalSignalType.INCIDENT.value and signal.is_active()
        ]
        active_alerts = [
            signal for signal in all_signals if signal.signal_type == OperationalSignalType.ALERT.value and signal.is_active()
        ]
        recent_deployments = self._recent(
            [signal for signal in all_signals if signal.signal_type == OperationalSignalType.DEPLOYMENT.value],
            self.policy.deployment_window_days,
        )
        open_changes = [
            signal for signal in all_signals if signal.signal_type == OperationalSignalType.CHANGE.value and signal.is_active()
        ]
        maintenance_windows = [
            signal
            for signal in all_signals
            if signal.signal_type == OperationalSignalType.MAINTENANCE.value and signal.is_active()
        ]
        performance_degradations = [
            signal
            for signal in all_signals
            if signal.signal_type == OperationalSignalType.PERFORMANCE_DEGRADATION.value and signal.is_active()
        ]

        availability_trend = self._availability_trend(all_signals)
        mttr = self._mttr(all_signals)
        mtbf = self._mtbf(all_signals)
        stability = self._stability_score(active_incidents, active_alerts, performance_degradations, mttr, mtbf)
        health = self._health_score(
            active_incidents,
            active_alerts,
            performance_degradations,
            open_changes,
            maintenance_windows,
            availability_trend,
            stability,
        )

        dimensions = {
            "Open Incidents": len(active_incidents),
            "Active Alerts": len(active_alerts),
            "Recent Deployments": len(recent_deployments),
            "Open Changes": len(open_changes),
            "Maintenance Windows": len(maintenance_windows),
            "Performance Degradation": len(performance_degradations),
            "Availability Trend": availability_trend,
            "MTTR": mttr,
            "MTBF": mtbf,
            "Operational Stability": stability,
        }
        return OperationalCalculationResult(
            technology_id=str(node.technology_id),
            operational_health=health,
            status=self.policy.status_for_health(health),
            dimensions=dimensions,
            active_incidents=[signal.to_dict() for signal in active_incidents],
            active_alerts=[signal.to_dict() for signal in active_alerts],
            recent_deployments=[signal.to_dict() for signal in recent_deployments],
            open_changes=[signal.to_dict() for signal in open_changes],
            maintenance_windows=[signal.to_dict() for signal in maintenance_windows],
            signals=[signal.to_dict() for signal in all_signals],
            policy=self.policy.to_dict(),
        )

    def apply_to_node(
        self,
        node: TechnologyNode,
        signals: list[OperationalSignal] | None = None,
    ) -> OperationalCalculationResult:
        result = self.calculate(node, signals)
        node.metadata["operational_breakdown"] = result.to_dict()
        node.metadata["open_alerts"] = result.dimensions["Active Alerts"]
        node.metadata["incidents"] = result.dimensions["Open Incidents"]
        node.metadata["deployments"] = result.dimensions["Recent Deployments"]
        node.metadata["changes"] = result.dimensions["Open Changes"]
        node.metadata["maintenance"] = result.dimensions["Maintenance Windows"]
        node.metadata["operational_health"] = result.operational_health
        node.metadata["operational_status"] = result.status
        if node.health:
            node.health.operational_score = result.operational_health
        node.refresh_state()
        return result

    def _health_score(
        self,
        active_incidents: list[OperationalSignal],
        active_alerts: list[OperationalSignal],
        performance_degradations: list[OperationalSignal],
        open_changes: list[OperationalSignal],
        maintenance_windows: list[OperationalSignal],
        availability_trend: float,
        stability: float,
    ) -> float:
        penalty = sum(
            self.policy.incident_penalty * self.policy.severity_multiplier(signal.severity) * signal.confidence_score
            for signal in active_incidents
        )
        penalty += sum(
            self.policy.alert_penalty * self.policy.severity_multiplier(signal.severity) * signal.confidence_score
            for signal in active_alerts
        )
        penalty += sum(
            self.policy.performance_penalty * self.policy.severity_multiplier(signal.severity) * signal.confidence_score
            for signal in performance_degradations
        )
        penalty += sum(
            self.policy.change_penalty * self.policy.severity_multiplier(signal.severity) * signal.confidence_score
            for signal in open_changes
        )
        penalty += sum(
            self.policy.maintenance_penalty * self.policy.severity_multiplier(signal.severity) * signal.confidence_score
            for signal in maintenance_windows
        )
        raw_health = min(self.policy.base_health - penalty, availability_trend, stability)
        return round(max(0.0, min(100.0, raw_health)), 2)

    def _stability_score(
        self,
        active_incidents: list[OperationalSignal],
        active_alerts: list[OperationalSignal],
        performance_degradations: list[OperationalSignal],
        mttr: float,
        mtbf: float,
    ) -> float:
        incident_pressure = len(active_incidents) * 12.0
        alert_pressure = len(active_alerts) * 5.0
        performance_pressure = len(performance_degradations) * 8.0
        mttr_pressure = min(20.0, max(0.0, mttr - self.policy.mttr_target_minutes) / self.policy.mttr_target_minutes * 20)
        mtbf_bonus = min(10.0, max(0.0, mtbf - self.policy.mtbf_target_minutes) / self.policy.mtbf_target_minutes * 10)
        return round(max(0.0, min(100.0, 100.0 - incident_pressure - alert_pressure - performance_pressure - mttr_pressure + mtbf_bonus)), 2)

    def _availability_trend(self, signals: list[OperationalSignal]) -> float:
        availability_values = []
        for signal in signals:
            if signal.signal_type != OperationalSignalType.AVAILABILITY.value:
                continue
            value = _number(signal.metadata, "availability", "value", "score", default=None)
            if value is not None:
                availability_values.append(value)
        if not availability_values:
            return 100.0
        return round(max(0.0, min(100.0, sum(availability_values) / len(availability_values))), 2)

    def _mttr(self, signals: list[OperationalSignal]) -> float:
        resolved = [
            signal.duration
            for signal in signals
            if signal.signal_type == OperationalSignalType.INCIDENT.value
            and signal.status in {OperationalStatus.RESOLVED.value, OperationalStatus.CLOSED.value}
            and signal.duration > 0
        ]
        return round(sum(resolved) / len(resolved), 2) if resolved else 0.0

    def _mtbf(self, signals: list[OperationalSignal]) -> float:
        values = [
            value
            for value in (_number(signal.metadata, "mtbf", "mtbf_minutes", default=None) for signal in signals)
            if value is not None
        ]
        return round(sum(values) / len(values), 2) if values else self.policy.mtbf_target_minutes

    def _recent(self, signals: list[OperationalSignal], window_days: int) -> list[OperationalSignal]:
        now = datetime.now(timezone.utc)
        recent = []
        for signal in signals:
            parsed = _parse_datetime(signal.event_time)
            if parsed is None or (now - parsed).days <= window_days:
                recent.append(signal)
        return sorted(recent, key=lambda signal: signal.event_time, reverse=True)


def _number(metadata: dict[str, Any], *keys: str, default: float | None) -> float | None:
    for key in keys:
        value = metadata.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
