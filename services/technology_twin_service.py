from __future__ import annotations

from uuid import UUID

from core.digital_twin.technology import (
    CostCalculator,
    CostSignal,
    HealthCalculator,
    HealthSignal,
    HealthSignalType,
    InfrastructureLayer,
    InfrastructureResource,
    OperationalCalculator,
    OperationalSignal,
    RiskCalculator,
    RiskSignal,
    TechnologyTwin,
)
from core.digital_twin.technology.technology_twin import TECHNOLOGY_ENTITY_TYPES
from core.entities.entity import EnterpriseEntity, EntityRelationship
from repositories.entity_repository import EntityRepository
from repositories.technology_twin_repository import TechnologyTwinRepository


class TechnologyTwinService:
    def __init__(
        self,
        entity_repository: EntityRepository | None = None,
        twin_repository: TechnologyTwinRepository | None = None,
    ):
        self.entity_repository = entity_repository or EntityRepository()
        self.twin_repository = twin_repository or TechnologyTwinRepository()
        self.health_calculator = HealthCalculator()
        self.cost_calculator = CostCalculator()
        self.risk_calculator = RiskCalculator()
        self.operational_calculator = OperationalCalculator()

    def build_technology_twin(self, organization_id: UUID | str, persist: bool = True) -> TechnologyTwin:
        resolved_id = UUID(str(organization_id))
        entities = [
            entity
            for entity in self.entity_repository.get_entities()
            if entity.organization_id == resolved_id
        ]
        relationships = [
            relationship
            for relationship in self.entity_repository.get_relationships()
            if self._relationship_belongs_to_org(relationship, entities)
        ]
        twin = TechnologyTwin.build(resolved_id, entities, relationships)
        return self.twin_repository.save(twin) if persist else twin

    def refresh_technology_twin(self, organization_id: UUID | str) -> TechnologyTwin:
        return self.build_technology_twin(organization_id, persist=True)

    def get_latest_technology_twin(self, organization_id: UUID | str) -> TechnologyTwin | None:
        return self.twin_repository.latest_for_organization(organization_id)

    def technology_context(self, organization_id: UUID | str, technology_id: UUID | str) -> dict:
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        return twin.technology_context(technology_id)

    def technology_portfolio(self, organization_id: UUID | str) -> list[dict]:
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        return [
            {
                "technology_id": str(node.technology_id),
                "name": node.name,
                "technology_type": node.technology_type,
                "vendor": node.vendor,
                "cloud_provider": node.cloud_provider,
                "environment": node.environment,
                "region": node.region,
                "status": node.status,
                "health": node.state.health_score if node.state else 100.0,
                "risk": node.risk,
                "monthly_cost": node.monthly_cost,
                "applications": len(node.application_ids),
                "business_services": len(node.business_service_ids),
            }
            for node in sorted(twin.nodes.values(), key=lambda item: (item.technology_type, item.name.lower()))
        ]

    def graph(self, organization_id: UUID | str) -> dict:
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        return twin.graph()

    def attach_infrastructure_resource(
        self,
        organization_id: UUID | str,
        technology_id: UUID | str,
        resource: InfrastructureResource,
        relationship_type: str = "RUNS_ON",
    ) -> TechnologyTwin:
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        node = twin.nodes.get(UUID(str(technology_id)))
        if not node:
            raise KeyError(f"Technology twin node not found: {technology_id}")
        node.attach_infrastructure_resource(resource, relationship_type=relationship_type)
        twin.refresh()
        return self.twin_repository.save(twin)

    def get_infrastructure_layer(
        self,
        organization_id: UUID | str,
        technology_id: UUID | str,
    ) -> InfrastructureLayer:
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        node = twin.nodes.get(UUID(str(technology_id)))
        if not node:
            raise KeyError(f"Technology twin node not found: {technology_id}")
        if node.infrastructure_layer is None:
            node.infrastructure_layer = InfrastructureLayer(node.technology_id)
        return node.infrastructure_layer

    def map_resource_to_technology(
        self,
        organization_id: UUID | str,
        technology_id: UUID | str,
        resource_entity_id: UUID | str,
        relationship_type: str = "RUNS_ON",
    ) -> TechnologyTwin:
        entity = self.entity_repository.get_entity(resource_entity_id)
        if not entity:
            raise KeyError(f"Infrastructure resource entity not found: {resource_entity_id}")
        return self.attach_infrastructure_resource(
            organization_id,
            technology_id,
            InfrastructureResource.from_entity(entity),
            relationship_type=relationship_type,
        )

    def calculate_infrastructure_health(self, organization_id: UUID | str, technology_id: UUID | str) -> float:
        layer = self.get_infrastructure_layer(organization_id, technology_id)
        layer.refresh()
        return layer.health_score

    def calculate_infrastructure_cost(self, organization_id: UUID | str, technology_id: UUID | str) -> float:
        layer = self.get_infrastructure_layer(organization_id, technology_id)
        layer.refresh()
        return layer.cost

    def record_health_signal(
        self,
        organization_id: UUID | str,
        technology_id: UUID | str,
        signal_type: str,
        value: float,
        weight: float | None = None,
        source_system: str = "manual",
        confidence_score: float = 1.0,
        metadata: dict | None = None,
    ) -> HealthSignal:
        signal = HealthSignal.create(
            technology_id,
            signal_type,
            value,
            weight=self.health_calculator.policy.weight_for(signal_type) if weight is None else weight,
            source_system=source_system,
            confidence_score=confidence_score,
            metadata=metadata,
        )
        self.twin_repository.save_health_signal(signal)
        self.calculate_technology_health(organization_id, technology_id)
        return signal

    def calculate_technology_health(self, organization_id: UUID | str, technology_id: UUID | str) -> dict:
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        node = twin.nodes.get(UUID(str(technology_id)))
        if not node:
            raise KeyError(f"Technology twin node not found: {technology_id}")
        signals = self.twin_repository.list_health_signals(technology_id)
        result = self.health_calculator.apply_to_node(node, signals)
        twin.refresh()
        self.twin_repository.save(twin)
        return result.to_dict()

    def calculate_layer_health(self, organization_id: UUID | str, technology_id: UUID | str) -> float:
        layer = self.get_infrastructure_layer(organization_id, technology_id)
        return self.health_calculator.calculate_layer_health(layer)

    def get_health_breakdown(self, organization_id: UUID | str, technology_id: UUID | str) -> dict:
        return self.calculate_technology_health(organization_id, technology_id)

    def get_degraded_technologies(self, organization_id: UUID | str, threshold: float = 70.0) -> list[dict]:
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        degraded = []
        for node in twin.nodes.values():
            breakdown = self.calculate_technology_health(organization_id, node.technology_id)
            if breakdown["health_score"] < threshold:
                degraded.append(
                    {
                        "technology_id": str(node.technology_id),
                        "name": node.name,
                        "status": breakdown["status"],
                        "health": breakdown["health_score"],
                        "issues": breakdown["issues"],
                    }
                )
        return degraded

    def record_cost_signal(
        self,
        organization_id: UUID | str,
        technology_id: UUID | str,
        provider: str,
        service: str,
        amount: float,
        signal_type: str = "Cloud Spend",
        account: str = "",
        cost_center: str = "",
        business_unit: str = "",
        application: str = "",
        environment: str = "",
        usage: float = 0.0,
        trend: float = 0.0,
        confidence_score: float = 1.0,
        metadata: dict | None = None,
    ) -> CostSignal:
        signal = CostSignal.create(
            technology_id,
            provider=provider,
            service=service,
            amount=amount,
            signal_type=signal_type,
            account=account,
            cost_center=cost_center,
            business_unit=business_unit,
            application=application,
            environment=environment,
            usage=usage,
            trend=trend,
            confidence_score=confidence_score,
            metadata=metadata,
        )
        self.twin_repository.save_cost_signal(signal)
        self.get_cost_breakdown(organization_id, technology_id)
        return signal

    def calculate_current_cost(self, organization_id: UUID | str, technology_id: UUID | str) -> float:
        return self.get_cost_breakdown(organization_id, technology_id)["current_cost"]

    def calculate_monthly_cost(self, organization_id: UUID | str, technology_id: UUID | str) -> float:
        return self.get_cost_breakdown(organization_id, technology_id)["monthly_cost"]

    def calculate_forecast(self, organization_id: UUID | str, technology_id: UUID | str) -> float:
        return self.get_cost_breakdown(organization_id, technology_id)["forecast"]

    def calculate_budget_variance(self, organization_id: UUID | str, technology_id: UUID | str) -> dict:
        breakdown = self.get_cost_breakdown(organization_id, technology_id)
        return {
            "budget": breakdown["budget"],
            "budget_variance": breakdown["budget_variance"],
            "budget_variance_percent": breakdown["budget_variance_percent"],
            "cost_health": breakdown["cost_health"],
        }

    def calculate_roi(self, organization_id: UUID | str, technology_id: UUID | str) -> float:
        return self.get_cost_breakdown(organization_id, technology_id)["roi"]

    def calculate_optimization(self, organization_id: UUID | str, technology_id: UUID | str) -> dict:
        breakdown = self.get_cost_breakdown(organization_id, technology_id)
        return {
            "optimization_opportunity": breakdown["optimization_opportunity"],
            "potential_savings": breakdown["potential_savings"],
        }

    def get_cost_breakdown(self, organization_id: UUID | str, technology_id: UUID | str) -> dict:
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        node = twin.nodes.get(UUID(str(technology_id)))
        if not node:
            raise KeyError(f"Technology twin node not found: {technology_id}")
        signals = self.twin_repository.list_cost_signals(technology_id)
        result = self.cost_calculator.apply_to_node(node, signals)
        twin.refresh()
        self.twin_repository.save(twin)
        return result.to_dict()

    def record_risk_signal(
        self,
        organization_id: UUID | str,
        technology_id: UUID | str,
        risk_type: str,
        severity: str,
        probability: float,
        impact: float,
        source_system: str = "manual",
        affected_entity: str = "",
        mitigation: str = "",
        owner: str = "",
        status: str = "Open",
        confidence_score: float = 1.0,
        metadata: dict | None = None,
    ) -> RiskSignal:
        signal = RiskSignal.create(
            technology_id,
            risk_type=risk_type,
            severity=severity,
            probability=probability,
            impact=impact,
            source_system=source_system,
            affected_entity=affected_entity,
            mitigation=mitigation,
            owner=owner,
            status=status,
            confidence_score=confidence_score,
            metadata=metadata,
        )
        self.twin_repository.save_risk_signal(signal)
        self.get_risk_breakdown(organization_id, technology_id)
        return signal

    def calculate_risk_score(self, organization_id: UUID | str, technology_id: UUID | str) -> float:
        return self.get_risk_breakdown(organization_id, technology_id)["risk_score"]

    def calculate_risk_posture(self, organization_id: UUID | str, technology_id: UUID | str) -> str:
        return self.get_risk_breakdown(organization_id, technology_id)["risk_posture"]

    def get_risk_breakdown(self, organization_id: UUID | str, technology_id: UUID | str) -> dict:
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        node = twin.nodes.get(UUID(str(technology_id)))
        if not node:
            raise KeyError(f"Technology twin node not found: {technology_id}")
        signals = self.twin_repository.list_risk_signals(technology_id)
        result = self.risk_calculator.apply_to_node(node, signals)
        twin.refresh()
        self.twin_repository.save(twin)
        return result.to_dict()

    def get_critical_risks(self, organization_id: UUID | str, technology_id: UUID | str | None = None) -> list[dict]:
        if technology_id is not None:
            return self.get_risk_breakdown(organization_id, technology_id)["critical_risks"]
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        critical = []
        for node in twin.nodes.values():
            critical.extend(self.get_risk_breakdown(organization_id, node.technology_id)["critical_risks"])
        return critical

    def get_risk_mitigations(self, organization_id: UUID | str, technology_id: UUID | str | None = None) -> list[dict]:
        if technology_id is not None:
            return self.get_risk_breakdown(organization_id, technology_id)["mitigations"]
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        mitigations = []
        for node in twin.nodes.values():
            mitigations.extend(self.get_risk_breakdown(organization_id, node.technology_id)["mitigations"])
        return mitigations

    def record_operational_signal(
        self,
        organization_id: UUID | str,
        technology_id: UUID | str,
        signal_type: str,
        source_system: str,
        severity: str = "Info",
        status: str = "Open",
        event_time: str | None = None,
        duration: float = 0.0,
        affected_component: str = "",
        owner: str = "",
        confidence_score: float = 1.0,
        metadata: dict | None = None,
    ) -> OperationalSignal:
        signal = OperationalSignal.create(
            technology_id,
            signal_type=signal_type,
            source_system=source_system,
            severity=severity,
            status=status,
            event_time=event_time,
            duration=duration,
            affected_component=affected_component,
            owner=owner,
            confidence_score=confidence_score,
            metadata=metadata,
        )
        self.twin_repository.save_operational_signal(signal)
        self.get_operational_summary(organization_id, technology_id)
        return signal

    def calculate_operational_health(self, organization_id: UUID | str, technology_id: UUID | str) -> float:
        return self.get_operational_summary(organization_id, technology_id)["operational_health"]

    def get_active_incidents(self, organization_id: UUID | str, technology_id: UUID | str | None = None) -> list[dict]:
        if technology_id is not None:
            return self.get_operational_summary(organization_id, technology_id)["active_incidents"]
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        incidents = []
        for node in twin.nodes.values():
            incidents.extend(self.get_operational_summary(organization_id, node.technology_id)["active_incidents"])
        return incidents

    def get_active_alerts(self, organization_id: UUID | str, technology_id: UUID | str | None = None) -> list[dict]:
        if technology_id is not None:
            return self.get_operational_summary(organization_id, technology_id)["active_alerts"]
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        alerts = []
        for node in twin.nodes.values():
            alerts.extend(self.get_operational_summary(organization_id, node.technology_id)["active_alerts"])
        return alerts

    def get_recent_changes(self, organization_id: UUID | str, technology_id: UUID | str | None = None) -> list[dict]:
        if technology_id is not None:
            return self.get_operational_summary(organization_id, technology_id)["open_changes"]
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        changes = []
        for node in twin.nodes.values():
            changes.extend(self.get_operational_summary(organization_id, node.technology_id)["open_changes"])
        return changes

    def get_deployment_history(self, organization_id: UUID | str, technology_id: UUID | str | None = None) -> list[dict]:
        if technology_id is not None:
            return self.get_operational_summary(organization_id, technology_id)["recent_deployments"]
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        deployments = []
        for node in twin.nodes.values():
            deployments.extend(self.get_operational_summary(organization_id, node.technology_id)["recent_deployments"])
        return deployments

    def get_operational_summary(self, organization_id: UUID | str, technology_id: UUID | str) -> dict:
        twin = self.get_latest_technology_twin(organization_id) or self.build_technology_twin(organization_id)
        node = twin.nodes.get(UUID(str(technology_id)))
        if not node:
            raise KeyError(f"Technology twin node not found: {technology_id}")
        signals = self.twin_repository.list_operational_signals(technology_id)
        result = self.operational_calculator.apply_to_node(node, signals)
        twin.refresh()
        self.twin_repository.save(twin)
        return result.to_dict()

    def _relationship_belongs_to_org(
        self,
        relationship: EntityRelationship,
        entities: list[EnterpriseEntity],
    ) -> bool:
        entity_ids = {entity.id for entity in entities}
        return relationship.source_entity_id in entity_ids or relationship.target_entity_id in entity_ids

    def technology_entities(self, organization_id: UUID | str) -> list[EnterpriseEntity]:
        resolved_id = UUID(str(organization_id))
        return [
            entity
            for entity in self.entity_repository.get_entities()
            if entity.organization_id == resolved_id and entity.entity_type in TECHNOLOGY_ENTITY_TYPES
        ]
