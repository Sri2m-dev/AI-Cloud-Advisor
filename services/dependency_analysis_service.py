from __future__ import annotations

from collections import deque
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.enterprise_graph_service import EnterpriseGraphService


class DependencyAnalysisService:
    DEPENDENCY_FORWARD = {
        ("Business Capability", "Business Service"),
        ("Business Service", "Application"),
        ("Application", "Enterprise Asset"),
        ("Enterprise Asset", "Cloud Resource"),
        ("Enterprise Asset", "Cloud Provider"),
        ("Cloud Resource", "Cloud Provider"),
        ("Application", "Cloud Cost"),
        ("Enterprise Asset", "Cloud Cost"),
        ("Application", "Owner"),
        ("Application", "Cost Center"),
        ("Application", "Team"),
        ("Application", "Recommendation"),
        ("Recommendation", "Decision"),
        ("Decision", "Workflow"),
        ("Workflow", "Execution"),
    }

    @staticmethod
    def get_dependency_map(node_id: str, organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        upstream = DependencyAnalysisService.get_upstream_dependencies(node_id, org_id)
        downstream = DependencyAnalysisService.get_downstream_impacts(node_id, org_id)
        return {
            "node": node_id,
            "upstream": upstream,
            "downstream": downstream,
            "depends_on": upstream,
            "impacts": downstream,
            "summary": {
                "upstream_count": len(upstream),
                "downstream_count": len(downstream),
                "max_upstream_depth": max([row["depth"] for row in upstream] or [0]),
                "max_downstream_depth": max([row["depth"] for row in downstream] or [0]),
            },
        }

    @staticmethod
    def get_upstream_dependencies(node_id: str, organization_id: str | None = None) -> list[dict[str, Any]]:
        graph_data = DependencyAnalysisService._graph_data(organization_id)
        start = EnterpriseGraphService._resolve_node_id(graph_data, node_id)
        if not start:
            return []
        rows = DependencyAnalysisService._directed_walk(graph_data, start, mode="dependency", depth=5)
        return DependencyAnalysisService._prioritized(rows)

    @staticmethod
    def get_downstream_impacts(node_id: str, organization_id: str | None = None) -> list[dict[str, Any]]:
        graph_data = DependencyAnalysisService._graph_data(organization_id)
        start = EnterpriseGraphService._resolve_node_id(graph_data, node_id)
        if not start:
            return []
        rows = DependencyAnalysisService._directed_walk(graph_data, start, mode="impact", depth=5)
        return DependencyAnalysisService._prioritized(rows)

    @staticmethod
    def get_single_points_of_failure(organization_id: str | None = None) -> list[dict[str, Any]]:
        graph_data = DependencyAnalysisService._graph_data(organization_id)
        candidates = [
            node
            for node in graph_data["nodes"]
            if node["type"] in {"Enterprise Asset", "Cloud Provider", "Cloud Resource", "Technology"}
        ]
        rows = []
        for node in candidates:
            impacts = DependencyAnalysisService.get_downstream_impacts(node["name"], organization_id)
            impacted_capabilities = {row["node"] for row in impacts if row["node_type"] == "Business Capability"}
            impacted_apps = {row["node"] for row in impacts if row["node_type"] == "Application"}
            if impacted_capabilities or len(impacted_apps) >= 1:
                rows.append(
                    {
                        "Node": node["name"],
                        "Type": node["type"],
                        "Impacted Applications": len(impacted_apps),
                        "Impacted Capabilities": len(impacted_capabilities),
                        "Impact Score": len(impacted_apps) * 10 + len(impacted_capabilities) * 25,
                    }
                )
        return sorted(rows, key=lambda row: row["Impact Score"], reverse=True)

    @staticmethod
    def get_critical_dependency_paths(organization_id: str | None = None) -> list[dict[str, Any]]:
        graph_data = DependencyAnalysisService._graph_data(organization_id)
        capabilities = [node for node in graph_data["nodes"] if node["type"] == "Business Capability"]
        providers = [node for node in graph_data["nodes"] if node["type"] == "Cloud Provider"]
        rows = []
        for capability in capabilities:
            for provider in providers:
                path = EnterpriseGraphService.find_path(capability["name"], provider["name"], organization_id)
                if len(path) >= 4:
                    rows.append(
                        {
                            "Capability": capability["name"],
                            "Provider": provider["name"],
                            "Depth": len(path) - 1,
                            "Path": " -> ".join(row["node"] for row in path),
                        }
                    )
        return sorted(rows, key=lambda row: row["Depth"], reverse=True)

    @staticmethod
    def get_provider_dependency_summary(organization_id: str | None = None) -> list[dict[str, Any]]:
        graph_data = DependencyAnalysisService._graph_data(organization_id)
        providers = [node for node in graph_data["nodes"] if node["type"] == "Cloud Provider"]
        rows = []
        for provider in providers:
            impacts = DependencyAnalysisService.get_downstream_impacts(provider["name"], organization_id)
            rows.append(
                {
                    "Provider": provider["name"],
                    "Applications": len({row["node"] for row in impacts if row["node_type"] == "Application"}),
                    "Capabilities": len({row["node"] for row in impacts if row["node_type"] == "Business Capability"}),
                    "Assets": len({row["node"] for row in impacts if row["node_type"] == "Enterprise Asset"}),
                    "Impact Count": len(impacts),
                }
            )
        return sorted(rows, key=lambda row: row["Impact Count"], reverse=True)

    @staticmethod
    def get_application_dependency_summary(organization_id: str | None = None) -> list[dict[str, Any]]:
        graph_data = DependencyAnalysisService._graph_data(organization_id)
        applications = [node for node in graph_data["nodes"] if node["type"] == "Application"]
        rows = []
        for app in applications:
            dependencies = DependencyAnalysisService.get_upstream_dependencies(app["name"], organization_id)
            impacts = DependencyAnalysisService.get_downstream_impacts(app["name"], organization_id)
            rows.append(
                {
                    "Application": app["name"],
                    "Dependencies": len(dependencies),
                    "Impacts": len(impacts),
                    "Assets": len({row["node"] for row in dependencies if row["node_type"] == "Enterprise Asset"}),
                    "Providers": len({row["node"] for row in dependencies if row["node_type"] == "Cloud Provider"}),
                    "Capabilities": len({row["node"] for row in impacts if row["node_type"] == "Business Capability"}),
                    "Risk": "High" if len(impacts) >= 5 else "Medium" if len(impacts) >= 2 else "Low",
                }
            )
        return sorted(rows, key=lambda row: (row["Impacts"], row["Dependencies"]), reverse=True)

    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        graph = EnterpriseGraphService.build_graph(organization_id)
        provider_summary = DependencyAnalysisService.get_provider_dependency_summary(organization_id)
        app_summary = DependencyAnalysisService.get_application_dependency_summary(organization_id)
        single_points = DependencyAnalysisService.get_single_points_of_failure(organization_id)
        critical_paths = DependencyAnalysisService.get_critical_dependency_paths(organization_id)
        most_connected = max(
            EnterpriseGraphService.get_dashboard(organization_id).get("critical_nodes", []),
            key=lambda row: row.get("Degree", 0),
            default={},
        )
        return {
            "summary": {
                "Total Dependencies": graph["edge_count"],
                "Critical Paths": len(critical_paths),
                "Single Points of Failure": len(single_points),
                "High-Risk Applications": len([row for row in app_summary if row["Risk"] == "High"]),
                "Provider Concentration": provider_summary[0]["Provider"] if provider_summary else "Unknown",
                "Average Dependency Depth": DependencyAnalysisService._average_path_depth(critical_paths),
                "Most Connected Node": most_connected.get("Node", "Unknown"),
            },
            "provider_dependency_summary": provider_summary,
            "application_dependency_summary": app_summary,
            "single_points_of_failure": single_points,
            "critical_dependency_paths": critical_paths,
        }

    @staticmethod
    def _graph_data(organization_id: str | None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        EnterpriseGraphService.build_graph(org_id)
        return EnterpriseGraphService._cached_graph(org_id)

    @staticmethod
    def _directed_walk(graph_data: dict[str, Any], start: str, mode: str, depth: int) -> list[dict[str, Any]]:
        rows = []
        queue = deque([(start, 0)])
        visited = {start}
        while queue:
            current, current_depth = queue.popleft()
            if current_depth >= depth:
                continue
            for edge, neighbor in DependencyAnalysisService._oriented_neighbors(graph_data, current, mode):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                node = graph_data["node_by_id"].get(neighbor)
                if not node:
                    continue
                rows.append(
                    {
                        "depth": current_depth + 1,
                        "node": node["name"],
                        "node_type": node["type"],
                        "relationship": edge.get("relationship_type"),
                        "path_hint": f"{edge.get('source_name')} -> {edge.get('target_name')}",
                    }
                )
                queue.append((neighbor, current_depth + 1))
        return rows

    @staticmethod
    def _oriented_neighbors(graph_data: dict[str, Any], current: str, mode: str) -> list[tuple[dict[str, Any], str]]:
        pairs = []
        for edge in graph_data["edges"]:
            if edge["source"] != current and edge["target"] != current:
                continue
            source = graph_data["node_by_id"].get(edge["source"], {})
            target = graph_data["node_by_id"].get(edge["target"], {})
            forward = DependencyAnalysisService._dependency_direction(edge, source, target)
            if mode == "impact":
                if current == edge["target"] and forward == "source_to_target":
                    pairs.append((edge, edge["source"]))
                elif current == edge["source"] and forward == "target_to_source":
                    pairs.append((edge, edge["target"]))
                elif current == edge["source"] and DependencyAnalysisService._is_impact_side_edge(edge):
                    pairs.append((edge, edge["target"]))
                elif forward == "both":
                    pairs.append((edge, edge["target"] if current == edge["source"] else edge["source"]))
            else:
                if current == edge["source"] and forward == "source_to_target":
                    pairs.append((edge, edge["target"]))
                elif current == edge["target"] and forward == "target_to_source":
                    pairs.append((edge, edge["source"]))
                elif forward == "both":
                    pairs.append((edge, edge["target"] if current == edge["source"] else edge["source"]))
        return pairs

    @staticmethod
    def _is_impact_side_edge(edge: dict[str, Any]) -> bool:
        return edge.get("relationship_type") in {
            "OWNED_BY",
            "FUNDED_BY",
            "GENERATES_COST",
            "BELONGS_TO",
            "SUPPORTED_BY",
            "PART_OF",
            "USES",
        }

    @staticmethod
    def _dependency_direction(edge: dict[str, Any], source: dict[str, Any], target: dict[str, Any]) -> str:
        source_type = source.get("type") or edge.get("source_type")
        target_type = target.get("type") or edge.get("target_type")
        pair = (source_type, target_type)
        reverse_pair = (target_type, source_type)
        relation = edge.get("relationship_type")

        if pair in DependencyAnalysisService.DEPENDENCY_FORWARD:
            return "source_to_target"
        if reverse_pair in DependencyAnalysisService.DEPENDENCY_FORWARD:
            return "target_to_source"
        if relation in {"SUPPORTS"}:
            return "source_to_target"
        if relation in {"OWNS", "USES", "HOSTED_ON", "PART_OF", "PROVIDED_BY", "GENERATES_COST"}:
            return "source_to_target"
        if relation in {"IMPLEMENTS", "EXECUTES"}:
            return "target_to_source"
        if relation in {"RELATED_TO", "APPROVED_BY"}:
            return "both"
        return "source_to_target"

    @staticmethod
    def _prioritized(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        priority = {
            "Cloud Provider": 1,
            "Cloud Resource": 2,
            "Enterprise Asset": 3,
            "Application": 4,
            "Business Service": 5,
            "Business Capability": 6,
            "Owner": 7,
            "Cost Center": 8,
            "Cloud Cost": 9,
            "Recommendation": 10,
            "Decision": 11,
            "Workflow": 12,
            "Execution": 13,
        }
        return sorted(rows, key=lambda row: (row["depth"], priority.get(row["node_type"], 99), row["node"]))

    @staticmethod
    def _average_path_depth(paths: list[dict[str, Any]]) -> float:
        if not paths:
            return 0.0
        return round(sum(float(row.get("Depth") or 0) for row in paths) / len(paths), 1)
