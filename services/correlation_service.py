from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import UUID

from core.correlation.correlation_context import CorrelationContext
from core.correlation.correlation_event import (
    CorrelationEvent,
    CorrelationEventType,
    CorrelationSeverity,
)
from core.correlation.correlation_result import CorrelationResult
from core.correlation.correlation_rule import CorrelationPatternType
from core.entities.entity import EnterpriseEntity
from repositories.correlation_repository import CorrelationRepository
from repositories.entity_repository import EntityRepository


class CorrelationService:
    def __init__(
        self,
        correlation_repository: CorrelationRepository | None = None,
        entity_repository: EntityRepository | None = None,
    ):
        self.correlation_repository = correlation_repository or CorrelationRepository()
        self.entity_repository = entity_repository or EntityRepository()

    def register_event(
        self,
        event_type: str,
        title: str,
        source_system: str,
        organization_id: UUID | str,
        description: str = "",
        occurred_at: str | datetime | None = None,
        severity: str = CorrelationSeverity.MEDIUM.value,
        entity_ids: list[UUID | str] | None = None,
        external_id: str = "",
        confidence_score: float = 100.0,
        metadata: dict | None = None,
    ) -> CorrelationEvent:
        self._validate_event_type(event_type)
        event = CorrelationEvent(
            event_type=event_type,
            title=title.strip(),
            source_system=source_system.strip(),
            organization_id=UUID(str(organization_id)),
            description=description.strip(),
            occurred_at=self._normalize_timestamp(occurred_at) if occurred_at else self._now(),
            severity=severity,
            entity_ids=[UUID(str(entity_id)) for entity_id in entity_ids or []],
            external_id=external_id,
            confidence_score=self._bounded(confidence_score),
            metadata=metadata or {},
        )
        return self.correlation_repository.save_event(event)

    def link_event_to_entity(self, event_id: UUID | str, entity_id: UUID | str) -> CorrelationEvent:
        if not self.entity_repository.get_entity(entity_id):
            raise KeyError(f"Entity not found: {entity_id}")
        return self.correlation_repository.link_event_to_entity(event_id, entity_id)

    def find_related_events(self, event_id: UUID | str) -> list[CorrelationEvent]:
        return self.correlation_repository.find_related_events(event_id)

    def correlate_entity_context(self, entity_id: UUID | str) -> CorrelationContext:
        entity = self._get_entity(entity_id)
        relationships = self.entity_repository.get_relationships(entity.id)
        related_entities = self._related_entities(entity, relationships)
        related_ids = {entity.id, *(related_entity.id for related_entity in related_entities)}
        events = []
        for related_id in related_ids:
            events.extend(self.correlation_repository.find_events_for_entity(related_id))
        events = self._unique_events(events)
        results = self.detect_correlation_patterns(entity.id, events)
        return CorrelationContext(
            entity=entity,
            events=events,
            relationships=relationships,
            related_entities=related_entities,
            results=results,
            metadata={
                "event_type_counts": dict(Counter(event.event_type for event in events)),
                "related_entity_count": len(related_entities),
            },
        )

    def detect_correlation_patterns(
        self,
        entity_id: UUID | str,
        events: list[CorrelationEvent] | None = None,
    ) -> list[CorrelationResult]:
        entity = self._get_entity(entity_id)
        scoped_events = events or self.correlation_repository.find_events_for_entity(entity.id)
        results = []
        for detector in (
            self._detect_deployment_driven_cost_increase,
            self._detect_saas_optimization_opportunity,
            self._detect_business_impact_risk,
        ):
            result = detector(entity, scoped_events)
            if result:
                results.append(self.correlation_repository.save_result(result))
        return results

    def generate_correlation_summary(self, entity_id: UUID | str) -> str:
        context = self.correlate_entity_context(entity_id)
        if not context.results:
            return f"No high-confidence correlation pattern detected for {context.entity.display_name}."
        summaries = [result.summary for result in context.results]
        return " ".join(summaries)

    def _detect_deployment_driven_cost_increase(
        self,
        entity: EnterpriseEntity,
        events: list[CorrelationEvent],
    ) -> CorrelationResult | None:
        cost_events = self._events_of_type(events, CorrelationEventType.COST_SPIKE.value)
        alert_events = self._events_of_type(events, CorrelationEventType.ALERT.value)
        deployment_events = self._events_of_type(events, CorrelationEventType.DEPLOYMENT.value)
        if not (cost_events and alert_events and deployment_events):
            return None

        matched_events = self._events_within_window(
            [cost_events[0], alert_events[0], deployment_events[0]],
            hours=72,
        )
        if len(matched_events) < 3:
            return None

        confidence = self._average([event.confidence_score for event in matched_events], default=85.0)
        return CorrelationResult(
            pattern_type=CorrelationPatternType.DEPLOYMENT_DRIVEN_COST_INCREASE.value,
            summary=(
                f"{entity.display_name} shows a possible deployment-driven cost increase: "
                f"cost spike, alert, and deployment events occurred within the same correlation window."
            ),
            organization_id=entity.organization_id,
            entity_ids=[entity.id],
            event_ids=[event.id for event in matched_events],
            confidence_score=round(min(100.0, confidence + 5), 2),
            severity=self._max_severity(matched_events),
            evidence=[
                "Cost spike detected",
                "Operational alert detected",
                "Deployment detected in the same entity context",
            ],
            recommended_actions=[
                "Review deployment changes for resource or traffic changes",
                "Compare post-deployment unit cost and utilization",
                "Validate alert telemetry before rollback or optimization action",
            ],
            metadata={"window_hours": 72},
        )

    def _detect_saas_optimization_opportunity(
        self,
        entity: EnterpriseEntity,
        events: list[CorrelationEvent],
    ) -> CorrelationResult | None:
        renewal_events = self._events_of_type(events, CorrelationEventType.RENEWAL_RISK.value)
        license_events = self._events_of_type(events, CorrelationEventType.LICENSE_WASTE.value)
        cost_events = [
            event
            for event in events
            if event.event_type == CorrelationEventType.COST_SPIKE.value
            or "vendor_spend" in event.metadata
            or "duplicate_tool" in event.metadata
        ]
        if not (renewal_events and license_events and cost_events):
            return None
        matched_events = self._events_within_window(
            [renewal_events[0], license_events[0], cost_events[0]],
            hours=24 * 30,
        )
        return CorrelationResult(
            pattern_type=CorrelationPatternType.SAAS_OPTIMIZATION_OPPORTUNITY.value,
            summary=f"{entity.display_name} has a SaaS optimization opportunity tied to renewal risk, inactive usage, and spend signals.",
            organization_id=entity.organization_id,
            entity_ids=[entity.id],
            event_ids=[event.id for event in matched_events],
            confidence_score=self._average([event.confidence_score for event in matched_events], default=80.0),
            severity=self._max_severity(matched_events),
            evidence=["Renewal risk detected", "License waste detected", "Vendor spend or duplicate-tool signal detected"],
            recommended_actions=["Review renewal terms", "Reclaim inactive licenses", "Consolidate duplicate SaaS capabilities"],
            metadata={"window_hours": 24 * 30},
        )

    def _detect_business_impact_risk(
        self,
        entity: EnterpriseEntity,
        events: list[CorrelationEvent],
    ) -> CorrelationResult | None:
        incident_events = self._events_of_type(events, CorrelationEventType.INCIDENT.value)
        risk_events = self._events_of_type(events, CorrelationEventType.RISK.value)
        compliance_events = self._events_of_type(events, CorrelationEventType.COMPLIANCE_FINDING.value)
        if not incident_events or not (risk_events or compliance_events):
            return None
        matched_events = self._events_within_window(
            [incident_events[0], *((risk_events or compliance_events)[:1])],
            hours=24 * 14,
        )
        return CorrelationResult(
            pattern_type=CorrelationPatternType.BUSINESS_IMPACT_RISK.value,
            summary=f"{entity.display_name} has an incident correlated with risk or compliance signals, indicating potential business impact.",
            organization_id=entity.organization_id,
            entity_ids=[entity.id],
            event_ids=[event.id for event in matched_events],
            confidence_score=self._average([event.confidence_score for event in matched_events], default=80.0),
            severity=self._max_severity(matched_events),
            evidence=["Incident detected", "Risk or compliance finding detected"],
            recommended_actions=["Map affected business services", "Confirm technology dependencies", "Prepare executive impact summary"],
            metadata={"window_hours": 24 * 14},
        )

    def _related_entities(self, entity: EnterpriseEntity, relationships) -> list[EnterpriseEntity]:
        related = []
        for relationship in relationships:
            related_id = (
                relationship.target_entity_id
                if relationship.source_entity_id == entity.id
                else relationship.source_entity_id
            )
            candidate = self.entity_repository.get_entity(related_id)
            if candidate and candidate.id != entity.id:
                related.append(candidate)
        return sorted({candidate.id: candidate for candidate in related}.values(), key=lambda item: item.display_name.lower())

    def _get_entity(self, entity_id: UUID | str) -> EnterpriseEntity:
        entity = self.entity_repository.get_entity(entity_id)
        if not entity:
            raise KeyError(f"Entity not found: {entity_id}")
        return entity

    @staticmethod
    def _validate_event_type(event_type: str) -> None:
        if event_type not in {item.value for item in CorrelationEventType}:
            raise ValueError(f"Unsupported correlation event type: {event_type}")

    @staticmethod
    def _events_of_type(events: list[CorrelationEvent], event_type: str) -> list[CorrelationEvent]:
        return sorted(
            [event for event in events if event.event_type == event_type],
            key=lambda event: event.occurred_at,
            reverse=True,
        )

    @staticmethod
    def _events_within_window(events: list[CorrelationEvent], hours: int) -> list[CorrelationEvent]:
        parsed_events = []
        for event in events:
            parsed_events.append((event, CorrelationService._parse_timestamp(event.occurred_at)))
        timestamps = [timestamp for _, timestamp in parsed_events]
        if max(timestamps) - min(timestamps) <= timedelta(hours=hours):
            return [event for event, _ in parsed_events]
        return []

    @staticmethod
    def _unique_events(events: list[CorrelationEvent]) -> list[CorrelationEvent]:
        return sorted({event.id: event for event in events}.values(), key=lambda item: item.occurred_at, reverse=True)

    @staticmethod
    def _max_severity(events: list[CorrelationEvent]) -> str:
        rank = {
            CorrelationSeverity.INFO.value: 0,
            CorrelationSeverity.LOW.value: 1,
            CorrelationSeverity.MEDIUM.value: 2,
            CorrelationSeverity.HIGH.value: 3,
            CorrelationSeverity.CRITICAL.value: 4,
        }
        return max((event.severity for event in events), key=lambda severity: rank.get(severity, 0), default=CorrelationSeverity.MEDIUM.value)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _normalize_timestamp(value: str | datetime) -> str:
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _average(values: list[float], default: float) -> float:
        return round(sum(values) / len(values), 2) if values else default

    @staticmethod
    def _bounded(value: float) -> float:
        return round(max(0.0, min(100.0, float(value))), 2)
