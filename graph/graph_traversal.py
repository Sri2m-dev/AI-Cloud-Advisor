from __future__ import annotations

from collections import deque
from enum import StrEnum
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.enterprise_graph_service import EnterpriseGraphService


class TraversalType(StrEnum):
    UPSTREAM = "UPSTREAM"
    DOWNSTREAM = "DOWNSTREAM"
    FULL_GRAPH = "FULL_GRAPH"
    SHORTEST_PATH = "SHORTEST_PATH"
    ALL_IMPACTS = "ALL_IMPACTS"


DEPENDENCY_FORWARD = {
    ("Business Capability", "Business Service"),
    ("Business Service", "Application"),
    ("Application", "Technology"),
    ("Application", "Enterprise Asset"),
    ("Application", "Cloud Resource"),
    ("Technology", "Application"),
    ("Enterprise Asset", "Cloud Resource"),
    ("Enterprise Asset", "Cloud Provider"),
    ("Cloud Resource", "Cloud Provider"),
    ("Application", "Cloud Cost"),
    ("Enterprise Asset", "Cloud Cost"),
    ("Application", "Owner"),
    ("Application", "Department"),
    ("Application", "Cost Center"),
    ("Application", "Team"),
    ("Application", "Recommendation"),
    ("Recommendation", "Decision"),
    ("Decision", "Workflow"),
    ("Workflow", "Execution"),
}


def traverse_graph(
    node: str,
    organization_id: str | None = None,
    traversal_type: TraversalType | str = TraversalType.ALL_IMPACTS,
    depth: int = 6,
    target: str | None = None,
) -> dict[str, Any]:
    org_id = resolve_organization_id(organization_id)
    graph_data = EnterpriseGraphService._cached_graph(org_id)
    start_id = EnterpriseGraphService._resolve_node_id(graph_data, node)
    traversal = TraversalType(str(traversal_type).upper())

    if not start_id:
        return {
            "node": node,
            "node_id": None,
            "traversal_type": traversal.value,
            "paths": [],
            "nodes": [],
            "edges": [],
        }

    if traversal == TraversalType.SHORTEST_PATH:
        path = EnterpriseGraphService.shortest_path(node, target or "", org_id)
        return {
            "node": node,
            "node_id": start_id,
            "target": target,
            "traversal_type": traversal.value,
            "paths": [path] if path else [],
            "nodes": path,
            "edges": _path_edges(graph_data, path),
        }

    if traversal == TraversalType.UPSTREAM:
        rows = _directed_walk(graph_data, start_id, mode="dependency", depth=depth)
    elif traversal == TraversalType.DOWNSTREAM:
        rows = _directed_walk(graph_data, start_id, mode="impact", depth=depth)
    elif traversal == TraversalType.FULL_GRAPH:
        rows = _walk(graph_data, start_id, depth=depth, mode="both")
    else:
        rows = _merge_rows(
            _directed_walk(graph_data, start_id, mode="dependency", depth=depth),
            _directed_walk(graph_data, start_id, mode="impact", depth=depth),
        )

    node_ids = {start_id, *[row["node_id"] for row in rows]}
    return {
        "node": graph_data["node_by_id"][start_id]["name"],
        "node_id": start_id,
        "traversal_type": traversal.value,
        "paths": _representative_paths(rows),
        "nodes": rows,
        "edges": [
            edge
            for edge in graph_data["edges"]
            if edge["source"] in node_ids and edge["target"] in node_ids
        ],
    }


def shortest_path(
    source: str,
    target: str,
    organization_id: str | None = None,
) -> list[dict[str, Any]]:
    return EnterpriseGraphService.shortest_path(source, target, organization_id)


def _directed_walk(
    graph_data: dict[str, Any],
    start_id: str,
    mode: str,
    depth: int,
) -> list[dict[str, Any]]:
    rows = []
    queue = deque([(start_id, 0, [])])
    visited = {start_id}
    while queue:
        current_id, current_depth, path = queue.popleft()
        if current_depth >= depth:
            continue
        for edge, neighbor_id in _oriented_neighbors(graph_data, current_id, mode):
            if neighbor_id in visited:
                continue
            visited.add(neighbor_id)
            node = graph_data["node_by_id"].get(neighbor_id)
            if not node:
                continue
            next_path = [
                *path,
                {
                    "from": edge.get("source_name"),
                    "to": edge.get("target_name"),
                    "relationship": edge.get("relationship_type"),
                },
            ]
            rows.append(_row(node, edge, current_depth + 1, next_path))
            queue.append((neighbor_id, current_depth + 1, next_path))
    return _prioritized(rows)


