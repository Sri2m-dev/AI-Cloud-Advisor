from __future__ import annotations

from typing import Any

import streamlit as st

from repositories.business_service_graph_repository import BusinessServiceGraphRepository
from repositories.technology_graph_repository import TechnologyGraphRepository
from services.ai_governance_service import AIGovernanceService


RELATIONSHIP_TYPES = {
    "USES",
    "DEPENDS_ON",
    "HOSTED_ON",
    "OWNED_BY",
    "SUPPORTED_BY",
    "FUNDED_BY",
    "HAS_COST",
    "HAS_RISK",
    "USES_AI",
    "USES_SAAS",
}


def _normalize(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _lower(value: Any) -> str:
    return _normalize(value).lower()


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _first_existing(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _dedupe(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen = set()
    deduped = []
    for row in rows:
        key = tuple(_lower(row.get(item)) for item in keys)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _node(name: str, node_type: str, **metadata: Any) -> dict[str, Any]:
    return {
        "id": f"{node_type.lower().replace(' ', '_')}:{name.lower().replace(' ', '_')}",
        "name": name,
        "type": node_type,
        "metadata": metadata,
    }


def _relationship(
    source: str,
    relationship_type: str,
    target: str,
    source_type: str,
    target_type: str,
    **metadata: Any,
) -> dict[str, Any]:
    return {
        "source": source,
        "source_name": source,
        "source_type": source_type,
        "relationship_type": relationship_type.upper(),
        "target": target,
        "target_name": target,
        "target_type": target_type,
        "metadata": metadata,
    }


class KnowledgeGraphRepository:
    @staticmethod
    def _technology_name(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "technology_name",
                "technology",
                "tool_name",
                "product",
                "vendor_name",
                "provider",
                "service_name",
                default="Unknown Technology",
            )
        )

    @staticmethod
    def _technology_type(row: dict[str, Any]) -> str:
        return _normalize(_first_existing(row, "technology_type", "type", "category", default="Technology"))

    @staticmethod
    def _technology_cost(row: dict[str, Any]) -> float:
        return _safe_float(
            _first_existing(
                row,
                "annual_cost",
                "annual_spend",
                "total_spend",
                "yearly_cost",
                "cost",
                "amount",
                default=0,
            )
        )

    @staticmethod
    def _service_name(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(row, "service_name", "business_service_name", "name", "service", default="Unknown Service")
        )

    @staticmethod
    def _application_name(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(row, "application_name", "application", "app_name", "name", default="Unknown Application")
        )

    @staticmethod
    def _seed_relationships() -> list[dict[str, Any]]:
        return [
            _relationship("Revenue Services", "USES", "Order Processing", "Business Domain", "Business Service"),
            _relationship("Order Processing", "USES", "Checkout", "Business Service", "Application"),
            _relationship("Checkout", "DEPENDS_ON", "AWS", "Application", "Technology", cost_domain="Cloud", cost=0),
            _relationship("Checkout", "DEPENDS_ON", "GitHub", "Application", "Technology", cost_domain="SaaS", cost=6500),
            _relationship("Checkout", "DEPENDS_ON", "Datadog", "Application", "Technology", cost_domain="License", cost=8000),
            _relationship("Checkout", "DEPENDS_ON", "Managed Services", "Application", "Technology", cost_domain="MSP", cost=6000),
            _relationship("Checkout", "USES_AI", "ChatGPT Enterprise", "Application", "Technology", cost_domain="AI", cost=12000),
            _relationship("Checkout", "USES_AI", "GitHub Copilot", "Application", "Technology", cost_domain="AI", cost=9000),
            _relationship("GitHub", "OWNED_BY", "Engineering", "Technology", "Owner"),
            _relationship("AWS", "OWNED_BY", "CloudOps", "Technology", "Owner"),
            _relationship("ChatGPT Enterprise", "OWNED_BY", "Engineering", "Technology", "Owner"),
            _relationship("GitHub Copilot", "OWNED_BY", "Engineering", "Technology", "Owner"),
            _relationship("Datadog", "OWNED_BY", "CloudOps", "Technology", "Owner"),
            _relationship("Managed Services", "SUPPORTED_BY", "Minfy", "Technology", "Vendor"),
            _relationship("GitHub", "HAS_COST", "18000", "Technology", "Cost", cost=18000, cost_domain="SaaS"),
            _relationship("ChatGPT Enterprise", "HAS_COST", "12000", "Technology", "Cost", cost=12000, cost_domain="AI"),
            _relationship("GitHub Copilot", "HAS_COST", "9000", "Technology", "Cost", cost=9000, cost_domain="AI"),
            _relationship("AWS", "HAS_RISK", "Critical", "Technology", "Risk", risk="Critical"),
            _relationship("GitHub", "HAS_RISK", "Medium", "Technology", "Risk", risk="Medium"),
            _relationship("ChatGPT Enterprise", "HAS_RISK", "Low", "Technology", "Risk", risk="Low"),
        ]

    @staticmethod
    def _live_relationships() -> list[dict[str, Any]]:
        rows = []
        for row in TechnologyGraphRepository.get_technology_relationships():
            source = _normalize(_first_existing(row, "source_name", "source", "from_name"))
            target = _normalize(_first_existing(row, "target_name", "target", "to_name"))
            if not source or not target:
                continue
            rows.append(
                _relationship(
                    source,
                    _normalize(_first_existing(row, "relationship_type", "relationship", "type", default="DEPENDS_ON")),
                    target,
                    _normalize(_first_existing(row, "source_type", "from_type", default="Technology")),
                    _normalize(_first_existing(row, "target_type", "to_type", default="Technology")),
                )
            )

        for row in BusinessServiceGraphRepository.get_business_service_relationships():
            source = _normalize(
                _first_existing(row, "source_name", "source", "parent_name", "from_name", "business_service_name")
            )
            target = _normalize(
                _first_existing(row, "target_name", "target", "child_name", "to_name", "application_name")
            )
            if not source or not target:
                continue
            rows.append(
                _relationship(
                    source,
                    _normalize(_first_existing(row, "relationship_type", "relationship", "type", default="USES")),
                    target,
                    _normalize(_first_existing(row, "source_type", "from_type", default="Business Service")),
                    _normalize(_first_existing(row, "target_type", "to_type", default="Application")),
                )
            )

        return rows

    @staticmethod
    @st.cache_data(ttl=300)
    def get_all_relationships() -> list[dict[str, Any]]:
        relationships = KnowledgeGraphRepository._seed_relationships() + KnowledgeGraphRepository._live_relationships()
        return _dedupe(relationships, ("source_name", "relationship_type", "target_name", "source_type", "target_type"))

    @staticmethod
    @st.cache_data(ttl=300)
    def get_all_nodes() -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []

        for row in BusinessServiceGraphRepository.get_business_services():
            name = KnowledgeGraphRepository._service_name(row)
            nodes.append(_node(name, "Business Service", owner=_first_existing(row, "owner", "service_owner")))

        for row in BusinessServiceGraphRepository.get_application_registry():
            name = KnowledgeGraphRepository._application_name(row)
            nodes.append(_node(name, "Application", owner=_first_existing(row, "owner", "application_owner")))

        for row in BusinessServiceGraphRepository.get_technology_inventory():
            name = KnowledgeGraphRepository._technology_name(row)
            nodes.append(
                _node(
                    name,
                    "Technology",
                    technology_type=KnowledgeGraphRepository._technology_type(row),
                    vendor=_first_existing(row, "vendor_name", "vendor", "provider", default="Unknown"),
                    cost=KnowledgeGraphRepository._technology_cost(row),
                    owner=_first_existing(row, "owner_department", "owner", "business_owner", default="Unassigned"),
                )
            )

        for row in AIGovernanceService.get_ai_tools():
            name = KnowledgeGraphRepository._technology_name(row)
            if name.lower() in {"copilot", "microsoft copilot", "copilot enterprise"}:
                name = "GitHub Copilot"
            nodes.append(
                _node(
                    name,
                    "Technology",
                    technology_type="AI",
                    vendor=_first_existing(row, "vendor_name", "vendor", default="Unknown"),
                    cost=KnowledgeGraphRepository._technology_cost(row),
                    owner=_first_existing(row, "owner_department", "owner", default="Unassigned"),
                )
            )

        for relationship in KnowledgeGraphRepository.get_all_relationships():
            nodes.append(_node(relationship["source_name"], relationship["source_type"]))
            nodes.append(_node(relationship["target_name"], relationship["target_type"]))

        return _dedupe(nodes, ("name", "type"))

    @staticmethod
    def get_service_graph() -> dict[str, list[dict[str, Any]]]:
        relationships = [
            row
            for row in KnowledgeGraphRepository.get_all_relationships()
            if row["source_type"] in {"Business Domain", "Business Service"}
            or row["target_type"] in {"Business Domain", "Business Service"}
        ]
        return {"nodes": KnowledgeGraphRepository.get_all_nodes(), "relationships": relationships}

    @staticmethod
    def get_application_graph() -> dict[str, list[dict[str, Any]]]:
        relationships = [
            row
            for row in KnowledgeGraphRepository.get_all_relationships()
            if row["source_type"] == "Application" or row["target_type"] == "Application"
        ]
        return {"nodes": KnowledgeGraphRepository.get_all_nodes(), "relationships": relationships}

    @staticmethod
    def get_technology_graph() -> dict[str, list[dict[str, Any]]]:
        relationships = [
            row
            for row in KnowledgeGraphRepository.get_all_relationships()
            if row["source_type"] == "Technology" or row["target_type"] == "Technology"
        ]
        return {"nodes": KnowledgeGraphRepository.get_all_nodes(), "relationships": relationships}

    @staticmethod
    def get_cost_graph() -> dict[str, list[dict[str, Any]]]:
        relationships = [
            row
            for row in KnowledgeGraphRepository.get_all_relationships()
            if row["relationship_type"] == "HAS_COST" or row["target_type"] == "Cost"
        ]
        return {"nodes": KnowledgeGraphRepository.get_all_nodes(), "relationships": relationships}
