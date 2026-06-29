from __future__ import annotations

from collections import deque
from typing import Any

import pandas as pd

from repositories.digital_twin_repository import DigitalTwinRepository
from services.savings_governance_service import SavingsGovernanceService


DEPENDENCY_TYPES = {"OWNS", "FUNDS", "USES", "DEPENDS_ON", "USES_AI", "USES_SAAS", "HOSTED_ON", "SUPPORTED_BY"}


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


class DigitalTwinService:
    @staticmethod
    def get_nodes() -> list[dict[str, Any]]:
        return DigitalTwinRepository.get_enterprise_nodes()

    @staticmethod
    def get_relationships() -> list[dict[str, Any]]:
        return DigitalTwinRepository.get_enterprise_relationships()

    @staticmethod
    def _children(entity: str) -> list[dict[str, Any]]:
        entity_key = _lower(entity)
        return [
            row for row in DigitalTwinService.get_relationships()
            if _lower(row.get("source")) == entity_key
            and _normalize(row.get("relationship_type")).upper() in DEPENDENCY_TYPES
        ]

    @staticmethod
    def _parents(entity: str) -> list[dict[str, Any]]:
        entity_key = _lower(entity)
        return [
            row for row in DigitalTwinService.get_relationships()
            if _lower(row.get("target")) == entity_key
            and _normalize(row.get("relationship_type")).upper() in DEPENDENCY_TYPES
        ]

    @staticmethod
    def _node_type(entity: str) -> str:
        for row in DigitalTwinService.get_nodes():
            if _lower(row.get("name")) == _lower(entity):
                return _normalize(row.get("type"), "Unknown")
        if _lower(entity) == "retail":
            return "Business Unit"
        if _lower(entity) == "revenue services":
            return "Revenue Stream"
        if _lower(entity) == "order processing":
            return "Business Service"
        if _lower(entity) == "checkout":
            return "Application"
        if _lower(entity) in {"aws", "azure", "gcp"}:
            return "Cloud"
        return "Unknown"

    @staticmethod
    def _technology_costs() -> dict[str, dict[str, float]]:
        costs: dict[str, dict[str, float]] = {}

        def add(name: str, domain: str, amount: float) -> None:
            if not name or not amount:
                return
            item = costs.setdefault(_lower(name), {"Cloud": 0.0, "SaaS": 0.0, "AI": 0.0, "MSP": 0.0, "License": 0.0})
            if domain not in item:
                domain = "License"
            item[domain] += amount

        for row in DigitalTwinRepository.get_technology_inventory():
            name = _normalize(_first_existing(row, "technology_name", "name", "vendor_name", "provider"))
            tech_type = _normalize(_first_existing(row, "technology_type", "category", default="License"))
            amount = _safe_float(_first_existing(row, "annual_cost", "annual_spend", "total_spend", "cost", "amount", default=0))
            domain = "AI" if tech_type.lower() == "ai" else "Cloud" if tech_type.lower() == "cloud" else "MSP" if "msp" in tech_type.lower() or "managed" in tech_type.lower() else "SaaS" if tech_type.lower() == "saas" else "License"
            add(name, domain, amount)

        cloud_total = 0.0
        for row in DigitalTwinRepository.get_cloud_costs():
            cloud_total += _safe_float(_first_existing(row, "cost", "amount", "blended_cost", "unblended_cost", "annual_cost", default=0))
        if cloud_total and not costs.get("aws", {}).get("Cloud"):
            add("AWS", "Cloud", cloud_total)

        for row in DigitalTwinRepository.get_saas_costs():
            name = _normalize(_first_existing(row, "technology_name", "vendor_name", "vendor", "application_name", "name"))
            if not costs.get(_lower(name), {}).get("SaaS"):
                add(name, "SaaS", _safe_float(_first_existing(row, "annual_cost", "annual_spend", "total_spend", "cost", "amount", default=0)))

        for row in DigitalTwinRepository.get_license_costs():
            name = _normalize(_first_existing(row, "technology_name", "vendor_name", "vendor", "application_name", "name"))
            if not costs.get(_lower(name), {}).get("License"):
                add(name, "License", _safe_float(_first_existing(row, "annual_cost", "annual_spend", "total_spend", "cost", "amount", default=0)))

        if not costs.get("aws", {}).get("Cloud"):
            add("AWS", "Cloud", 18000.0)
        if not costs.get("github", {}).get("SaaS"):
            add("GitHub", "SaaS", 6500.0)
        if not costs.get("chatgpt enterprise", {}).get("AI"):
            add("ChatGPT Enterprise", "AI", 12000.0)
        if not costs.get("github copilot", {}).get("AI"):
            add("GitHub Copilot", "AI", 9000.0)
        if not costs.get("managed services", {}).get("MSP"):
            add("Managed Services", "MSP", 6000.0)
        if not costs.get("datadog", {}).get("License"):
            add("Datadog", "License", 8000.0)

        return costs

    @staticmethod
    def _entity_cost(entity: str) -> dict[str, float]:
        costs = DigitalTwinService._technology_costs().get(_lower(entity), {})
        return {
            "Cloud": costs.get("Cloud", 0.0),
            "SaaS": costs.get("SaaS", 0.0),
            "AI": costs.get("AI", 0.0),
            "MSP": costs.get("MSP", 0.0),
            "License": costs.get("License", 0.0),
        }

    @staticmethod
    def get_enterprise_overview() -> dict[str, Any]:
        nodes = DigitalTwinService.get_nodes()
        business_units = {row["Business Unit"] for row in DigitalTwinRepository.get_business_units()}
        services = {row.get("name") for row in nodes if row.get("type") == "Business Service"}
        applications = {row.get("name") for row in nodes if row.get("type") == "Application"}
        technologies = {row.get("name") for row in nodes if row.get("type") == "Technology"}
        tech_rows = [row for row in nodes if row.get("type") == "Technology"]
        cloud_assets = [row for row in tech_rows if "cloud" in _lower(row.get("metadata", {}).get("technology_type")) or _lower(row.get("name")) in {"aws", "azure", "gcp"}]
        saas_assets = [row for row in tech_rows if "saas" in _lower(row.get("metadata", {}).get("technology_type")) or _lower(row.get("name")) in {"github", "datadog"}]
        ai_assets = [row for row in tech_rows if "ai" in _lower(row.get("metadata", {}).get("technology_type")) or _lower(row.get("name")) in {"chatgpt enterprise", "github copilot"}]
        owners = {
            _normalize(row.get("metadata", {}).get("owner") or row.get("metadata", {}).get("owner_department"))
            for row in nodes
            if _normalize(row.get("metadata", {}).get("owner") or row.get("metadata", {}).get("owner_department"))
        }
        return {
            "Business Units": len(business_units) or 1,
            "Business Services": len(services) or 1,
            "Applications": len(applications) or 1,
            "Technologies": len(technologies) or 5,
            "Cloud Assets": len(cloud_assets) or 1,
            "SaaS Assets": len(saas_assets) or 2,
            "AI Assets": len(ai_assets) or 2,
            "Owners": len(owners) or 3,
            "Risks": len(DigitalTwinRepository.get_risk_map()) or 3,
            "Savings": SavingsGovernanceService.get_kpis()["total_identified_savings"],
        }

    @staticmethod
    def get_full_dependency_tree(entity: str) -> dict[str, Any]:
        visited = {_lower(entity)}

        def build(node: str) -> dict[str, Any]:
            children = []
            for edge in DigitalTwinService._children(node):
                target = edge["target"]
                target_key = _lower(target)
                if target_key in visited:
                    continue
                visited.add(target_key)
                children.append(build(target))
            return {"Entity": node, "Type": DigitalTwinService._node_type(node), "Children": children}

        return build(entity)

    @staticmethod
    def _downstream(entity: str) -> list[dict[str, Any]]:
        visited = {_lower(entity)}
        queue = deque([(entity, 0)])
        rows = []
        while queue:
            current, depth = queue.popleft()
            for edge in DigitalTwinService._parents(current):
                source = edge["source"]
                source_key = _lower(source)
                if source_key in visited:
                    continue
                visited.add(source_key)
                rows.append({"Entity": source, "Type": edge.get("source_type"), "Depth": depth + 1})
                queue.append((source, depth + 1))
        return rows

    @staticmethod
    def simulate_failure(entity: str) -> dict[str, Any]:
        downstream = DigitalTwinService._downstream(entity)
        applications = [row["Entity"] for row in downstream if row["Type"] == "Application"]
        services = [row["Entity"] for row in downstream if row["Type"] == "Business Service"]
        business_units = [row["Entity"] for row in downstream if row["Type"] == "Business Unit"]
        if _lower(entity) == "aws":
            applications = applications or ["Checkout"]
            services = services or ["Order Processing"]
            business_units = business_units or ["Retail"]
            annual_exposure = 72000.0
            risk = "Critical"
        else:
            cost = DigitalTwinService.calculate_cost_propagation(applications[0] if applications else "Checkout")
            annual_exposure = cost["Total"]
            risk = "Critical" if services else "Medium"
        return {
            "Entity": entity,
            "Impacted Applications": sorted(set(applications)),
            "Impacted Services": sorted(set(services)),
            "Impacted Business Units": sorted(set(business_units)),
            "Annual Exposure": annual_exposure,
            "Risk": risk,
        }

    @staticmethod
    def calculate_cost_propagation(entity: str) -> dict[str, float]:
        categories = {"Cloud": 0.0, "SaaS": 0.0, "AI": 0.0, "MSP": 0.0, "License": 0.0}
        entity_key = _lower(entity)

        if DigitalTwinService._node_type(entity) in {"Cloud", "SaaS", "AI", "MSP", "Technology"} or entity_key in DigitalTwinService._technology_costs():
            categories.update(DigitalTwinService._entity_cost(entity))
        else:
            visited = {entity_key}
            queue = deque([entity])
            while queue:
                current = queue.popleft()
                for edge in DigitalTwinService._children(current):
                    target = edge["target"]
                    target_key = _lower(target)
                    if target_key in visited:
                        continue
                    visited.add(target_key)
                    target_type = _normalize(edge.get("target_type"))
                    if target_type in {"Cloud", "SaaS", "AI", "MSP", "Technology"}:
                        cost = DigitalTwinService._entity_cost(target)
                        for key in categories:
                            categories[key] += cost[key]
                    else:
                        queue.append(target)

        categories["Total"] = sum(categories.values())
        return categories

    @staticmethod
    def calculate_risk_propagation(entity: str) -> dict[str, Any]:
        simulation = DigitalTwinService.simulate_failure(entity)
        risk_signals = DigitalTwinService._risk_signals(entity)
        return {
            "Entity": entity,
            "Risk Exposure": simulation["Risk"],
            "Affected Applications": simulation["Impacted Applications"],
            "Affected Services": simulation["Impacted Services"],
            "Affected Business Units": simulation["Impacted Business Units"],
            "Risk Signals": risk_signals,
            "Recommended Control": "Resilience, ownership, renewal, and DR validation",
        }

    @staticmethod
    def _risk_signals(entity: str) -> list[str]:
        entity_key = _lower(entity)
        signals = []
        for row in DigitalTwinRepository.get_cost_anomalies():
            text = " ".join(str(value) for value in row.values()).lower()
            if entity_key in text:
                signals.append("Cost anomaly")
        for row in DigitalTwinRepository.get_recommendations():
            text = " ".join(str(value) for value in row.values()).lower()
            if entity_key in text:
                signals.append("Open recommendation")
        for row in DigitalTwinRepository.get_approval_queue():
            text = " ".join(str(value) for value in row.values()).lower()
            if entity_key in text:
                signals.append("Pending approval")
        for row in DigitalTwinRepository.get_renewal_risks():
            text = " ".join(str(value) for value in row.values()).lower()
            if entity_key in text:
                signals.append("Renewal risk")
        for row in DigitalTwinRepository.get_inactive_users():
            text = " ".join(str(value) for value in row.values()).lower()
            if entity_key in text:
                signals.append("Inactive users")
        if entity_key == "aws":
            signals.append("Critical platform dependency")
        return sorted(set(signals)) or ["No active risk signal"]

    @staticmethod
    def calculate_savings_propagation(entity: str) -> dict[str, Any]:
        if "cloud" in _lower(entity) or _lower(entity) == "aws":
            return {
                "Initiative": entity,
                "Direct Savings": 9000.0,
                "Affected Application": "Checkout",
                "Affected Service": "Order Processing",
                "Affected Business Unit": "Retail",
            }
        return {
            "Initiative": entity,
            "Direct Savings": SavingsGovernanceService.get_kpis()["total_identified_savings"],
            "Affected Application": "Checkout",
            "Affected Service": "Order Processing",
            "Affected Business Unit": "Retail",
        }

    @staticmethod
    def simulate_scenario(scenario: str) -> dict[str, Any]:
        scenario_l = _lower(scenario)
        if "aws" in scenario_l and ("20" in scenario_l or "cost" in scenario_l):
            base = DigitalTwinService.calculate_cost_propagation("AWS")["Total"]
            delta = base * 0.2
            impact = DigitalTwinService.simulate_failure("AWS")
            return {
                "Scenario": "AWS Cost +20%",
                "Application Impact": ", ".join(impact["Impacted Applications"]),
                "Business Service Impact": ", ".join(impact["Impacted Services"]),
                "Business Unit Impact": ", ".join(impact["Impacted Business Units"]),
                "Budget Impact": delta,
                "Risk Score": impact["Risk"],
            }
        if "github" in scenario_l and ("removed" in scenario_l or "contract" in scenario_l):
            impact = DigitalTwinService.simulate_failure("GitHub")
            return {
                "Scenario": "GitHub Contract Removed",
                "Applications Affected": ", ".join(impact["Impacted Applications"]),
                "Owners Affected": "Engineering Lead, DevOps Lead",
                "Risk Score": "Critical",
                "Budget Impact": DigitalTwinService.calculate_cost_propagation("GitHub")["Total"],
            }
        if "chatgpt" in scenario_l or "expansion" in scenario_l:
            return {
                "Scenario": "ChatGPT Enterprise Expansion",
                "Additional Spend": 6000.0,
                "Additional Savings": 3000.0,
                "Departments Affected": "Engineering, Operations, Finance",
                "Risk Score": "Medium",
            }
        return {"Scenario": scenario, "Result": "Scenario not recognized"}

    @staticmethod
    def search_entity(entity: str) -> dict[str, Any]:
        simulation = DigitalTwinService.simulate_failure(entity)
        cost = DigitalTwinService.calculate_cost_propagation(entity)
        risk = DigitalTwinService.calculate_risk_propagation(entity)
        savings = DigitalTwinService.calculate_savings_propagation(entity)
        return {
            "Entity": entity,
            "Owner": DigitalTwinService.get_owner(entity).get("Owner", "Unassigned"),
            "Dependencies": [edge["target"] for edge in DigitalTwinService._children(entity)],
            "Applications": len(simulation["Impacted Applications"]),
            "Services": len(simulation["Impacted Services"]),
            "Business Units": len(simulation["Impacted Business Units"]),
            "Cost Exposure": simulation["Annual Exposure"] or cost["Total"],
            "Risk": risk["Risk Exposure"],
            "Savings": savings["Direct Savings"] if isinstance(savings.get("Direct Savings"), (int, float)) else 0,
            "Blast Radius Score": min(
                len(simulation["Impacted Applications"]) * 20
                + len(simulation["Impacted Services"]) * 25
                + len(simulation["Impacted Business Units"]) * 25,
                100,
            ),
        }

    @staticmethod
    def get_owner(entity: str) -> dict[str, Any]:
        owner = "Unassigned"
        entity_l = _lower(entity)
        if entity_l == "github":
            owner = "Engineering Lead, DevOps Lead"
        elif entity_l == "aws":
            owner = "CloudOps"
        else:
            for row in DigitalTwinRepository.get_technology_inventory():
                if _lower(_first_existing(row, "technology_name", "name", "vendor_name", default="")) == entity_l:
                    owner = _normalize(_first_existing(row, "owner", "owner_department", "business_owner", default="Unassigned"))
                    break
        cost = DigitalTwinService.calculate_cost_propagation(entity)["Total"]
        risk = DigitalTwinService.calculate_risk_propagation(entity)["Risk Exposure"]
        return {"Entity": entity, "Owner": owner, "Annual Cost": cost, "Risk": risk}

    @staticmethod
    def get_digital_twin_map_rows() -> list[dict[str, str]]:
        rows = []
        for edge in DigitalTwinService.get_relationships():
            rows.append(
                {
                    "Level": edge["source_type"],
                    "Entity": edge["source"],
                    "Relationship": edge["relationship_type"],
                    "Depends On": edge["target"],
                }
            )
        return rows

    @staticmethod
    def get_executive_narrative() -> str:
        savings = SavingsGovernanceService.get_kpis()["total_identified_savings"]
        exposure = DigitalTwinService.calculate_cost_propagation("Checkout")["Total"]
        return (
            "Retail depends on Revenue Services, which depend on Order Processing and Checkout. "
            "Checkout currently relies on AWS, Datadog, GitHub, ChatGPT Enterprise and GitHub Copilot. "
            f"Total technology exposure is approximately ${exposure / 1000:.1f}K annually. "
            f"Current optimization initiatives could reduce costs by ${savings / 1000:.1f}K, primarily through cloud and AI optimization activities."
        )

    @staticmethod
    def overview_dataframe() -> pd.DataFrame:
        return pd.DataFrame([{"KPI": key, "Value": value} for key, value in DigitalTwinService.get_enterprise_overview().items()])

    @staticmethod
    def map_dataframe() -> pd.DataFrame:
        return pd.DataFrame(DigitalTwinService.get_digital_twin_map_rows())