def _walk(graph_data: dict[str, Any], start_id: str, depth: int, mode: str) -> list[dict[str, Any]]:
    del mode
    rows = []
    queue = deque([(start_id, 0, [])])
    visited = {start_id}
    while queue:
        current_id, current_depth, path = queue.popleft()
        if current_depth >= depth:
            continue
        for neighbor_id in graph_data["adjacency"].get(current_id, set()):
            if neighbor_id in visited:
                continue
            visited.add(neighbor_id)
            edge = graph_data["edge_lookup"].get((current_id, neighbor_id), {})
            node = graph_data["node_by_id"].get(neighbor_id)
            if not node:
                continue
            next_path = [
                *path,
                {
                    "from": edge.get("source_name"),
                    "to": edge.get("target_name"),
                    "relationship": edge.get("relationship_type"),
                },
            ]
            rows.append(_row(node, edge, current_depth + 1, next_path))
            queue.append((neighbor_id, current_depth + 1, next_path))
    return _prioritized(rows)


def _row(
    node: dict[str, Any],
    edge: dict[str, Any],
    depth: int,
    path: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "depth": depth,
        "node_id": node["id"],
        "node": node["name"],
        "node_type": node["type"],
        "relationship": edge.get("relationship_type"),
        "source": edge.get("source_name"),
        "target": edge.get("target_name"),
        "metadata": node.get("metadata") or {},
        "path": path,
    }


def _oriented_neighbors(
    graph_data: dict[str, Any],
    current_id: str,
    mode: str,
) -> list[tuple[dict[str, Any], str]]:
    pairs = []
    for edge in graph_data["edges"]:
        if edge["source"] != current_id and edge["target"] != current_id:
            continue
        source = graph_data["node_by_id"].get(edge["source"], {})
        target = graph_data["node_by_id"].get(edge["target"], {})
        forward = _dependency_direction(edge, source, target)
        if mode == "impact":
            if current_id == edge["target"] and forward == "source_to_target":
                pairs.append((edge, edge["source"]))
            elif current_id == edge["source"] and forward == "target_to_source":
                pairs.append((edge, edge["target"]))
            elif current_id == edge["source"] and _is_impact_side_edge(edge):
                pairs.append((edge, edge["target"]))
            elif forward == "both":
                pairs.append((edge, edge["target"] if current_id == edge["source"] else edge["source"]))
        else:
            if current_id == edge["source"] and forward == "source_to_target":
                pairs.append((edge, edge["target"]))
            elif current_id == edge["target"] and forward == "target_to_source":
                pairs.append((edge, edge["source"]))
            elif forward == "both":
                pairs.append((edge, edge["target"] if current_id == edge["source"] else edge["source"]))
    return pairs


def _dependency_direction(
    edge: dict[str, Any],
    source: dict[str, Any],
    target: dict[str, Any],
) -> str:
    pair = (source.get("type") or edge.get("source_type"), target.get("type") or edge.get("target_type"))
    reverse_pair = (pair[1], pair[0])
    relation = str(edge.get("relationship_type") or "").upper()
    if pair in DEPENDENCY_FORWARD:
        return "source_to_target"
    if reverse_pair in DEPENDENCY_FORWARD:
        return "target_to_source"
    if relation in {"SUPPORTS", "OWNS", "USES", "HOSTED_ON", "PART_OF", "PROVIDED_BY", "GENERATES_COST"}:
        return "source_to_target"
    if relation in {"IMPLEMENTS", "EXECUTES"}:
        return "target_to_source"
    if relation in {"RELATED_TO", "APPROVED_BY"}:
        return "both"
    return "source_to_target"


def _is_impact_side_edge(edge: dict[str, Any]) -> bool:
    return str(edge.get("relationship_type") or "").upper() in {
        "OWNED_BY",
        "FUNDED_BY",
        "GENERATES_COST",
        "BELONGS_TO",
        "SUPPORTED_BY",
        "PART_OF",
        "USES",
        "RELATED_TO",
    }


def _prioritized(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {
        "Technology": 1,
        "Cloud Provider": 2,
        "Cloud Resource": 3,
        "Enterprise Asset": 4,
        "Application": 5,
        "Business Service": 6,
        "Business Capability": 7,
        "Department": 8,
        "Owner": 9,
        "Cost Center": 10,
        "Recommendation": 11,
        "Workflow": 12,
        "Execution": 13,
        "Audit": 14,
    }
    return sorted(rows, key=lambda row: (row["depth"], priority.get(row["node_type"], 99), row["node"]))


def _merge_rows(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {}
    for group in groups:
        for row in group:
            existing = merged.get(row["node_id"])
            if not existing or row["depth"] < existing["depth"]:
                merged[row["node_id"]] = row
    return _prioritized(list(merged.values()))


def _representative_paths(rows: list[dict[str, Any]], limit: int = 10) -> list[list[dict[str, Any]]]:
    paths = []
    for row in sorted(rows, key=lambda item: (-item["depth"], item["node"]))[:limit]:
        paths.append(row.get("path") or [])
    return paths


def _path_edges(graph_data: dict[str, Any], path: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges = []
    for index, row in enumerate(path[1:], start=1):
        previous = path[index - 1]
        edge = graph_data["edge_lookup"].get(
            (
                EnterpriseGraphService._resolve_node_id(graph_data, previous["node"]) or "",
                EnterpriseGraphService._resolve_node_id(graph_data, row["node"]) or "",
            )
        )
        if edge:
            edges.append(edge)
    return edges
