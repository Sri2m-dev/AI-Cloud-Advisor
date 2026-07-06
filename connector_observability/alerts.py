"""Connector observability alert rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Mapping

from connector_observability.metrics import ConnectorMetricsSnapshot
from connector_sdk import ConnectorHealthStatus, ConnectorSyncResult, ConnectorSyncState


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertRuleType(str, Enum):
    CONSECUTIVE_FAILURES = "consecutive_failures"
    AUTHENTICATION_EXPIRED = "authentication_expired"
    QUEUE_BACKLOG = "queue_backlog"
    SYNC_DURATION_THRESHOLD = "sync_duration_threshold"
    HEALTH_SCORE_BELOW_THRESHOLD = "health_score_below_threshold"
    NO_SUCCESSFUL_SYNC_WITHIN_SLA = "no_successful_sync_within_sla"


@dataclass(frozen=True)
class ConnectorAlertRule:
    """Declarative connector alert rule."""

    rule_id: str
    rule_type: AlertRuleType
    threshold: float
    severity: AlertSeverity = AlertSeverity.WARNING
    enabled: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorAlert:
    """Alert emitted from connector health, queue, sync, or metrics state."""

    connector_id: str
    rule_id: str
    rule_type: AlertRuleType
    severity: AlertSeverity
    message: str
    observed_value: float | str | None = None
    threshold: float | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ConnectorAlertEngine:
    """Evaluate alert rules against connector observability snapshots."""

    def evaluate(
        self,
        connector_id: str,
        rules: list[ConnectorAlertRule],
        *,
        metrics: ConnectorMetricsSnapshot | None = None,
        health: ConnectorHealthStatus | None = None,
        sync_state: ConnectorSyncResult | None = None,
        queue_depth: int | None = None,
        now: datetime | None = None,
    ) -> list[ConnectorAlert]:
        now = now or datetime.now(timezone.utc)
        alerts: list[ConnectorAlert] = []
        for rule in rules:
            if not rule.enabled:
                continue
            alert = self._evaluate_rule(connector_id, rule, metrics=metrics, health=health, sync_state=sync_state, queue_depth=queue_depth, now=now)
            if alert is not None:
                alerts.append(alert)
        return alerts

    def _evaluate_rule(
        self,
        connector_id: str,
        rule: ConnectorAlertRule,
        *,
        metrics: ConnectorMetricsSnapshot | None,
        health: ConnectorHealthStatus | None,
        sync_state: ConnectorSyncResult | None,
        queue_depth: int | None,
        now: datetime,
    ) -> ConnectorAlert | None:
        if rule.rule_type == AlertRuleType.CONSECUTIVE_FAILURES:
            value = health.consecutive_failures if health else 0
            return self._alert_if(value > rule.threshold, connector_id, rule, value, "Consecutive connector failures exceed threshold.")
        if rule.rule_type == AlertRuleType.AUTHENTICATION_EXPIRED:
            expired = bool(health and "auth" in health.status.lower() and "expired" in health.status.lower())
            return self._alert_if(expired, connector_id, rule, "expired", "Connector authentication appears expired.")
        if rule.rule_type == AlertRuleType.QUEUE_BACKLOG:
            value = queue_depth if queue_depth is not None else (metrics.queue_depth if metrics else 0)
            return self._alert_if(value > rule.threshold, connector_id, rule, value, "Connector queue backlog exceeds threshold.")
        if rule.rule_type == AlertRuleType.SYNC_DURATION_THRESHOLD:
            value = sync_state.duration_ms if sync_state else (metrics.average_duration_ms if metrics else 0)
            return self._alert_if(value > rule.threshold, connector_id, rule, value, "Connector sync duration exceeds threshold.")
        if rule.rule_type == AlertRuleType.HEALTH_SCORE_BELOW_THRESHOLD:
            score = self._health_score(health)
            return self._alert_if(score < rule.threshold, connector_id, rule, score, "Connector health score is below threshold.")
        if rule.rule_type == AlertRuleType.NO_SUCCESSFUL_SYNC_WITHIN_SLA:
            last_success = health.last_success_at if health else None
            if last_success is None:
                return self._alert(connector_id, rule, "never", "Connector has no successful sync recorded.")
            elapsed_minutes = (now - last_success).total_seconds() / 60
            return self._alert_if(elapsed_minutes > rule.threshold, connector_id, rule, round(elapsed_minutes, 2), "Connector has no successful sync within SLA.")
        return None

    def _health_score(self, health: ConnectorHealthStatus | None) -> float:
        if health is None:
            return 0.0
        base = 100.0
        if health.status.lower() not in {"healthy", "ok", "available"}:
            base -= 35
        base -= min(health.consecutive_failures * 10, 50)
        if health.latency_ms and health.latency_ms > int(timedelta(seconds=30).total_seconds() * 1000):
            base -= 10
        return max(base, 0.0)

    def _alert_if(
        self,
        condition: bool,
        connector_id: str,
        rule: ConnectorAlertRule,
        observed_value: float | str,
        message: str,
    ) -> ConnectorAlert | None:
        if not condition:
            return None
        return self._alert(connector_id, rule, observed_value, message)

    def _alert(
        self,
        connector_id: str,
        rule: ConnectorAlertRule,
        observed_value: float | str,
        message: str,
    ) -> ConnectorAlert:
        return ConnectorAlert(
            connector_id=connector_id,
            rule_id=rule.rule_id,
            rule_type=rule.rule_type,
            severity=rule.severity,
            message=message,
            observed_value=observed_value,
            threshold=rule.threshold,
            metadata=rule.metadata,
        )


alert_engine = ConnectorAlertEngine()
