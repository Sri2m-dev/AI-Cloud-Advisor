from __future__ import annotations

from collections import deque
from functools import lru_cache
from heapq import heappop, heappush
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from repositories.enterprise_graph_repository import EnterpriseGraphRepository

try:
    import networkx as nx
except Exception:  # pragma: no cover - optional dependency fallback
    nx = None


class EnterpriseGraphService:
    @staticmethod
    def build_graph(organization_id: str | None = None, refresh: bool = False) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        if refresh:
            EnterpriseGraphService._cached_graph.cache_clear()
        graph_data = EnterpriseGraphService._cached_graph(org_id)
        return {
            "organization_id": org_id,
            "nodes": graph_data["nodes"],
            "edges": graph_data["edges"],
            "node_count": len(graph_data["nodes"]),
            "edge_count": len(graph_data["edges"]),
            "metrics": EnterpriseGraphService._metrics(graph_data),
        }

    @staticmethod
    def get_node(node: str, organization_id: str | None = None) -> dict[str, Any] | None:
        graph_data = EnterpriseGraphService._cached_graph(resolve_organization_id(organization_id))
        node_id = EnterpriseGraphService._resolve_node_id(graph_data, node)
        return graph_data["node_by_id"].get(node_id) if node_id else None

    @staticmethod
    def get_neighbors(node: str, organization_id: str | None = None) -> list[dict[str, Any]]:
        graph_data = EnterpriseGraphService._cached_graph(resolve_organization_id(organization_id))
        node_id = EnterpriseGraphService._resolve_node_id(graph_data, node)
        if not node_id:
            return []
        neighbors = []
        for edge in graph_data["edges"]:
            if edge["source"] == node_id:
                neighbor = graph_data["node_by_id"].get(edge["target"])
                if neighbor:
                    neighbors.append({"direction": "out", "relationship": edge["relationship_type"], "node": neighbor})
            if edge["target"] == node_id:
                neighbor = graph_data["node_by_id"].get(edge["source"])
                if neighbor:
                    neighbors.append({"direction": "in", "relationship": edge["relationship_type"], "node": neighbor})
        return neighbors

    @staticmethod
    def shortest_path(source: str, target: str, organization_id: str | None = None) -> list[dict[str, Any]]:
        graph_data = EnterpriseGraphService._cached_graph(resolve_organization_id(organization_id))
        source_id = EnterpriseGraphService._resolve_node_id(graph_data, source)
        target_id = EnterpriseGraphService._resolve_node_id(graph_data, target)
        if not source_id or not target_id:
            return []

        path = EnterpriseGraphService._weighted_path(graph_data, source_id, target_id)
        return EnterpriseGraphService._path_rows(graph_data, path)

    @staticmethod
    def find_path(source: str, target: str, organization_id: str | None = None) -> list[dict[str, Any]]:
        return EnterpriseGraphService.shortest_path(source, target, organization_id)

    @staticmethod
    def find_dependencies(node: str, organization_id: str | None = None, depth: int = 2) -> list[dict[str, Any]]:
        graph_data = EnterpriseGraphService._cached_graph(resolve_organization_id(organization_id))
        node_id = EnterpriseGraphService._resolve_node_id(graph_data, node)
        if not node_id:
            return []
        return EnterpriseGraphService._walk(graph_data, node_id, depth, direction="both")

    @staticmethod
    def find_impacted_nodes(node: str, organization_id: str | None = None, depth: int = 4) -> list[dict[str, Any]]:
        graph_data = EnterpriseGraphService._cached_graph(resolve_organization_id(organization_id))
        node_id = EnterpriseGraphService._resolve_node_id(graph_data, node)
        if not node_id:
            return []
        priority_types = {"Application", "Business Service", "Business Capability", "Owner", "Department", "Business Unit"}
        rows = EnterpriseGraphService._walk(graph_data, node_id, depth, direction="both")
        return [row for row in rows if row["node"]["type"] in priority_types]

    @staticmethod
    def subgraph(
        node: str | None = None,
        node_type: str | None = None,
        edge_type: str | None = None,
        organization_id: str | None = None,
        depth: int = 2,
        limit: int = 150,
    ) -> dict[str, list[dict[str, Any]]]:
        graph_data = EnterpriseGraphService._cached_graph(resolve_organization_id(organization_id))
        if node:
            node_id = EnterpriseGraphService._resolve_node_id(graph_data, node)
            if not node_id:
                return {"nodes": [], "edges": []}
            walked = EnterpriseGraphService._walk(graph_data, node_id, depth, direction="both")
            node_ids = {node_id, *[row["node"]["id"] for row in walked]}
        else:
            node_ids = {row["id"] for row in graph_data["nodes"] if not node_type or row["type"] == node_type}

        edges = [
            edge
            for edge in graph_data["edges"]
            if edge["source"] in node_ids
            and edge["target"] in node_ids
            and (not edge_type or edge["relationship_type"] == edge_type)
        ][:limit]
        edge_node_ids = {edge["source"] for edge in edges} | {edge["target"] for edge in edges}
        if node:
            edge_node_ids.add(EnterpriseGraphService._resolve_node_id(graph_data, node))
        nodes = [graph_data["node_by_id"][node_id] for node_id in list(edge_node_ids)[:limit] if node_id in graph_data["node_by_id"]]
        return {"nodes": nodes, "edges": edges}

    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        graph = EnterpriseGraphService.build_graph(organization_id)
        graph_data = EnterpriseGraphService._cached_graph(graph["organization_id"])
        return {
            "summary": graph["metrics"],
            "nodes": graph["nodes"],
            "edges": graph["edges"],
            "node_types": EnterpriseGraphService._distribution(graph["nodes"], "type", "Node Type"),
            "edge_types": EnterpriseGraphService._distribution(graph["edges"], "relationship_type", "Edge Type"),
            "critical_nodes": EnterpriseGraphService._critical_nodes(graph_data)[:15],
            "orphan_nodes": EnterpriseGraphService._orphan_nodes(graph_data)[:25],
        }

    @staticmethod
    @lru_cache(maxsize=16)
    def _cached_graph(organization_id: str) -> dict[str, Any]:
        data = EnterpriseGraphRepository.load_nodes_and_edges(organization_id)
        nodes = data["nodes"]
        edges = data["edges"]
        node_by_id = {node["id"]: node for node in nodes}
        label_index: dict[str, str] = {}
        for node in nodes:
            label_index.setdefault(node["name"].lower(), node["id"])
            label_index.setdefault(node["id"].lower(), node["id"])

        adjacency: dict[str, set[str]] = {node["id"]: set() for node in nodes}
        edge_lookup: dict[tuple[str, str], dict[str, Any]] = {}
        for edge in edges:
            adjacency.setdefault(edge["source"], set()).add(edge["target"])
            adjacency.setdefault(edge["target"], set()).add(edge["source"])
            edge_lookup.setdefault((edge["source"], edge["target"]), edge)
            edge_lookup.setdefault((edge["target"], edge["source"]), edge)

        graph = None
        if nx is not None:
            graph = nx.Graph()
            for node in nodes:
                graph.add_node(node["id"], **node)
            for edge in edges:
                graph.add_edge(edge["source"], edge["target"], **edge)

        return {
            "nodes": nodes,
            "edges": edges,
            "node_by_id": node_by_id,
            "label_index": label_index,
            "adjacency": adjacency,
            "edge_lookup": edge_lookup,
            "graph": graph,
        }

    @staticmethod
    def _resolve_node_id(graph_data: dict[str, Any], node: str) -> str | None:
        key = str(node or "").strip().lower()
        if key in graph_data["label_index"]:
            return graph_data["label_index"][key]
        for label, node_id in graph_data["label_index"].items():
            if key and key in label:
                return node_id
        return None

    @staticmethod
    def _bfs_path(adjacency: dict[str, set[str]], source: str, target: str) -> list[str]:
        queue = deque([[source]])
        visited = {source}
        while queue:
            path = queue.popleft()
            current = path[-1]
            if current == target:
                return path
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append([*path, neighbor])
        return []

    @staticmethod
    def _weighted_path(graph_data: dict[str, Any], source: str, target: str) -> list[str]:
        queue: list[tuple[int, int, str, list[str]]] = [(0, 0, source, [source])]
        best: dict[str, int] = {source: 0}
        counter = 0
        while queue:
            cost, _counter, current, path = heappop(queue)
            if current == target:
                return path
            if cost > best.get(current, 10**9):
                continue
            for neighbor in graph_data["adjacency"].get(current, set()):
                edge = graph_data["edge_lookup"].get((current, neighbor), {})
                next_cost = cost + EnterpriseGraphService._edge_weight(edge)
                if next_cost < best.get(neighbor, 10**9):
                    best[neighbor] = next_cost
                    counter += 1
                    heappush(queue, (next_cost, counter, neighbor, [*path, neighbor]))
        return []

    @staticmethod
    def _edge_weight(edge: dict[str, Any]) -> int:
        relation = str(edge.get("relationship_type") or "").upper()
        if edge.get("source_type") == "Organization" or edge.get("target_type") == "Organization":
            return 12
        weights = {
            "SUPPORTS": 1,
            "USES": 1,
            "OWNS": 1,
            "HOSTED_ON": 1,
            "PART_OF": 1,
            "PROVIDED_BY": 1,
            "FUNDED_BY": 2,
            "BELONGS_TO": 2,
            "GENERATES_COST": 3,
            "EXECUTES": 4,
            "IMPLEMENTS": 5,
            "APPROVED_BY": 5,
            "RELATED_TO": 8,
        }
        return weights.get(relation, 4)

    @staticmethod
    def _path_rows(graph_data: dict[str, Any], path: list[str]) -> list[dict[str, Any]]:
        rows = []
        for index, node_id in enumerate(path):
            node = graph_data["node_by_id"].get(node_id)
            if not node:
                continue
            edge = graph_data["edge_lookup"].get((path[index - 1], node_id)) if index else None
            rows.append(
                {
                    "step": index + 1,
                    "node": node["name"],
                    "node_type": node["type"],
                    "relationship": edge.get("relationship_type") if edge else None,
                }
            )
        return rows

    @staticmethod
    def _walk(graph_data: dict[str, Any], start_id: str, depth: int, direction: str) -> list[dict[str, Any]]:
        del direction
        rows = []
        queue = deque([(start_id, 0)])
        visited = {start_id}
        while queue:
            current, current_depth = queue.popleft()
            if current_depth >= depth:
                continue
            for neighbor in graph_data["adjacency"].get(current, set()):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                edge = graph_data["edge_lookup"].get((current, neighbor), {})
                node = graph_data["node_by_id"].get(neighbor)
                if node:
                    rows.append({"depth": current_depth + 1, "relationship": edge.get("relationship_type"), "node": node})
                    queue.append((neighbor, current_depth + 1))
        return rows

    @staticmethod
    def _metrics(graph_data: dict[str, Any]) -> dict[str, Any]:
        nodes = graph_data["nodes"]
        edges = graph_data["edges"]
        node_count = len(nodes)
        edge_count = len(edges)
        orphan_count = len(EnterpriseGraphService._orphan_nodes(graph_data))
        components = EnterpriseGraphService._connected_components(graph_data)
        coverage = round(((node_count - orphan_count) / node_count) * 100, 1) if node_count else 0.0
        health = round((coverage * 0.55) + (min(edge_count / max(node_count, 1), 2) / 2 * 30) + (15 if components <= 3 else 8), 1)
        reasoning = round((coverage * 0.65) + (min(edge_count, node_count * 2) / max(node_count * 2, 1) * 35), 1) if node_count else 0.0
        return {
            "Graph Nodes": node_count,
            "Graph Relationships": edge_count,
            "Connected Components": components,
            "Orphan Nodes": orphan_count,
            "Critical Nodes": len(EnterpriseGraphService._critical_nodes(graph_data)),
            "Dependency Depth": EnterpriseGraphService._max_depth(graph_data),
            "Graph Health Score": min(health, 100.0),
            "Coverage %": coverage,
            "Reasoning Readiness %": min(reasoning, 100.0),
        }

    @staticmethod
    def _connected_components(graph_data: dict[str, Any]) -> int:
        if nx is not None and graph_data.get("graph") is not None:
            return nx.number_connected_components(graph_data["graph"])
        remaining = set(graph_data["adjacency"])
        count = 0
        while remaining:
            count += 1
            start = next(iter(remaining))
            visited = set(EnterpriseGraphService._bfs_reachable(graph_data["adjacency"], start))
            remaining -= visited
        return count

    @staticmethod
    def _bfs_reachable(adjacency: dict[str, set[str]], start: str) -> set[str]:
        visited = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return visited

    @staticmethod
    def _orphan_nodes(graph_data: dict[str, Any]) -> list[dict[str, Any]]:
        return [node for node in graph_data["nodes"] if not graph_data["adjacency"].get(node["id"])]

    @staticmethod
    def _critical_nodes(graph_data: dict[str, Any]) -> list[dict[str, Any]]:
        degrees = [(node_id, len(neighbors)) for node_id, neighbors in graph_data["adjacency"].items()]
        rows = []
        for node_id, degree in sorted(degrees, key=lambda item: item[1], reverse=True):
            node = graph_data["node_by_id"].get(node_id)
            if node and degree >= 3:
                rows.append({"Node": node["name"], "Type": node["type"], "Degree": degree})
        return rows

    @staticmethod
    def _max_depth(graph_data: dict[str, Any]) -> int:
        if not graph_data["nodes"]:
            return 0
        depths = []
        for node in graph_data["nodes"][:50]:
            visited = EnterpriseGraphService._walk(graph_data, node["id"], 8, "both")
            depths.append(max([row["depth"] for row in visited] or [0]))
        return max(depths or [0])

    @staticmethod
    def _distribution(rows: list[dict[str, Any]], key: str, label: str) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for row in rows:
            value = str(row.get(key) or "Unknown")
            counts[value] = counts.get(value, 0) + 1
        return [{label: name, "Count": count} for name, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)]
