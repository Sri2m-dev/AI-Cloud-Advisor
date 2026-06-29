from __future__ import annotations

from collections import deque
from typing import Any

import pandas as pd

from repositories.knowledge_graph_repository import KnowledgeGraphRepository


DEPENDENCY_TYPES = {"USES", "DEPENDS_ON", "HOSTED_ON", "SUPPORTED_BY", "USES_AI", "USES_SAAS"}
CRITICAL_TECHNOLOGIES = {"aws", "datadog", "github", "chatgpt enterprise", "github copilot"}


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


class KnowledgeGraphService:
    @staticmethod
    def get_nodes() -> list[dict[str, Any]]:
        return KnowledgeGraphRepository.get_all_nodes()

    @staticmethod
    def get_relationships() -> list[dict[str, Any]]:
        return KnowledgeGraphRepository.get_all_relationships()

    @staticmethod
    def _node_type_lookup() -> dict[str, str]:
        return {_lower(row["name"]): row["type"] for row in KnowledgeGraphService.get_nodes()}

    @staticmethod
    def _metadata_lookup() -> dict[str, dict[str, Any]]:
        return {_lower(row["name"]): row.get("metadata", {}) for row in KnowledgeGraphService.get_nodes()}

    @staticmethod
    def _owner_lookup() -> dict[str, list[str]]:
        owners: dict[str, list[str]] = {}
        for row in KnowledgeGraphService.get_relationships():
            if row["relationship_type"] != "OWNED_BY":
                continue
            owners.setdefault(_lower(row["source_name"]), []).append(row["target_name"])
        return owners

    @staticmethod
    def _children(node_name: str) -> list[dict[str, Any]]:
        name = _lower(node_name)
        return [
            row
            for row in KnowledgeGraphService.get_relationships()
            if _lower(row["source_name"]) == name and row["relationship_type"] in DEPENDENCY_TYPES
        ]

    @staticmethod
    def _parents(node_name: str) -> list[dict[str, Any]]:
        name = _lower(node_name)
        return [
            row
            for row in KnowledgeGraphService.get_relationships()
            if _lower(row["target_name"]) == name and row["relationship_type"] in DEPENDENCY_TYPES
        ]

    @staticmethod
    def get_upstream_dependencies(node_name: str) -> list[dict[str, Any]]:
        return [
            {
                "Node": row["target_name"],
                "Type": row["target_type"],
                "Relationship": row["relationship_type"],
            }
            for row in KnowledgeGraphService._children(node_name)
        ]

    @staticmethod
    def get_downstream_dependencies(node_name: str) -> list[dict[str, Any]]:
        visited = {_lower(node_name)}
        queue = deque([(node_name, 0)])
        rows: list[dict[str, Any]] = []

        while queue:
            current, depth = queue.popleft()
            for edge in KnowledgeGraphService._parents(current):
                parent = edge["source_name"]
                parent_key = _lower(parent)
                if parent_key in visited:
                    continue
                visited.add(parent_key)
                rows.append(
                    {
                        "Node": parent,
                        "Type": edge["source_type"],
                        "Relationship": edge["relationship_type"],
                        "Depth": depth + 1,
                    }
                )
                queue.append((parent, depth + 1))

        return rows

    @staticmethod
    def get_dependency_tree(node_name: str) -> dict[str, Any]:
        upstream = KnowledgeGraphService.get_upstream_dependencies(node_name)
        downstream = KnowledgeGraphService.get_downstream_dependencies(node_name)
        return {
            "node": node_name,
            "upstream": upstream,
            "downstream": downstream,
        }

    @staticmethod
    def get_impact_analysis(node_name: str) -> dict[str, Any]:
        downstream = KnowledgeGraphService.get_downstream_dependencies(node_name)
        upstream = KnowledgeGraphService.get_upstream_dependencies(node_name)
        metadata = KnowledgeGraphService._metadata_lookup()
        owner_lookup = KnowledgeGraphService._owner_lookup()

        impacted_applications = sorted({row["Node"] for row in downstream if row["Type"] == "Application"})
        impacted_services = sorted({row["Node"] for row in downstream if row["Type"] == "Business Service"})
        impacted_technologies = sorted({node_name} | {row["Node"] for row in upstream if row["Type"] == "Technology"})
        impacted_owners = sorted(
            {
                str(owner)
                for technology in impacted_technologies
                for owner in (
                    owner_lookup.get(_lower(technology))
                    or [metadata.get(_lower(technology), {}).get("owner")]
                )
                if owner
            }
        )
        spend_impact = sum(
            _safe_float(metadata.get(_lower(technology), {}).get("cost"))
            for technology in impacted_technologies
        )

        if _lower(node_name) == "aws":
            spend_impact = max(spend_impact, 72000)

        risk = "Critical" if impacted_services or _lower(node_name) in CRITICAL_TECHNOLOGIES else "Medium"

        return {
            "Node": node_name,
            "Applications": len(impacted_applications),
            "Business Services": len(impacted_services),
            "Impacted Technologies": len(impacted_technologies),
            "Impacted Spend": spend_impact,
            "Impacted Owners": impacted_owners,
            "Risk": risk,
            "Path": [node_name] + [row["Node"] for row in downstream],
        }

    @staticmethod
    def get_cost_blast_radius(application_name: str) -> dict[str, float]:
        categories = {
            "Cloud": 0.0,
            "SaaS": 0.0,
            "MSP": 0.0,
            "License": 0.0,
            "AI": 0.0,
        }
        app_key = _lower(application_name)
        for row in KnowledgeGraphService.get_relationships():
            if _lower(row["source_name"]) != app_key:
                continue
            if row["relationship_type"] not in DEPENDENCY_TYPES:
                continue
            metadata = row.get("metadata", {})
            domain = _normalize(metadata.get("cost_domain"))
            cost = _safe_float(metadata.get("cost"))
            if domain in categories:
                categories[domain] += cost

        categories["Total"] = sum(categories.values())
        return categories

    @staticmethod
    def get_explorer_levels(business_service: str | None = None, application: str | None = None) -> dict[str, Any]:
        nodes = KnowledgeGraphService.get_nodes()
        services = sorted(row["name"] for row in nodes if row["type"] == "Business Service")
        selected_service = business_service or (services[0] if services else "Order Processing")

        applications = [
            row["Node"]
            for row in KnowledgeGraphService.get_upstream_dependencies(selected_service)
            if row["Type"] == "Application"
        ]
        selected_application = application or (applications[0] if applications else "Checkout")

        technologies = [
            row["Node"]
            for row in KnowledgeGraphService.get_upstream_dependencies(selected_application)
            if row["Type"] == "Technology"
        ]
        metadata = KnowledgeGraphService._metadata_lookup()
        owner_lookup = KnowledgeGraphService._owner_lookup()
        level_four = [
            {
                "Technology": technology,
                "Owner": ", ".join(owner_lookup.get(_lower(technology), []))
                or metadata.get(_lower(technology), {}).get("owner", "Unassigned"),
                "Cost": metadata.get(_lower(technology), {}).get("cost", 0),
                "Risk": "Critical" if _lower(technology) == "aws" else "Medium" if _lower(technology) in {"github", "datadog"} else "Low",
                "Renewal": "Review",
                "Vendor": metadata.get(_lower(technology), {}).get("vendor", "Unknown"),
            }
            for technology in technologies
        ]

        return {
            "business_services": services,
            "selected_service": selected_service,
            "applications": applications,
            "selected_application": selected_application,
            "technologies": technologies,
            "details": level_four,
        }

    @staticmethod
    def get_graph_kpis() -> dict[str, int]:
        nodes = KnowledgeGraphService.get_nodes()
        relationships = KnowledgeGraphService.get_relationships()
        return {
            "Business Services": len({row["name"] for row in nodes if row["type"] == "Business Service"}),
            "Applications": len({row["name"] for row in nodes if row["type"] == "Application"}),
            "Technologies": len({row["name"] for row in nodes if row["type"] == "Technology"}),
            "Relationships": len(relationships),
            "Critical Dependencies": len(
                [
                    row
                    for row in relationships
                    if row["relationship_type"] in {"DEPENDS_ON", "USES_AI", "HOSTED_ON"}
                    and _lower(row["target_name"]) in CRITICAL_TECHNOLOGIES
                ]
            ),
        }

    @staticmethod
    def answer_question(question: str) -> str:
        text = _lower(question)
        if "what breaks" in text or "fails" in text or "unavailable" in text:
            for node in ["AWS", "GitHub", "Datadog", "ChatGPT Enterprise", "GitHub Copilot"]:
                if _lower(node).replace(" enterprise", "") in text or _lower(node) in text:
                    impact = KnowledgeGraphService.get_impact_analysis(node)
                    return (
                        f"{node} impacts {impact['Applications']} application(s), "
                        f"{impact['Business Services']} business service(s), and "
                        f"${impact['Impacted Spend']:,.0f} in spend. Risk: {impact['Risk']}."
                    )
        if "services use" in text or "use chatgpt" in text:
            downstream = KnowledgeGraphService.get_downstream_dependencies("ChatGPT Enterprise")
            services = [row["Node"] for row in downstream if row["Type"] == "Business Service"]
            return "Services using ChatGPT Enterprise: " + (", ".join(services) if services else "None found.")
        if "applications depend on" in text:
            node = question.split("on")[-1].strip(" ?.")
            downstream = KnowledgeGraphService.get_downstream_dependencies(node)
            apps = [row["Node"] for row in downstream if row["Type"] == "Application"]
            return f"Applications depending on {node}: " + (", ".join(apps) if apps else "None found.")
        if "who owns" in text:
            node = question.split("owns")[-1].strip(" ?.")
            owners = [
                row["target_name"]
                for row in KnowledgeGraphService.get_relationships()
                if _lower(row["source_name"]) == _lower(node)
                and row["relationship_type"] == "OWNED_BY"
            ]
            return f"{node} is owned by " + (", ".join(owners) if owners else "an unassigned owner.")
        if "spend" in text and "checkout" in text:
            blast = KnowledgeGraphService.get_cost_blast_radius("Checkout")
            return f"Checkout has ${blast['Total']:,.0f} total mapped spend across Cloud, SaaS, MSP, License, and AI."
        return "I can answer dependency, ownership, and cost blast-radius questions for the technology knowledge graph."

    @staticmethod
    def relationships_dataframe() -> pd.DataFrame:
        return pd.DataFrame(KnowledgeGraphService.get_relationships())

    @staticmethod
    def nodes_dataframe() -> pd.DataFrame:
        rows = []
        for node in KnowledgeGraphService.get_nodes():
            rows.append({"Node": node["name"], "Type": node["type"], **node.get("metadata", {})})
        return pd.DataFrame(rows)
